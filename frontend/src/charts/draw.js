// Canvas chart renderers. Each takes a canvas and the live simulator and draws one frame.
import { MONSOON_ONSET_DAY, SEASON_DAYS } from '../sim/constants.js';
import { FLEET, WARDS, fleetState } from '../sim/fleet.js';
import { clamp, dateOf, fmtDay, MONTHS, SEASON_START } from '../sim/util.js';
import { accent, C, emptyState, MONO, niceStep, prep, pulseDot, radar, yAxis } from './canvas.js';

/** Whole season: water table, daily deepest level, rain, intake line and the forecast cone. */
export function drawSeason(cv, s) {
  const { ctx, w, h } = prep(cv);
  const sc = s.sc;
  const box = { l: 46, t: 24, w: w - 58, h: h - 50 };
  const X = (d) => box.l + (d / SEASON_DAYS) * box.w;
  const Y = (v) => box.t + (v / sc.depth) * box.h;

  ctx.fillStyle = accent(0.06);
  ctx.fillRect(X(MONSOON_ONSET_DAY), box.t, X(SEASON_DAYS) - X(MONSOON_ONSET_DAY), box.h);
  yAxis(ctx, box, 0, sc.depth, Y, ' m');
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillStyle = C.faint;
  for (let m = 0; m < 12; m++) {
    const d = (new Date(dateOf(0)).setMonth(9 + m) - SEASON_START) / 86400e3;
    const x = X(d);
    ctx.fillText(MONTHS.en[(9 + m) % 12], x + box.w / 24, box.t + box.h + 8);
    ctx.strokeStyle = C.line;
    ctx.beginPath();
    ctx.moveTo(Math.round(x) + 0.5, box.t + box.h);
    ctx.lineTo(Math.round(x) + 0.5, box.t + box.h + 4);
    ctx.stroke();
  }

  ctx.fillStyle = C.rain;
  ctx.globalAlpha = 0.7;
  for (const r of s.daily) {
    if (r.rain > 0.5) {
      const hh = Math.min(18, r.rain / 3);
      ctx.fillRect(X(r.day), box.t - hh - 2, Math.max(1.5, box.w / SEASON_DAYS), hh);
    }
  }
  ctx.globalAlpha = 1;

  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = C.lat;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(box.l, Y(sc.intake));
  ctx.lineTo(box.l + box.w, Y(sc.intake));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = C.lat;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'bottom';
  ctx.fillText('intake ' + sc.intake + ' m', box.l + 6, Y(sc.intake) - 3);

  const D = s.daily;
  if (D.length > 1) {
    const g = ctx.createLinearGradient(0, box.t, 0, box.t + box.h);
    g.addColorStop(0, accent(0.22));
    g.addColorStop(1, accent(0.02));
    ctx.beginPath();
    ctx.moveTo(X(D[0].day), box.t + box.h);
    D.forEach((r) => ctx.lineTo(X(r.day + 0.5), Y(r.swl)));
    ctx.lineTo(X(D[D.length - 1].day + 0.5), box.t + box.h);
    ctx.closePath();
    ctx.fillStyle = g;
    ctx.fill();

    ctx.strokeStyle = C.aqua2;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();
    D.forEach((r, i) => (i ? ctx.lineTo(X(r.day + 0.5), Y(r.peak)) : ctx.moveTo(X(r.day + 0.5), Y(r.peak))));
    ctx.stroke();
    ctx.globalAlpha = 1;

    ctx.shadowColor = C.aqua;
    ctx.shadowBlur = 16;
    ctx.strokeStyle = C.aqua;
    ctx.lineWidth = 2.4;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    D.forEach((r, i) => (i ? ctx.lineTo(X(r.day + 0.5), Y(r.swl)) : ctx.moveTo(X(r.day + 0.5), Y(r.swl))));
    ctx.stroke();
    const last = D[D.length - 1];
    ctx.fillStyle = C.aqua;
    ctx.beginPath();
    ctx.arc(X(last.day + 0.5), Y(last.swl), 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    pulseDot(ctx, X(last.day + 0.5), Y(last.swl), C.aqua);
  }

  const fc = s.forecast;
  if (fc && (fc.state === 'fail' || fc.state === 'ok') && Number.isFinite(fc.rate)) {
    const d0 = s.t / 24;
    const x0 = X(d0);
    const y0 = Y(fc.swl + fc.D);
    const yAt = (d) => Y(Math.min(sc.depth, fc.swl + fc.D + fc.rate * (d - d0)));
    const end = Math.min(fc.p50, 364);
    const early = Math.min(fc.p10, 364);
    const late = Math.min(fc.p90, 364);
    ctx.fillStyle = 'rgba(239,167,123,.14)';
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(X(early), fc.p10 < 364 ? Y(fc.limit) : yAt(early));
    ctx.lineTo(X(late), fc.p90 < 364 ? Y(fc.limit) : yAt(late));
    ctx.closePath();
    ctx.fill();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = C.act;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(X(end), yAt(end));
    ctx.stroke();
    ctx.setLineDash([]);
    if (fc.state === 'fail') {
      ctx.fillStyle = C.act;
      ctx.beginPath();
      ctx.arc(X(fc.p50), Y(fc.limit), 4.5, 0, Math.PI * 2);
      ctx.fill();
      const right = X(fc.p50) > box.l + box.w - 90;
      ctx.textAlign = right ? 'right' : 'left';
      ctx.textBaseline = 'bottom';
      ctx.fillText('dry ~' + fmtDay(fc.p50), X(fc.p50) + (right ? -6 : 6), Y(fc.limit) - 6);
    }
  }
  ctx.strokeStyle = C.mist;
  ctx.globalAlpha = 0.35;
  ctx.beginPath();
  ctx.moveTo(Math.round(X(s.t / 24)) + 0.5, box.t);
  ctx.lineTo(Math.round(X(s.t / 24)) + 0.5, box.t + box.h);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

/** Last 72 hours of measured depth with pump runs shaded. */
export function drawLast72(cv, s) {
  const { ctx, w, h } = prep(cv);
  const sc = s.sc;
  const box = { l: 46, t: 12, w: w - 58, h: h - 38 };
  const t1 = s.t;
  const t0 = t1 - 72;
  const pts = s.readings.filter((r) => r.t >= t0);
  let lo = Infinity;
  let hi = -Infinity;
  for (const p of pts) { lo = Math.min(lo, p.d); hi = Math.max(hi, p.d); }
  if (s.pumpOn) hi = Math.max(hi, s.dl);
  if (!Number.isFinite(lo)) { lo = s.swl - 1; hi = s.swl + 5; }
  const pad = Math.max(0.6, (hi - lo) * 0.12);
  lo -= pad;
  hi += pad;
  const X = (t) => box.l + ((t - t0) / 72) * box.w;
  const Y = (v) => box.t + ((v - lo) / (hi - lo)) * box.h;

  ctx.fillStyle = 'rgba(220,170,126,.12)';
  const runs = s.cycles.filter((c) => c.tOff > t0).map((c) => [c.tOn, c.tOff]);
  if (s.cur) runs.push([s.cur.tOn, s.cur.off != null ? s.cur.off : t1]);
  for (const [a, b] of runs) {
    const xa = X(Math.max(a, t0));
    const xb = X(Math.min(b, t1));
    if (xb > xa) ctx.fillRect(xa, box.t, xb - xa, box.h);
  }
  yAxis(ctx, box, lo, hi, Y, ' m');
  ctx.fillStyle = C.faint;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let t = Math.ceil(t0 / 12) * 12; t <= t1; t += 12) {
    ctx.fillText(dateOf(t).getHours() === 0 ? fmtDay(t / 24) : '12:00', X(t), box.t + box.h + 8);
  }
  if (sc.intake < hi && sc.intake > lo) {
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = C.lat;
    ctx.beginPath();
    ctx.moveTo(box.l, Y(sc.intake));
    ctx.lineTo(box.l + box.w, Y(sc.intake));
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.shadowColor = C.aqua;
  ctx.shadowBlur = 12;
  ctx.strokeStyle = C.aqua;
  ctx.lineWidth = 1.9;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  let prev = null;
  for (const p of pts) {
    if (!prev || p.t - prev.t > 0.4) ctx.moveTo(X(p.t), Y(p.d));
    else ctx.lineTo(X(p.t), Y(p.d));
    prev = p;
  }
  ctx.stroke();
  ctx.shadowBlur = 0;
  if (prev) pulseDot(ctx, X(prev.t), Y(prev.d), C.aqua);
  if (s.pumpOn) {
    ctx.fillStyle = C.lat;
    ctx.beginPath();
    ctx.arc(X(t1), Y(s.dl), 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText('pumping', X(t1) - 6, Y(s.dl) - 5);
  }
}

/** Theis recovery plot for the last finished cycle: residual drawdown vs log10(t/t'). */
export function drawRecovery(cv, s) {
  const { ctx, w, h } = prep(cv);
  const c = s.lastCycle;
  const box = { l: 46, t: 12, w: w - 58, h: h - 38 };
  if (!c || !c.pts) return emptyState(ctx, box, 'Waiting for the first full pump cycle.');
  const P = c.pts.filter((p) => p.t > c.tOff).map((p) => ({ x: Math.log10((p.t - c.tOn) / (p.t - c.tOff)), y: p.d - c.pre, late: p.t - c.tOff >= 0.75 }));
  const xm = Math.max(0.5, ...P.map((p) => p.x)) * 1.05;
  const ym = Math.max(0.5, ...P.map((p) => p.y)) * 1.1;
  const yl = Math.min(0, ...P.map((p) => p.y));
  const X = (v) => box.l + (v / xm) * box.w;
  const Y = (v) => box.t + box.h - ((v - yl) / (ym - yl)) * box.h;
  yAxis(ctx, box, yl, ym, Y, ' m');
  ctx.fillStyle = C.faint;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  const st = niceStep(xm, 4);
  for (let v = 0; v <= xm; v += st) ctx.fillText(v.toFixed(st < 1 ? 1 : 0), X(v), box.t + box.h + 8);
  ctx.textAlign = 'right';
  ctx.fillText('log₁₀(t / t′)', box.l + box.w, box.t + box.h - 6);
  for (const p of P) {
    ctx.fillStyle = p.late ? C.aqua : C.faint;
    ctx.globalAlpha = p.late ? 0.95 : 0.6;
    ctx.beginPath();
    ctx.arc(X(p.x), Y(p.y), p.late ? 3 : 2.2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  if (Number.isFinite(c.a)) {
    ctx.strokeStyle = C.act;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(X(0), Y(c.b));
    ctx.lineTo(X(xm), Y(c.b + c.a * xm));
    ctx.stroke();
  }
}

/** Received waveform and the gained matched-filter envelope against depth. */
export function drawEcho(cv, ping, pumpOn = false) {
  const { ctx, w, h } = prep(cv);
  const box = { l: 46, t: 10, w: w - 58, h: h - 36 };
  if (!ping) return emptyState(ctx, box, 'Pump running. The next ping fires when it stops.');
  if (pumpOn) {
    ctx.font = MONO;
    ctx.fillStyle = C.lat;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillText('pump running · showing last ping', box.l + box.w, box.t);
  }
  const p = ping;
  const topH = box.h * 0.32;
  const botT = box.t + topH + 12;
  const botH = box.h - topH - 12;

  ctx.strokeStyle = C.faint;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i < p.N; i += 2) {
    const x = box.l + (i / p.N) * box.w;
    const y = box.t + topH / 2 - (clamp(p.rx[i] / 0.12, -1, 1) * topH) / 2;
    if (i) ctx.lineTo(x, y);
    else ctx.moveTo(x, y);
  }
  ctx.stroke();
  ctx.fillStyle = C.faint;
  ctx.font = MONO;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillText('received (clipped)', box.l, box.t);

  const maxD = 150;
  const X = (d) => box.l + (d / maxD) * box.w;
  const depthAt = (l) => ((l / p.fs) * p.c) / 2;
  let em = 0;
  for (let l = 0; l < p.nL; l++) if (depthAt(l) > 4) em = Math.max(em, p.env[l]);
  ctx.strokeStyle = C.line;
  for (let d = 0; d <= 150; d += 25) {
    const x = Math.round(X(d)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(x, botT);
    ctx.lineTo(x, botT + botH);
    ctx.stroke();
    ctx.fillStyle = C.faint;
    ctx.textAlign = 'center';
    ctx.fillText(d + ' m', x, botT + botH + 6);
  }
  const yEnv = (l) => botT + botH - clamp(p.env[l] / em, 0, 1.05) * botH * 0.92;
  const g = ctx.createLinearGradient(0, botT, 0, botT + botH);
  g.addColorStop(0, accent(0.35));
  g.addColorStop(1, accent(0));
  ctx.beginPath();
  ctx.moveTo(X(0), botT + botH);
  let lastL = 0;
  for (let l = 0; l < p.nL && depthAt(l) <= maxD; l++) { ctx.lineTo(X(depthAt(l)), yEnv(l)); lastL = l; }
  ctx.lineTo(X(depthAt(lastL)), botT + botH);
  ctx.closePath();
  ctx.fillStyle = g;
  ctx.fill();
  ctx.strokeStyle = C.aqua;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  for (let l = 0; l <= lastL; l++) (l ? ctx.lineTo(X(depthAt(l)), yEnv(l)) : ctx.moveTo(X(0), yEnv(0)));
  ctx.stroke();

  const col = p.falseEchoOn ? C.fault : C.act;
  ctx.fillStyle = col;
  ctx.beginPath();
  ctx.arc(X(p.est), botT + botH * 0.08, 4.5, 0, Math.PI * 2);
  ctx.fill();
  const right = X(p.est) > box.l + box.w - 110;
  ctx.textAlign = right ? 'right' : 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText((p.falseEchoOn ? 'false echo ' : 'water ') + p.est.toFixed(2) + ' m', X(p.est) + (right ? -8 : 8), botT + botH * 0.08);

  const ph = ((performance.now() / 1000) % 2.2) / 2.2;
  const sx = box.l + ph * box.w;
  const gg = ctx.createLinearGradient(sx - 50, 0, sx, 0);
  gg.addColorStop(0, accent(0));
  gg.addColorStop(1, accent(0.3));
  ctx.fillStyle = gg;
  ctx.fillRect(sx - 50, box.t, 50, box.h);
  ctx.fillStyle = C.aqua;
  ctx.fillRect(sx, box.t, 1.5, box.h);
  pulseDot(ctx, X(p.est), botT + botH * 0.08, col);
}

const FLEET_COLORS = () => ({ ok: C.ok, watch: C.watch, act: C.act, crit: C.crit });

/** Ward map of the fleet with a radar sweep. Returns dot positions for hover tooltips. */
// Live mode: place registered wells on the same map. A ward named in the well's ward, location or
// name puts it in that ward; otherwise it is spread around the middle. Deterministic per well id.
function hash01(str, salt) {
  let x = 2166136261 ^ salt;
  for (let i = 0; i < str.length; i++) x = Math.imul(x ^ str.charCodeAt(i), 16777619);
  return ((x >>> 0) % 10000) / 10000;
}
export function liveFleetLayout(wells) {
  return wells.map((wl) => {
    if (wl.map && Number.isFinite(wl.map.x) && Number.isFinite(wl.map.y)) return { wl, x: wl.map.x, y: wl.map.y };
    const text = `${wl.ward || ''} ${wl.location || ''} ${wl.name || ''}`.toLowerCase();
    const ward = WARDS.find((wd) => text.includes(wd.n.toLowerCase()));
    const a = hash01(wl.well_id, 1) * Math.PI * 2;
    const r = ward ? 0.025 + hash01(wl.well_id, 2) * 0.06 : 0.12 + hash01(wl.well_id, 3) * 0.3;
    const cx = ward ? ward.x : 0.5;
    const cy = ward ? ward.y : 0.5;
    return { wl, x: Math.min(0.97, Math.max(0.03, cx + Math.cos(a) * r)), y: Math.min(0.95, Math.max(0.05, cy + Math.sin(a) * r * 1.3)) };
  });
}

export function drawFleet(cv, s, live) {
  const { ctx, w, h } = prep(cv);
  const day = s.t / 24;
  const pad = 22;
  const X = (x) => pad + x * (w - 2 * pad);
  const Y = (y) => pad + y * (h - 2 * pad);
  ctx.strokeStyle = 'rgba(111,159,196,.25)';
  ctx.lineWidth = 6;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(X(0), Y(0.62));
  ctx.bezierCurveTo(X(0.25), Y(0.7), X(0.4), Y(0.4), X(0.6), Y(0.55));
  ctx.bezierCurveTo(X(0.75), Y(0.65), X(0.85), Y(0.45), X(1), Y(0.5));
  ctx.stroke();
  ctx.fillStyle = 'rgba(111,159,196,.7)';
  ctx.font = 'italic 11px Figtree, system-ui';
  ctx.textAlign = 'left';
  ctx.fillText('Mula–Mutha', X(0.6) + 6, Y(0.58) + 14);
  ctx.font = MONO;
  ctx.textAlign = 'center';
  for (const wd of WARDS) {
    ctx.fillStyle = C.faint;
    ctx.fillText(wd.n.toUpperCase(), X(wd.x), Y(wd.y) - (wd.y < 0.4 ? 30 : -34));
  }
  const col = FLEET_COLORS();
  const positions = [];
  if (live) {
    const lc = { ...col, fault: C.watch, nodata: C.faint };
    for (const p of liveFleetLayout(live.wells)) {
      const sel = p.wl.well_id === live.selected;
      const x = X(p.x);
      const y = Y(p.y);
      const c = lc[p.wl.status] || C.faint;
      positions.push({ x, y, live: p.wl, self: sel });
      ctx.fillStyle = c;
      ctx.globalAlpha = 0.18;
      ctx.beginPath();
      ctx.arc(x, y, sel ? 16 : 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(x, y, sel ? 6 : 4.5, 0, Math.PI * 2);
      ctx.fill();
      if (p.wl.status === 'crit' || p.wl.status === 'act' || sel) pulseDot(ctx, x, y, sel ? C.aqua : c, sel ? 1.5 : 1);
      if (sel) {
        ctx.strokeStyle = C.mist;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(x, y, 10, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = C.faint;
      ctx.font = MONO;
      ctx.fillText(p.wl.well_id, x, y + (sel ? 24 : 20));
    }
    if (!live.wells.length) emptyState(ctx, { l: pad, t: pad }, 'No wells registered yet. Run the simulator fleet or connect a device.');
    radar(ctx, positions.find((p) => p.self), w, h);
    return positions;
  }
  for (const f of FLEET) {
    const st = fleetState(f, day, s);
    const x = X(f.x);
    const y = Y(f.y);
    positions.push({ x, y, f, st });
    ctx.fillStyle = col[st.st];
    ctx.globalAlpha = 0.18;
    ctx.beginPath();
    ctx.arc(x, y, f.self ? 16 : 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.arc(x, y, f.self ? 6 : 4.5, 0, Math.PI * 2);
    ctx.fill();
    if (st.st === 'crit' || st.st === 'act' || f.self) pulseDot(ctx, x, y, f.self ? C.aqua : col[st.st], f.self ? 1.5 : 1);
    if (f.self) {
      ctx.strokeStyle = C.mist;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(x, y, 10, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  radar(ctx, positions.find((p) => p.f.self), w, h);
  return positions;
}
