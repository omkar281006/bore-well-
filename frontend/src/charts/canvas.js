// Shared canvas helpers. Chart colours come from CSS custom properties so both themes work.

export const C = {};

export function refreshChartColors() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  Object.assign(C, {
    aqua: v('--aqua'), aqua2: v('--aqua-2'), lat: v('--laterite'), mist: v('--mist'), muted: v('--muted'),
    faint: v('--faint'), line: v('--line'), ok: v('--ok'), watch: v('--watch'), act: v('--act'), crit: v('--crit'),
    fault: v('--fault'), rain: '#6f9fc4', fx: v('--fx'),
  });
}

export const MONO = '11px "JetBrains Mono", ui-monospace, monospace';
export const BODY = '13px Figtree, system-ui, sans-serif';

/** Size the canvas to its CSS box at device pixel ratio and return a cleared 2D context. */
export function prep(cv) {
  const r = cv.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(10, r.width);
  const h = Math.max(10, r.height);
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx, w, h };
}

export function niceStep(range, n) {
  const raw = range / n;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}

/** Horizontal grid lines with labels on the left. */
export function yAxis(ctx, box, y0, y1, Y, unit = '') {
  ctx.font = MONO;
  ctx.fillStyle = C.faint;
  ctx.strokeStyle = C.line;
  ctx.lineWidth = 1;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  const st = niceStep(Math.abs(y1 - y0), 4);
  for (let v = Math.ceil(Math.min(y0, y1) / st) * st; v <= Math.max(y0, y1) + 1e-9; v += st) {
    const y = Math.round(Y(v)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(box.l, y);
    ctx.lineTo(box.l + box.w, y);
    ctx.stroke();
    ctx.fillText((st < 1 ? v.toFixed(1) : Math.round(v)) + unit, box.l - 6, y);
  }
}

/** Expanding ring that marks a live value. */
export function pulseDot(ctx, x, y, color, scale = 1) {
  const t = ((performance.now() / 1000) % 1.6) / 1.6;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.globalAlpha = (1 - t) * 0.85;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.arc(x, y, (4 + t * 15) * scale, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

/** Rotating radar sweep centred on a point. */
export function radar(ctx, p, w, h) {
  if (!p) return;
  const a = (performance.now() / 1000) * 1.1;
  const R = Math.hypot(w, h);
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.strokeStyle = 'rgba(' + C.fx + ',.12)';
  ctx.lineWidth = 1;
  for (let r = 50; r < R; r += 50) {
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.rotate(a);
  for (let i = 0; i < 26; i++) {
    ctx.fillStyle = 'rgba(' + C.fx + ',' + 0.075 * (1 - i / 26) + ')';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, R, -(i + 1) * 0.03, -i * 0.03);
    ctx.closePath();
    ctx.fill();
  }
  ctx.strokeStyle = C.aqua;
  ctx.globalAlpha = 0.6;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(R, 0);
  ctx.stroke();
  ctx.restore();
}

/** "rgba(r,g,b,a)" from the theme's accent triplet. */
export const accent = (a) => 'rgba(' + C.fx + ',' + a + ')';

export function emptyState(ctx, box, text) {
  ctx.fillStyle = C.muted;
  ctx.font = BODY;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.fillText(text, box.l, box.t + 20);
}
