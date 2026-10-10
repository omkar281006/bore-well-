// The 3D cutaway: Deccan basalt block, the bore for the selected type, the water table
// with its cone of depression, fractures, sonar pings, particles, bloom and camera flights.
// Framework-free so React only mounts it and feeds it the simulator each frame.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { GammaCorrectionShader } from 'three/examples/jsm/shaders/GammaCorrectionShader.js';
import { RADIUS_OF_INFLUENCE } from '../sim/constants.js';
import { clamp, mulberry32 } from '../sim/util.js';
import { buildWell, disposeGroup } from './buildWell.js';
import { CAMERAS, K, L, LAYERS, PUMP_HOUSE, WELL } from './layout.js';
import { dotTexture, glowTexture, gradientTexture, rockTexture, windowTexture } from './textures.js';

const SKY = {
  dark: [[0, '#173332'], [0.5, '#0a1618'], [1, '#030809']],
  light: [[0, '#f4faf8'], [0.5, '#d9e8e4'], [1, '#b3c9c4']],
};

export class WellScene {
  constructor(canvas, labelsEl, { reduceMotion = false } = {}) {
    this.canvas = canvas;
    this.labelsEl = labelsEl;
    this.reduce = reduceMotion;
    this.labels = [];
    this.wellLabels = [];
    this.fracs = [];
    this.shocks = [];
    this.light = false;
    this.lastSc = null;
    this.pingVis = null;
    this.camTween = null;
    this.userTouched = false;
    this.frameN = 0;
    this.dayF = 0.6;
    this.tmp = new THREE.Vector3();
    this.size = { w: 1, h: 1 };

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    this.renderer = renderer;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0a1618, 34, 70);
    this.scene = scene;

    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 200);
    camera.position.set(42, 30, 48); // starts high; the intro flies it in
    this.camera = camera;

    const controls = new OrbitControls(camera, canvas);
    controls.target.set(0, -6.2, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.enablePan = false;
    controls.minDistance = 2.5;
    controls.maxDistance = 46;
    controls.maxPolarAngle = Math.PI * 0.62;
    controls.minPolarAngle = Math.PI * 0.18;
    controls.autoRotate = !this.reduce;
    controls.autoRotateSpeed = 0.28;
    controls.addEventListener('start', () => {
      controls.autoRotate = false;
      this.userTouched = true;
      this.camTween = null;
    });
    this.controls = controls;

    this.hemi = new THREE.HemisphereLight(0xcfe9e4, 0x14201f, 0.8);
    scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xfff0dc, 0.85);
    this.sun.position.set(12, 22, 10);
    scene.add(this.sun);
    const fill = new THREE.DirectionalLight(0x80d9cd, 0.25);
    fill.position.set(-14, -4, 12);
    scene.add(fill);
    this.wellLight = new THREE.PointLight(0x80d9cd, 0.9, 9, 2);
    scene.add(this.wellLight);

    this.mats = {
      wmat: new THREE.MeshStandardMaterial({ color: 0x5fc8bc, emissive: 0x1d6b64, emissiveIntensity: 0.6, roughness: 0.25, metalness: 0.1, transparent: true, opacity: 0.62 }),
      riserMat: new THREE.MeshStandardMaterial({ color: 0x2a2e2f, roughness: 0.55, metalness: 0.1, emissive: 0x80d9cd, emissiveIntensity: 0 }),
      pumpMat: new THREE.MeshStandardMaterial({ color: 0xc9d2d3, metalness: 0.85, roughness: 0.28, emissive: 0x80d9cd, emissiveIntensity: 0 }),
    };

    this.buildGround();
    this.buildWaterTable();
    this.buildEffects();

    try {
      this.composer = new EffectComposer(renderer);
      this.composer.addPass(new RenderPass(scene, camera));
      this.bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.8, 0.55, 0.74);
      this.composer.addPass(this.bloom);
      this.composer.addPass(new ShaderPass(GammaCorrectionShader));
      renderer.outputEncoding = THREE.LinearEncoding; // gamma is applied by the last pass
    } catch (e) {
      this.composer = null;
      this.bloom = null;
    }
    this.setLight(false);
  }

  // ---------- labels projected from 3D to DOM ----------
  addLabel(cls, text, pos) {
    const el = document.createElement('div');
    el.className = 'lbl ' + cls;
    el.textContent = text;
    this.labelsEl.appendChild(el);
    const o = { el, pos: new THREE.Vector3(pos[0], pos[1], pos[2]), near: 0 };
    this.labels.push(o);
    return o;
  }

  removeLabel(o) {
    o.el.remove();
    const i = this.labels.indexOf(o);
    if (i >= 0) this.labels.splice(i, 1);
  }

  // ---------- static scenery ----------
  buildGround() {
    const { scene } = this;
    LAYERS.forEach((ly, i) => {
      const h = (ly.b - ly.a) * K;
      const yc = (-(ly.a + ly.b) / 2) * K;
      const tex = rockTexture(ly.c, ly.v, i * 13 + 3);
      const t1 = tex.clone();
      t1.needsUpdate = true;
      t1.repeat.set(2, Math.max(0.2, h / 3));
      const back = new THREE.Mesh(new THREE.BoxGeometry(2 * L, h, L), new THREE.MeshStandardMaterial({ map: t1, roughness: 0.95 }));
      back.position.set(0, yc, -L / 2);
      scene.add(back);
      const t2 = tex.clone();
      t2.needsUpdate = true;
      t2.repeat.set(1, Math.max(0.2, h / 3));
      const side = new THREE.Mesh(new THREE.BoxGeometry(L, h, L), new THREE.MeshStandardMaterial({ map: t2, roughness: 0.95 }));
      side.position.set(-L / 2, yc, L / 2);
      scene.add(side);
      this.addLabel('layer l', ly.n, [-L, yc, L]);
    });

    const bp = [];
    LAYERS.forEach((ly) => {
      const y = -ly.b * K;
      bp.push(0, y, 0.005, L, y, 0.005, 0.005, y, 0, 0.005, y, L, -L, y, L + 0.005, 0, y, L + 0.005);
    });
    const bg = new THREE.BufferGeometry();
    bg.setAttribute('position', new THREE.Float32BufferAttribute(bp, 3));
    scene.add(new THREE.LineSegments(bg, new THREE.LineBasicMaterial({ color: 0x9fb8b3, transparent: true, opacity: 0.18 })));

    const gm = new THREE.MeshStandardMaterial({ color: 0x3e4f3b, roughness: 1 });
    const g1 = new THREE.Mesh(new THREE.PlaneGeometry(2 * L, L), gm);
    g1.rotation.x = -Math.PI / 2;
    g1.position.set(0, 0.003, -L / 2);
    scene.add(g1);
    const g2 = new THREE.Mesh(new THREE.PlaneGeometry(L, L), gm);
    g2.rotation.x = -Math.PI / 2;
    g2.position.set(-L / 2, 0.003, L / 2);
    scene.add(g2);

    // Housing society blocks with lit windows, overhead tank, trees, pump house.
    this.buildingMat = new THREE.MeshStandardMaterial({ color: 0xc6d1cd, roughness: 0.85, emissive: 0xf0c98e, emissiveMap: windowTexture(), emissiveIntensity: 0.55 });
    const bA = new THREE.Mesh(new THREE.BoxGeometry(1.9, 3.4, 1.7), this.buildingMat);
    bA.position.set(-4.3, 1.7, -4.1);
    scene.add(bA);
    const bB = new THREE.Mesh(new THREE.BoxGeometry(1.6, 2.5, 1.5), this.buildingMat);
    bB.position.set(-1.7, 1.25, -5.2);
    scene.add(bB);
    const tank = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.4, 24), new THREE.MeshStandardMaterial({ color: 0x6f9a95, roughness: 0.6 }));
    tank.position.set(-4.3, 3.6, -4.1);
    scene.add(tank);
    const r = mulberry32(31);
    const leaf = new THREE.MeshStandardMaterial({ color: 0x5c8a6c, roughness: 0.9 });
    const bark = new THREE.MeshStandardMaterial({ color: 0x5a4636 });
    [[-6, -1.5], [-5.6, 2.2], [-2.9, 5.8], [-6.2, 5.6], [2.5, -5.9], [5.6, -4.6], [-0.4, -3], [6, -1.6], [3.9, -2.6]].forEach(([x, z]) => {
      const s = 0.7 + r() * 0.6;
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 0.4 * s, 6), bark);
      trunk.position.set(x, 0.2 * s, z);
      scene.add(trunk);
      const crown = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42 * s, 0), leaf);
      crown.position.set(x, 0.55 * s + 0.2, z);
      crown.scale.y = 1.3;
      scene.add(crown);
    });
    const ph = new THREE.Mesh(new THREE.BoxGeometry(0.75, 0.45, 0.6), new THREE.MeshStandardMaterial({ color: 0x8a9e99, roughness: 0.8 }));
    ph.position.set(PUMP_HOUSE.x, 0.225, PUMP_HOUSE.z);
    scene.add(ph);

    // Depth ruler.
    const rp = [];
    for (let d = 0; d <= 150; d += 5) {
      const y = -d * K;
      rp.push(0.005, y, L, 0.005 + (d % 25 === 0 ? 0.22 : 0.1), y, L);
    }
    const rg = new THREE.BufferGeometry();
    rg.setAttribute('position', new THREE.Float32BufferAttribute(rp, 3));
    scene.add(new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: 0xd8e7e3, transparent: true, opacity: 0.45 })));
    for (let d = 0; d <= 150; d += 25) this.addLabel('tick r', d + ' m', [0.25, -d * K, L]);

    this.lWaterTable = this.addLabel('key r', '', [L, 0, 0.02]);
    this.lInWell = this.addLabel('key r', '', [WELL.x + 0.25, 0, WELL.z]);
    this.lIntake = this.addLabel('key warm r', '', [WELL.x + 0.2, -10.3, WELL.z]);
    this.lDevice = this.addLabel('key l', 'BoreWise unit', [WELL.x - 0.1, 0.35, WELL.z]);
  }

  buildWaterTable() {
    const { scene } = this;
    const sg = new THREE.PlaneGeometry(L - 0.02, L - 0.02, 40, 40);
    sg.rotateX(-Math.PI / 2);
    sg.translate(L / 2, 0, L / 2);
    this.surface = new THREE.Mesh(sg, new THREE.MeshStandardMaterial({ color: 0x6fd3c7, emissive: 0x174f4a, emissiveIntensity: 0.5, roughness: 0.2, metalness: 0.15, transparent: true, opacity: 0.42, side: THREE.DoubleSide, depthWrite: false }));
    scene.add(this.surface);

    // Saturated "curtains" on the two cut faces, with a bright line at the water table.
    const cm = new THREE.MeshBasicMaterial({ color: 0x6fd3c7, transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false });
    this.curtains = ['x', 'z'].map((ax) => {
      const N = 56;
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 6), 3));
      const idx = [];
      for (let i = 0; i < N - 1; i++) {
        const a = i * 2;
        idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
      }
      g.setIndex(idx);
      const m = new THREE.Mesh(g, cm);
      const lg = new THREE.BufferGeometry();
      lg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
      const line = new THREE.Line(lg, new THREE.LineBasicMaterial({ color: 0xa6f0e6, transparent: true, opacity: 0.9 }));
      m.userData = { ax, N, line };
      scene.add(m);
      scene.add(line);
      return m;
    });

    this.rings = [0, 1, 2].map(() => {
      const m = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.012, 8, 28), new THREE.MeshBasicMaterial({ color: 0x80d9cd, transparent: true, opacity: 0 }));
      m.rotation.x = Math.PI / 2;
      scene.add(m);
      return m;
    });

    const rn = 700;
    const rpos = new Float32Array(rn * 3);
    const rr = mulberry32(9);
    for (let i = 0; i < rn; i++) {
      rpos[i * 3] = (rr() * 2 - 1) * L;
      rpos[i * 3 + 1] = rr() * 7;
      rpos[i * 3 + 2] = (rr() * 2 - 1) * L;
    }
    const rgeo = new THREE.BufferGeometry();
    rgeo.setAttribute('position', new THREE.BufferAttribute(rpos, 3));
    this.rain = new THREE.Points(rgeo, new THREE.PointsMaterial({ color: 0xa9cbe0, size: 0.06, transparent: true, opacity: 0, depthWrite: false }));
    scene.add(this.rain);
  }

  buildEffects() {
    const { scene } = this;
    this.disc = new THREE.Mesh(new THREE.PlaneGeometry(36, 36), new THREE.MeshBasicMaterial({ map: glowTexture(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.disc.rotation.x = -Math.PI / 2;
    this.disc.position.y = -15.12;
    scene.add(this.disc);

    const rim = new THREE.BufferGeometry();
    rim.setAttribute('position', new THREE.Float32BufferAttribute([0, 0.01, 0, L, 0.01, 0, 0, 0.01, 0, 0, 0.01, L, 0, 0.01, L, 0, -15, L, L, 0.01, 0, L, -15, 0, 0, -15, 0, L, -15, 0, 0, -15, 0, 0, -15, L, 0, 0.01, 0, 0, -15, 0], 3));
    this.rim = new THREE.LineSegments(rim, new THREE.LineBasicMaterial({ color: 0x80d9cd, transparent: true, opacity: 0.6 }));
    scene.add(this.rim);

    const dot = dotTexture();
    const points = (n, color, size, opacity) => {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3).fill(-999), 3));
      const p = new THREE.Points(geo, new THREE.PointsMaterial({ color, size, map: dot, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending }));
      p.frustumCulled = false;
      scene.add(p);
      return p;
    };
    // Dust motes drifting up through the rock.
    this.motes = points(280, 0x9be6dc, 0.09, 0.6);
    const mr = mulberry32(21);
    const ma = this.motes.geometry.attributes.position.array;
    this.moteSeed = [];
    for (let i = 0; i < 280; i++) {
      ma[i * 3] = 0.2 + mr() * (L - 0.4);
      ma[i * 3 + 1] = -mr() * 15;
      ma[i * 3 + 2] = 0.2 + mr() * (L - 0.4);
      this.moteSeed.push(mr() * 6.28);
    }
    // Water flowing in along each water-bearing fracture, on both cut faces.
    this.inflow = points(240, 0x9ff7ec, 0.13, 1);
    this.inflowPh = Float32Array.from({ length: 240 }, () => Math.random());
    // Water lifted up the riser to the pump house.
    this.flow = points(80, 0xcffff8, 0.11, 1);
    this.flowPh = Float32Array.from({ length: 80 }, () => Math.random());
    // Bubbles rising in the bore while it refills.
    this.bubbles = points(70, 0xe0fffb, 0.07, 0.95);
    this.bubPh = Float32Array.from({ length: 70 }, () => Math.random());
    this.bubOff = Float32Array.from({ length: 140 }, () => Math.random() * 2 - 1);

    for (let i = 0; i < 5; i++) {
      const m = new THREE.Mesh(new THREE.RingGeometry(0.92, 1, 72), new THREE.MeshBasicMaterial({ color: 0x9ff7ec, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
      m.rotation.x = -Math.PI / 2;
      scene.add(m);
      this.shocks.push({ m, t0: -99, y: 0, warm: false });
    }
  }

  // ---------- per-scenario rebuild ----------
  rebuild(sc) {
    const { scene } = this;
    this.fracs.forEach((f) => {
      scene.remove(f.a, f.b);
      f.a.geometry.dispose();
      f.b.geometry.dispose();
      this.removeLabel(f.l);
    });
    this.fracs = [];
    sc.fr.forEach((f) => {
      const th = 0.03 + (f.T / 22) * 0.06;
      const mat = new THREE.MeshBasicMaterial({ color: 0x80d9cd, transparent: true, opacity: 0.9 });
      const a = new THREE.Mesh(new THREE.BoxGeometry(L, th, 0.02), mat);
      a.position.set(L / 2, -f.d * K, 0.012);
      const b = new THREE.Mesh(new THREE.BoxGeometry(0.02, th, L), mat);
      b.position.set(0.012, -f.d * K, L / 2);
      scene.add(a, b);
      this.fracs.push({ a, b, mat, d: f.d, l: this.addLabel('frac r', 'fracture ' + f.d + ' m', [L, -f.d * K, 0.02]) });
    });

    if (this.well) {
      scene.remove(this.well.group);
      disposeGroup(this.well.group);
    }
    this.wellLabels.forEach((o) => this.removeLabel(o));
    this.wellLabels = [];
    const addPart = (text, pos, side = 'r') => {
      const o = this.addLabel('part ' + side, text, pos);
      o.near = 7.5;
      this.wellLabels.push(o);
      return o;
    };
    this.well = buildWell(sc, this.mats, addPart);
    scene.add(this.well.group);
    this.lDevice.pos.set(this.well.tubeX - 0.12, this.well.devY + 0.3, this.well.tubeZ);
    this.lIntake.pos.set(WELL.x + sc.bore.r + 0.12, -sc.intake * K, WELL.z);
  }

  // ---------- theme ----------
  setLight(light) {
    this.light = light;
    const { scene } = this;
    if (scene.background && scene.background.dispose) scene.background.dispose();
    scene.background = gradientTexture(light ? SKY.light : SKY.dark);
    scene.fog.color.set(light ? 0xd9e8e4 : 0x0a1618);
    if (this.grid) {
      scene.remove(this.grid);
      this.grid.geometry.dispose();
    }
    this.grid = new THREE.GridHelper(44, 44, light ? 0x4a9a90 : 0x3a9990, light ? 0xa3c6bf : 0x15403c);
    this.grid.position.y = -15.05;
    this.grid.material.transparent = true;
    this.grid.material.opacity = 0.5;
    scene.add(this.grid);
    this.disc.material.opacity = light ? 0.22 : 1;
    if (this.bloom) this.bloom.threshold = light ? 0.95 : 0.74;
  }

  // ---------- camera ----------
  flyTo(pos, target, dur = 1.9, resumeOrbit = false) {
    this.controls.autoRotate = false;
    this.camTween = {
      p0: this.camera.position.clone(), q0: this.controls.target.clone(),
      p1: new THREE.Vector3(...pos), q1: new THREE.Vector3(...target),
      start: performance.now() / 1000, dur: this.reduce ? 0.01 : dur, resumeOrbit,
    };
  }

  goCam(name, sim, dur) {
    const [pos, target] = CAMERAS[name](sim);
    this.flyTo(pos, target, dur, name === 'overview');
  }

  camStep(time) {
    const tw = this.camTween;
    if (!tw) return;
    const u = Math.min(1, (time - tw.start) / tw.dur);
    const e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
    this.camera.position.lerpVectors(tw.p0, tw.p1, e);
    this.controls.target.lerpVectors(tw.q0, tw.q1, e);
    if (u >= 1) {
      if (tw.resumeOrbit) this.controls.autoRotate = !this.reduce && !this.userTouched;
      this.camTween = null;
    }
  }

  // ---------- effects triggers ----------
  shock(y, warm) {
    const s = this.shocks.reduce((a, b) => (a.t0 < b.t0 ? a : b));
    s.t0 = performance.now() / 1000;
    s.y = y;
    s.warm = !!warm;
  }

  startPing(sim) {
    this.pingVis = { t0: performance.now() / 1000, depth: sim.dl, dur: 0.7 + sim.dl / 80, hit: false };
    this.shock(0.03, true);
  }

  // ---------- per-frame update ----------
  levelAt(sim, rMetres) {
    const rw = sim.sc.rw || 0.075;
    const sw = Math.max(0, sim.dl - sim.swl);
    if (rMetres <= rw) return sim.swl + sw;
    return sim.swl + sw * Math.max(0, Math.log(RADIUS_OF_INFLUENCE / rMetres) / Math.log(RADIUS_OF_INFLUENCE / rw));
  }

  frame(time, dt, sim, { playing, speed, severity }) {
    const sc = sim.sc;
    if (this.lastSc !== sc) {
      this.rebuild(sc);
      this.lastSc = sc;
    }
    this.frameN++;
    const w = this.well;
    const reduce = this.reduce;

    // Water column inside the bore.
    const top = -sim.dl * K;
    const bot = -sc.depth * K;
    w.wcol.scale.y = Math.max(0.01, top - bot);
    w.wcol.position.y = (top + bot) / 2;
    this.mats.wmat.emissiveIntensity = sim.pumpOn ? 0.75 + 0.15 * Math.sin(time * 6) : 0.55;
    this.wellLight.position.set(WELL.x + 0.6, top + 0.5, WELL.z + 0.6);

    // Water table surface and cut-face curtains follow the cone of depression.
    const pos = this.surface.geometry.attributes.position;
    const arr = pos.array;
    for (let i = 0; i < pos.count; i++) {
      const x = arr[i * 3];
      const z = arr[i * 3 + 2];
      const r = Math.hypot(x - WELL.x, z - WELL.z) * 10;
      arr[i * 3 + 1] = -this.levelAt(sim, r) * K + (reduce ? 0 : Math.sin(x * 3 + time * 1.3) * Math.cos(z * 2.6 + time) * 0.008);
    }
    pos.needsUpdate = true;
    if (this.frameN % 6 === 0) this.surface.geometry.computeVertexNormals();
    for (const m of this.curtains) {
      const { ax, N, line } = m.userData;
      const p = m.geometry.attributes.position.array;
      const lp = line.geometry.attributes.position.array;
      for (let i = 0; i < N; i++) {
        const u = (i / (N - 1)) * L;
        const x = ax === 'x' ? u : 0.016;
        const z = ax === 'x' ? 0.016 : u;
        const y = -this.levelAt(sim, Math.hypot(x - WELL.x, z - WELL.z) * 10) * K;
        p[i * 6] = x; p[i * 6 + 1] = y; p[i * 6 + 2] = z;
        p[i * 6 + 3] = x; p[i * 6 + 4] = -15; p[i * 6 + 5] = z;
        lp[i * 3] = x; lp[i * 3 + 1] = y + 0.004; lp[i * 3 + 2] = z;
      }
      m.geometry.attributes.position.needsUpdate = true;
      line.geometry.attributes.position.needsUpdate = true;
      m.geometry.computeBoundingSphere();
      line.geometry.computeBoundingSphere();
    }

    for (const f of this.fracs) {
      const wet = f.d > sim.swl;
      f.mat.color.set(wet ? 0x80d9cd : 0x4a5b5d);
      f.mat.opacity = wet ? 0.85 : 0.6;
      f.l.el.classList.toggle('wet', wet);
      f.l.el.textContent = 'fracture ' + f.d + ' m · ' + (wet ? 'water-bearing' : 'dewatered');
    }

    // Pump glow, hand-pump stroke, starter lamps, dug-well water.
    this.mats.pumpMat.emissiveIntensity = sim.pumpOn ? (sim.dryRun ? 0.6 + 0.4 * Math.sin(time * 18) : 0.55 + 0.2 * Math.sin(time * 5)) : 0;
    this.mats.pumpMat.emissive.set(sim.dryRun ? 0xef8e82 : 0x80d9cd);
    this.mats.riserMat.emissiveIntensity = sim.pumpOn ? 0.25 : 0;
    if (w.handle) {
      const a = sim.pumpOn && !reduce ? Math.sin(time * 6) : 0;
      w.handle.rotation.z = a * 0.32;
      w.rod.position.y = w.rodY - a * 0.035;
    }
    if (w.lampG) {
      w.lampG.material.color.set(sim.pumpOn ? 0x6bff8a : 0x1c3a24);
      w.lampR.material.color.set(sim.dryRun || (sim.emergency && sim.t - sim.emergency.t < 2) ? 0xff5a4a : 0x3a1c1c);
    }
    if (w.dugWater && sc.dug) {
      const dd = sc.dug.d;
      w.dugWater.visible = sim.dl < dd - 0.05;
      if (w.dugWater.visible) {
        w.dugWater.scale.y = (dd - sim.dl) * K;
        w.dugWater.position.y = (-(sim.dl + dd) / 2) * K;
      }
    }

    this.lWaterTable.pos.set(L, -sim.swl * K, 0.02);
    this.lWaterTable.el.textContent = 'water table ' + sim.swl.toFixed(1) + ' m';
    this.lInWell.pos.set(WELL.x + 0.25, -sim.dl * K, WELL.z);
    this.lInWell.el.textContent = 'in well ' + sim.dl.toFixed(1) + ' m';
    this.lIntake.el.textContent = 'pump intake ' + sc.intake + ' m';

    // Rain on rainy days.
    const rainToday = sim.rain[Math.floor(sim.t / 24)] || 0;
    const ro = rainToday > 0.5 && playing ? Math.min(0.75, 0.25 + rainToday / 40) : 0;
    this.rain.material.opacity += (ro - this.rain.material.opacity) * 0.08;
    if (this.rain.material.opacity > 0.01 && !reduce) {
      const rp = this.rain.geometry.attributes.position.array;
      for (let i = 1; i < rp.length; i += 3) {
        rp[i] -= dt * 6;
        if (rp[i] < 0) rp[i] += 7;
      }
      this.rain.geometry.attributes.position.needsUpdate = true;
    }

    this.updatePing(time);
    this.updateParticles(time, dt, sim);
    this.updateMood(time, dt, sim, speed, severity);
    this.camStep(time);
    this.controls.update();
    if (this.composer) this.composer.render();
    else this.renderer.render(this.scene, this.camera);
    this.projectLabels();
  }

  updatePing(time) {
    const pv = this.pingVis;
    const w = this.well;
    if (!pv) {
      this.rings.forEach((m) => (m.material.opacity = 0));
      return;
    }
    const e = time - pv.t0;
    this.rings.forEach((m, i) => {
      const ee = e - i * 0.12;
      let y = 0;
      let op = 0;
      let col = 0x80d9cd;
      if (ee > 0 && ee < pv.dur) { y = (-ee / pv.dur) * pv.depth * K; op = 0.9; }
      else if (ee >= pv.dur && ee < 2 * pv.dur) { y = -(1 - (ee - pv.dur) / pv.dur) * pv.depth * K; op = 0.75; col = 0xdcaa7e; }
      m.position.set(w.tubeX, y, w.tubeZ);
      m.material.opacity = op * (1 - i * 0.25);
      m.material.color.set(col);
      const s = 1 + 0.3 * Math.sin(ee * 20);
      m.scale.set(s, s, s);
    });
    if (!pv.hit && e >= pv.dur) {
      pv.hit = true;
      this.shock(-pv.depth * K + 0.02, false);
    }
    w.led.material.color.set(e < 2 * pv.dur + 0.3 ? (Math.floor(e * 8) % 2 ? 0xdcaa7e : 0x80d9cd) : 0x80d9cd);
    if (e > 2 * pv.dur + 0.6) this.pingVis = null;
  }

  updateParticles(time, dt, sim) {
    const sc = sim.sc;
    const reduce = this.reduce;
    const w = this.well;
    const ma = this.motes.geometry.attributes.position.array;
    if (!reduce) {
      for (let i = 0; i < 280; i++) {
        ma[i * 3 + 1] += dt * 0.09;
        if (ma[i * 3 + 1] > -0.1) ma[i * 3 + 1] = -15;
        ma[i * 3] += Math.sin(time * 0.4 + this.moteSeed[i]) * dt * 0.04;
      }
      this.motes.geometry.attributes.position.needsUpdate = true;
    }

    const refilling = sim.lastOff != null && sim.t - sim.lastOff < 2;
    const spd = sim.pumpOn ? 0.6 : refilling ? 0.28 : 0.07;
    const ia = this.inflow.geometry.attributes.position.array;
    for (let fi = 0; fi < 4; fi++) {
      const f = sc.fr[fi];
      const wet = f && f.d > sim.swl;
      for (let side = 0; side < 2; side++) {
        for (let j = 0; j < 30; j++) {
          const idx = (fi * 2 + side) * 30 + j;
          let ph = this.inflowPh[idx];
          if (!reduce) {
            ph -= dt * spd * (0.55 + (j % 5) * 0.12);
            if (ph < 0) ph += 1;
            this.inflowPh[idx] = ph;
          }
          const y = wet ? -f.d * K + Math.sin(ph * 24 + j) * 0.025 : -999;
          const u = ph * (L - 0.5);
          if (side === 0) { ia[idx * 3] = WELL.x + u; ia[idx * 3 + 1] = y; ia[idx * 3 + 2] = 0.05; }
          else { ia[idx * 3] = 0.05; ia[idx * 3 + 1] = y; ia[idx * 3 + 2] = WELL.z + u; }
        }
      }
    }
    this.inflow.geometry.attributes.position.needsUpdate = true;
    this.inflow.material.opacity = 0.35 + spd;

    const fa = this.flow.geometry.attributes.position.array;
    for (let i = 0; i < 80; i++) {
      let ph = this.flowPh[i];
      if (!reduce && sim.pumpOn) {
        ph += dt * 0.55;
        if (ph > 1) ph -= 1;
        this.flowPh[i] = ph;
      }
      const q = sim.pumpOn && w.flowPath ? w.flowPath(ph, i) : [0, -999, 0];
      fa[i * 3] = q[0]; fa[i * 3 + 1] = q[1]; fa[i * 3 + 2] = q[2];
    }
    this.flow.geometry.attributes.position.needsUpdate = true;

    const ba = this.bubbles.geometry.attributes.position.array;
    const top = -sim.dl * K;
    const bot = Math.max(-sc.intake * K - 0.4, -sc.depth * K);
    const on = !sim.pumpOn && refilling;
    for (let i = 0; i < 70; i++) {
      let ph = this.bubPh[i];
      if (!reduce) {
        ph += dt * (0.25 + (i % 7) * 0.05);
        if (ph > 1) ph -= 1;
        this.bubPh[i] = ph;
      }
      if (!on || top <= bot) { ba[i * 3 + 1] = -999; continue; }
      ba[i * 3] = WELL.x + this.bubOff[i * 2] * 0.12 + Math.sin(time * 3 + i) * 0.01;
      ba[i * 3 + 1] = bot + ph * (top - bot);
      ba[i * 3 + 2] = WELL.z + this.bubOff[i * 2 + 1] * 0.12;
    }
    this.bubbles.geometry.attributes.position.needsUpdate = true;

    for (const o of this.shocks) {
      const e = time - o.t0;
      if (e < 1.8) {
        const r = 0.25 + e * (o.warm ? 3.2 : 2.6);
        o.m.scale.set(r, r, r);
        o.m.position.set(WELL.x, o.y, WELL.z);
        o.m.material.opacity = Math.pow(1 - e / 1.8, 1.6) * 0.9;
        o.m.material.color.set(o.warm ? 0xdcaa7e : 0x9ff7ec);
      } else o.m.material.opacity = 0;
    }
  }

  updateMood(time, dt, sim, speed, severity) {
    const crit = severity === 'crit';
    this.rim.material.color.set(crit ? 0xef8e82 : 0x80d9cd);
    this.rim.material.opacity = 0.4 + 0.25 * Math.sin(time * (crit ? 6 : 1.6));
    this.grid.material.opacity = 0.38 + 0.12 * Math.sin(time * 0.8);
    // Day and night at slow speeds; fixed daylight when fast-forwarding.
    let day = clamp(Math.sin((((sim.t % 24) - 6) / 12) * Math.PI), 0, 1);
    if (speed > 6) day = 0.6;
    this.dayF += (day - this.dayF) * Math.min(1, dt * 2);
    this.hemi.intensity = 0.38 + 0.55 * this.dayF + (this.light ? 0.35 : 0);
    this.sun.intensity = 0.25 + 0.7 * this.dayF;
    this.buildingMat.emissiveIntensity = 1.25 - 0.85 * this.dayF;
    if (this.bloom) {
      const target = ((crit ? 1.15 : 0.8) + (1 - this.dayF) * 0.2 + (this.pingVis ? 0.12 : 0)) * (this.light ? 0.35 : 1);
      this.bloom.strength += (target - this.bloom.strength) * Math.min(1, dt * 3);
    }
  }

  projectLabels() {
    const { w, h } = this.size;
    const v = this.tmp;
    for (const o of this.labels) {
      if (o.near && this.camera.position.distanceTo(o.pos) > o.near) { o.el.style.display = 'none'; continue; }
      v.copy(o.pos).project(this.camera);
      if (v.z > 1 || Math.abs(v.x) > 1.2 || Math.abs(v.y) > 1.2) { o.el.style.display = 'none'; continue; }
      o.el.style.display = '';
      o.el.style.left = (((v.x + 1) / 2) * w).toFixed(1) + 'px';
      o.el.style.top = (((1 - v.y) / 2) * h).toFixed(1) + 'px';
    }
  }

  resize(w, h) {
    this.size = { w, h };
    this.renderer.setSize(w, h, false);
    if (this.composer) {
      this.composer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      this.composer.setSize(w, h);
    }
    this.camera.aspect = w / h;
    this.camera.fov = w < 600 ? 48 : 36;
    this.camera.updateProjectionMatrix();
  }

  dispose() {
    this.controls.dispose();
    this.labels.forEach((o) => o.el.remove());
    this.scene.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
    });
    if (this.composer) this.composer.dispose?.();
    this.renderer.dispose();
  }
}
