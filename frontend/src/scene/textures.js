// Procedural canvas textures: basalt, concrete, gravel, stone lining, slotted screen, steel, pump ribs.
import * as THREE from 'three';
import { mulberry32 } from '../sim/util.js';

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return [c, c.getContext('2d')];
}

function finish(c, repeat) {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.encoding = THREE.sRGBEncoding;
  t.anisotropy = 4;
  if (repeat) t.repeat.set(repeat[0], repeat[1]);
  return t;
}

/** Basalt with vesicles (gas bubbles), some filled with pale zeolite. */
export function rockTexture(base, vesicles, seed) {
  const [c, g] = canvas(256, 256);
  const r = mulberry32(seed);
  g.fillStyle = base;
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 2600; i++) {
    const a = r() * 0.07;
    g.fillStyle = 'rgba(255,255,255,' + a + ')';
    g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2);
    g.fillStyle = 'rgba(0,0,0,' + a * 1.6 + ')';
    g.fillRect(r() * 256, r() * 256, 1 + r() * 3, 1 + r() * 2);
  }
  for (let i = 0; i < vesicles; i++) {
    const x = r() * 256;
    const y = r() * 256;
    const rad = 0.8 + r() * 3.2;
    g.beginPath();
    g.ellipse(x, y, rad * 1.5, rad, 0, 0, Math.PI * 2);
    g.fillStyle = r() < 0.35 ? 'rgba(170,215,200,.38)' : 'rgba(0,0,0,.38)';
    g.fill();
  }
  for (let i = 0; i < 7; i++) {
    g.fillStyle = 'rgba(255,255,255,' + (0.015 + r() * 0.03) + ')';
    g.fillRect(0, r() * 256, 256, 1 + r() * 3);
  }
  return finish(c);
}

/** Lit and unlit apartment windows, used as an emissive map. */
export function windowTexture() {
  const [c, g] = canvas(128, 256);
  const r = mulberry32(5);
  g.fillStyle = '#000';
  g.fillRect(0, 0, 128, 256);
  for (let y = 10; y < 250; y += 20) {
    for (let x = 10; x < 120; x += 22) {
      g.fillStyle = r() < 0.42 ? 'rgba(243,214,160,' + (0.6 + r() * 0.4) + ')' : 'rgba(60,80,82,.6)';
      g.fillRect(x, y, 12, 10);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.encoding = THREE.sRGBEncoding;
  return t;
}

const PAINTERS = {
  concrete(g, r) {
    for (let i = 0; i < 3200; i++) {
      g.fillStyle = 'rgba(0,0,0,' + r() * 0.12 + ')';
      g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2);
      g.fillStyle = 'rgba(255,255,255,' + r() * 0.14 + ')';
      g.fillRect(r() * 256, r() * 256, 1, 1);
    }
  },
  gravel(g, r) {
    const cols = ['#8b8170', '#a69a86', '#6f6a5e', '#bdb19b'];
    for (let i = 0; i < 950; i++) {
      const z = 2 + r() * 5;
      g.fillStyle = cols[i % 4];
      g.beginPath();
      g.ellipse(r() * 256, r() * 256, z, z * 0.75, r() * 3, 0, Math.PI * 2);
      g.fill();
    }
  },
  stone(g, r) {
    const cols = ['#8a8070', '#7b7263', '#958b7a', '#6e665a'];
    let y = 0;
    while (y < 256) {
      const h = 18 + r() * 14;
      let x = -r() * 30;
      while (x < 256) {
        const w = 26 + r() * 30;
        g.fillStyle = cols[Math.floor(r() * 4)];
        g.fillRect(x + 2, y + 2, w - 4, h - 4);
        x += w;
      }
      y += h;
    }
  },
  slots(g) {
    for (let y = 6; y < 256; y += 12) for (let x = 4; x < 256; x += 36) { g.fillStyle = 'rgba(10,20,22,.88)'; g.fillRect(x, y, 26, 3); }
  },
  steel(g, r) {
    for (let i = 0; i < 400; i++) { g.fillStyle = 'rgba(255,255,255,' + r() * 0.08 + ')'; g.fillRect(0, r() * 256, 256, 1); }
    for (let i = 0; i < 140; i++) { g.fillStyle = 'rgba(120,70,30,' + r() * 0.28 + ')'; g.beginPath(); g.arc(r() * 256, r() * 256, 1 + r() * 4, 0, 7); g.fill(); }
  },
  ribs(g) {
    for (let y = 0; y < 256; y += 16) { g.fillStyle = 'rgba(0,0,0,.35)'; g.fillRect(0, y, 256, 3); g.fillStyle = 'rgba(255,255,255,.3)'; g.fillRect(0, y + 3, 256, 1); }
  },
  intake(g) {
    for (let x = 0; x < 256; x += 10) { g.fillStyle = 'rgba(0,0,0,.85)'; g.fillRect(x, 30, 5, 196); }
  },
};

/** Material-style texture: kind is one of concrete, gravel, stone, slots, steel, ribs, intake. */
export function surfaceTexture(base, kind, seed, rx = 1, ry = 1) {
  const [c, g] = canvas(256, 256);
  g.fillStyle = base;
  g.fillRect(0, 0, 256, 256);
  PAINTERS[kind](g, mulberry32(seed));
  return finish(c, [rx, ry]);
}

/** Vertical sky gradient used as the scene background. */
export function gradientTexture(stops) {
  const [c, g] = canvas(8, 256);
  const gr = g.createLinearGradient(0, 0, 0, 256);
  stops.forEach(([at, col]) => gr.addColorStop(at, col));
  g.fillStyle = gr;
  g.fillRect(0, 0, 8, 256);
  const t = new THREE.CanvasTexture(c);
  t.encoding = THREE.sRGBEncoding;
  return t;
}

/** Soft round sprite for additive particles. */
export function dotTexture() {
  const [c, g] = canvas(64, 64);
  const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.25, 'rgba(200,255,245,.85)');
  gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

/** Radial glow disc under the cutaway. */
export function glowTexture() {
  const [c, g] = canvas(256, 256);
  const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(128,217,205,.6)');
  gr.addColorStop(0.35, 'rgba(79,178,167,.2)');
  gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}
