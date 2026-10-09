"""
BoreWise AWS Backend API & Ingestion Engine

Provides AWS Lambda handler function and local HTTP server endpoint for:
1. Ingesting IoT & simulated telemetry payloads.
2. Validating JSON schema & physical boundary rules.
3. Persisting valid telemetry into AWS DynamoDB (or local fallback storage).
4. Serving recent telemetry records to the dashboard or downstream subscribers.
"""

import os
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List
try:
    from backend.schema import validate_telemetry_payload
except ImportError:
    from schema import validate_telemetry_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BoreWiseBackend")

# Global in-memory storage fallback for local development without AWS credentials
LOCAL_TELEMETRY_STORE: List[Dict[str, Any]] = []

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "BoreWiseTelemetry")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_dynamodb_table():
    """Initializes DynamoDB table resource if boto3 & credentials exist."""
    try:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        return dynamodb.Table(TABLE_NAME)
    except Exception as e:
        logger.warning(f"DynamoDB connection unavailable ({e}). Using local in-memory store fallback.")
        return None


def handle_telemetry_post(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """
    Validates and stores a telemetry record.
    
    Returns:
        (status_code: int, response_dict: dict)
    """
    is_valid, error_msg = validate_telemetry_payload(payload)
    if not is_valid:
        logger.warning(f"Validation failed: {error_msg}")
        return 400, {
            "status": "error",
            "message": "Schema validation failed",
            "error": error_msg,
            "received_payload": payload
        }

    table = get_dynamodb_table()
    if table is not None:
        try:
            # Format numbers for DynamoDB (boto3 Decimal conversion)
            from decimal import Decimal
            item = json.loads(json.dumps(payload), parse_float=Decimal)
            table.put_item(Item=item)
            logger.info(f"Persisted record to DynamoDB table '{TABLE_NAME}'")
        except Exception as e:
            logger.error(f"DynamoDB write error: {e}. Falling back to local store.")
            LOCAL_TELEMETRY_STORE.append(payload)
    else:
        LOCAL_TELEMETRY_STORE.append(payload)

    return 201, {
        "status": "success",
        "message": "Telemetry record ingested and stored successfully",
        "well_id": payload["well_id"],
        "timestamp": payload["timestamp"],
        "data_source": payload["data_source"]
    }


def handle_telemetry_get(well_id: str = "BW-001", limit: int = 100) -> Tuple[int, Dict[str, Any]]:
    """Retrieves recent telemetry records for a given well."""
    table = get_dynamodb_table()
    records = []

    if table is not None:
        try:
            from boto3.dynamodb.conditions import Key
            res = table.query(
                KeyConditionExpression=Key("well_id").eq(well_id),
                ScanIndexForward=False,
                Limit=limit
            )
            records = res.get("Items", [])
            # Convert Decimals back to float
            for r in records:
                for k, v in r.items():
                    if hasattr(v, "to_eng_string") or type(v).__name__ == "Decimal":
                        r[k] = float(v)
        except Exception as e:
            logger.error(f"DynamoDB query failed: {e}. Reading from local store.")
            records = [r for r in LOCAL_TELEMETRY_STORE if r.get("well_id") == well_id][-limit:]
    else:
        records = [r for r in LOCAL_TELEMETRY_STORE if r.get("well_id") == well_id][-limit:]

    return 200, {
        "status": "success",
        "count": len(records),
        "well_id": well_id,
        "telemetry": records
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function for API Gateway / Lambda Function URL.
    """
    http_method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path", "/")

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
    }

    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    if http_method == "POST":
        try:
            body_str = event.get("body", "{}")
            payload = json.loads(body_str) if isinstance(body_str, str) else body_str
            status_code, response_body = handle_telemetry_post(payload)
        except Exception as e:
            status_code = 400
            response_body = {"status": "error", "message": f"Invalid JSON body: {str(e)}"}

        return {
            "statusCode": status_code,
            "headers": headers,
            "body": json.dumps(response_body)
        }

    elif http_method == "GET":
        query_params = event.get("queryStringParameters") or {}
        well_id = query_params.get("well_id", "BW-001")
        status_code, response_body = handle_telemetry_get(well_id=well_id)

        return {
            "statusCode": status_code,
            "headers": headers,
            "body": json.dumps(response_body)
        }

    return {
        "statusCode": 405,
        "headers": headers,
        "body": json.dumps({"status": "error", "message": f"Method {http_method} not allowed"})
    }


class LocalHTTPRequestHandler(BaseHTTPRequestHandler):
    """Simple HTTP Request Handler for local testing."""

    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        status_code, response_body = handle_telemetry_get(well_id="BW-001")
        self._set_headers(status_code)
        self.wfile.write(json.dumps(response_body).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
            status_code, response_body = handle_telemetry_post(payload)
        except Exception as e:
            status_code = 400
            response_body = {"status": "error", "message": f"Malformed request: {str(e)}"}

        self._set_headers(status_code)
        self.wfile.write(json.dumps(response_body).encode("utf-8"))


def run_local_server(port: int = 8000):
    """Runs local server on port 8000."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, LocalHTTPRequestHandler)
    print(f"[BoreWise] Ingestion Server running at http://localhost:{port}/telemetry")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local server.")
        httpd.server_close()


if __name__ == "__main__":
    run_local_server(8000)
