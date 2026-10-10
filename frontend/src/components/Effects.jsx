// Motion helpers: magnetic buttons, tilt-and-spotlight cards, counting numbers,
// and the ambient background (aurora, drifting particles, click ripples, grain).
import { useEffect, useRef, useState } from 'react';
import { C } from '../charts/canvas.js';
import { reduceMotion } from '../hooks/SimProvider.jsx';

export function MagneticButton({ className = 'btn', children, ...rest }) {
  const ref = useRef(null);
  const move = (e) => {
    if (reduceMotion || e.pointerType !== 'mouse') return;
    const r = ref.current.getBoundingClientRect();
    ref.current.style.transform = `translate(${((e.clientX - r.left - r.width / 2) * 0.12).toFixed(1)}px, ${((e.clientY - r.top - r.height / 2) * 0.2).toFixed(1)}px)`;
  };
  return (
    <button ref={ref} type="button" className={className} onPointerMove={move} onPointerLeave={() => (ref.current.style.transform = '')} {...rest}>
      {children}
    </button>
  );
}

/** Card that tilts toward the pointer and carries a spotlight glow. */
export function Card({ className = '', index = 0, children, ...rest }) {
  const ref = useRef(null);
  const move = (e) => {
    const el = ref.current;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    el.style.setProperty('--mx', x * 100 + '%');
    el.style.setProperty('--my', y * 100 + '%');
    if (!reduceMotion && e.pointerType === 'mouse') {
      el.style.transform = `perspective(1000px) rotateX(${((0.5 - y) * 2.6).toFixed(2)}deg) rotateY(${((x - 0.5) * 2.6).toFixed(2)}deg)`;
    }
  };
  return (
    <article ref={ref} className={'card ' + className} style={{ '--i': index }} onPointerMove={move} onPointerLeave={() => (ref.current.style.transform = '')} {...rest}>
      {children}
    </article>
  );
}

/** Number that eases toward its target each frame. */
export function CountUp({ value, decimals = 0, fallback = '—' }) {
  const ref = useRef(null);
  const cur = useRef(0);
  const target = useRef(value);
  target.current = value;
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const tick = (now) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const t = target.current;
      if (ref.current) {
        if (t == null || !Number.isFinite(t)) ref.current.textContent = fallback;
        else {
          cur.current += (t - cur.current) * (reduceMotion ? 1 : Math.min(1, dt * 5));
          ref.current.textContent = cur.current.toFixed(decimals);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [decimals, fallback]);
  return <span ref={ref}>{fallback}</span>;
}

/** Fixed background: aurora blobs, particles that drift up and avoid the pointer, click ripples. */
export function Ambient() {
  const ref = useRef(null);
  useEffect(() => {
    if (reduceMotion) return undefined;
    const cv = ref.current;
    const ctx = cv.getContext('2d');
    let w = 0;
    let h = 0;
    const resize = () => {
      const d = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      cv.width = w * d;
      cv.height = h * d;
      ctx.setTransform(d, 0, 0, d, 0, 0);
    };
    resize();
    const motes = Array.from({ length: 70 }, () => ({ x: Math.random() * w, y: Math.random() * h, r: 0.6 + Math.random() * 2.2, v: 6 + Math.random() * 16, p: Math.random() * 6.28 }));
    const ripples = [];
    const mouse = { x: -999, y: -999 };
    const onMove = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; };
    const onDown = (e) => { if (!e.target.closest('button,input,label,canvas,a,.hud,.cams')) ripples.push({ x: e.clientX, y: e.clientY, t: 0 }); };
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown);
    let raf = 0;
    let last = performance.now();
    const loop = (now) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const fx = C.fx || '128,217,205';
      ctx.clearRect(0, 0, w, h);
      for (const m of motes) {
        m.y -= m.v * dt;
        m.x += Math.sin((m.p += dt * 0.6)) * dt * 8;
        if (m.y < -10) { m.y = h + 10; m.x = Math.random() * w; }
        const d = Math.hypot(m.x - mouse.x, m.y - mouse.y) || 1;
        if (d < 150) {
          const f = (150 - d) / 150;
          m.x += ((m.x - mouse.x) / d) * f * 40 * dt;
          m.y += ((m.y - mouse.y) / d) * f * 40 * dt;
        }
        ctx.fillStyle = `rgba(${fx},${0.25 + (d < 150 ? ((150 - d) / 150) * 0.6 : 0)})`;
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2);
        ctx.fill();
      }
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i];
        r.t += dt;
        if (r.t > 1.6) { ripples.splice(i, 1); continue; }
        for (let k = 0; k < 3; k++) {
          const tt = r.t - k * 0.18;
          if (tt < 0) continue;
          ctx.strokeStyle = `rgba(${k === 2 ? '220,170,126' : fx},${Math.max(0, 1 - tt / 1.4) * 0.7})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(r.x, r.y, tt * 140, 0, Math.PI * 2);
          ctx.stroke();
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onDown);
    };
  }, []);
  return (
    <>
      <div className="aurora" aria-hidden="true"><i /><i /><i /></div>
      <canvas className="fx" ref={ref} aria-hidden="true" />
      <div className="grain" aria-hidden="true" />
      <div className="vignette" aria-hidden="true" />
    </>
  );
}

/** Sonar intro screen; removes itself after the camera dive starts. */
export function Intro() {
  const [done, setDone] = useState(reduceMotion);
  useEffect(() => {
    const t = setTimeout(() => setDone(true), 3500);
    return () => clearTimeout(t);
  }, []);
  if (done) return null;
  return (
    <div className="intro" aria-hidden="true">
      <div className="intro-sonar"><i /><i /><i /><i /></div>
      <div className="intro-word">BOREWISE</div>
      <div className="intro-sub">Listening to the aquifer</div>
    </div>
  );
}
