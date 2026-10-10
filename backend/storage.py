"""
Storage for telemetry and well records.

Single DynamoDB table (PK well_id, SK timestamp), as in the original design:
* readings use the ISO timestamp as the sort key
* the well's registration lives in the same partition under sort key "#META"
  ('#' sorts before digits, and readings never start with it)

Without AWS credentials (local development, tests) a MemoryStore is used. Set
BOREWISE_DATA_DIR to make it persist to JSON-lines files between restarts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("BoreWiseStorage")
META_SK = "#META"


def _to_plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: _to_plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_to_plain(x) for x in v]
    return v


class MemoryStore:
    kind = "memory"

    def __init__(self, data_dir: Optional[str] = None):
        self._lock = threading.Lock()
        self._readings: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._wells: Dict[str, Dict[str, Any]] = {}
        self.data_dir = data_dir
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
            self._load()

    # -- persistence (optional)
    def _load(self) -> None:
        wells_file = os.path.join(self.data_dir, "wells.json")
        if os.path.exists(wells_file):
            with open(wells_file, encoding="utf-8") as fh:
                self._wells = json.load(fh)
        for name in os.listdir(self.data_dir):
            if name.endswith(".jsonl"):
                with open(os.path.join(self.data_dir, name), encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            rec = json.loads(line)
                            self._readings.setdefault(rec["well_id"], {})[rec["timestamp"]] = rec
        logger.info("Loaded %d wells and %d readings from %s", len(self._wells), sum(map(len, self._readings.values())), self.data_dir)

    def _append(self, records: List[Dict[str, Any]]) -> None:
        if not self.data_dir:
            return
        by_well: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            by_well.setdefault(r["well_id"], []).append(r)
        for wid, rows in by_well.items():
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in wid)
            with open(os.path.join(self.data_dir, f"{safe}.jsonl"), "a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")

    # -- readings
    def put_readings(self, records: List[Dict[str, Any]]) -> int:
        with self._lock:
            for r in records:
                self._readings.setdefault(r["well_id"], {})[r["timestamp"]] = r
            self._append(records)
        return len(records)

    def query_readings(self, well_id: str, since: Optional[str] = None, limit: Optional[int] = None, newest_first: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            rows = list(self._readings.get(well_id, {}).values())
        if since:
            rows = [r for r in rows if r["timestamp"] >= since]
        rows.sort(key=lambda r: r["timestamp"], reverse=newest_first)
        return rows[:limit] if limit else rows

    # -- wells
    def put_well(self, cfg: Dict[str, Any]) -> None:
        with self._lock:
            self._wells[cfg["well_id"]] = cfg
            if self.data_dir:
                with open(os.path.join(self.data_dir, "wells.json"), "w", encoding="utf-8") as fh:
                    json.dump(self._wells, fh)

    def get_well(self, well_id: str) -> Optional[Dict[str, Any]]:
        return self._wells.get(well_id)

    def list_wells(self) -> List[Dict[str, Any]]:
        return list(self._wells.values())


class DynamoStore:
    kind = "dynamodb"

    def __init__(self, table):
        self.table = table

    def put_readings(self, records: List[Dict[str, Any]]) -> int:
        with self.table.batch_writer(overwrite_by_pkeys=["well_id", "timestamp"]) as batch:
            for r in records:
                batch.put_item(Item=json.loads(json.dumps(r), parse_float=Decimal))
        return len(records)

    def query_readings(self, well_id: str, since: Optional[str] = None, limit: Optional[int] = None, newest_first: bool = False) -> List[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        cond = Key("well_id").eq(well_id) & (Key("timestamp").gte(since) if since else Key("timestamp").gt("0"))
        kwargs: Dict[str, Any] = {"KeyConditionExpression": cond, "ScanIndexForward": not newest_first}
        items: List[Dict[str, Any]] = []
        while True:
            if limit:
                kwargs["Limit"] = limit - len(items)
            res = self.table.query(**kwargs)
            items.extend(res.get("Items", []))
            if "LastEvaluatedKey" not in res or (limit and len(items) >= limit):
                break
            kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]
        return [_to_plain(i) for i in items if i.get("timestamp") != META_SK]

    def put_well(self, cfg: Dict[str, Any]) -> None:
        item = json.loads(json.dumps({**cfg, "timestamp": META_SK}), parse_float=Decimal)
        self.table.put_item(Item=item)

    def get_well(self, well_id: str) -> Optional[Dict[str, Any]]:
        res = self.table.get_item(Key={"well_id": well_id, "timestamp": META_SK})
        item = res.get("Item")
        if not item:
            return None
        item = _to_plain(item)
        item.pop("timestamp", None)
        return item

    def list_wells(self) -> List[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Attr

        res = self.table.scan(FilterExpression=Attr("timestamp").eq(META_SK))
        out = []
        for item in res.get("Items", []):
            item = _to_plain(item)
            item.pop("timestamp", None)
            out.append(item)
        return out


_STORE = None


def get_store():
    """DynamoDB when DYNAMODB_TABLE is set and boto3 can reach it, otherwise the in-memory store."""
    global _STORE
    if _STORE is not None:
        return _STORE
    table_name = os.environ.get("DYNAMODB_TABLE")
    if table_name:
        try:
            import boto3

            table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-south-1")).Table(table_name)
            table.load()
            _STORE = DynamoStore(table)
            logger.info("Using DynamoDB table %s", table_name)
            return _STORE
        except Exception as exc:  # noqa: BLE001 - fall back for local runs
            logger.warning("DynamoDB unavailable (%s); using the in-memory store", exc)
    _STORE = MemoryStore(os.environ.get("BOREWISE_DATA_DIR") or None)
    return _STORE


def reset_store(store=None) -> None:
    """For tests: replace the cached store."""
    global _STORE
    _STORE = store
