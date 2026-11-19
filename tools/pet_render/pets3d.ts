// NetPet 3D 宠物：全部用 three.js 基础几何体程序化搭建，不依赖任何模型文件。
import * as THREE from 'three';
import { PETS as LIST } from './petlist';

const INK = '#3A2F3A', PINK = '#FF9DB0';
const mat = (c: string, o?: any) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.55, metalness: 0, ...(o || {}) });
const S = (r: number, c: any, x = 1, y = 1, z = 1, o?: any) => { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 28, 20), typeof c === 'string' ? mat(c, o) : c); m.scale.set(x, y, z); return m; };
const C = (r, h, c) => new THREE.Mesh(new THREE.ConeGeometry(r, h, 20), mat(c));
const Y = (r1, r2, h, c) => new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, 20), mat(c));
const P = (o, x, y, z, rx = 0, ry = 0, rz = 0) => { o.position.set(x, y, z); o.rotation.set(rx, ry, rz); return o; };

const SPEC = {
  cat: { body: '#FFC48F', belly: '#FFF1E3', ear: 'point', inner: PINK, snout: 'muzzle', snoutC: '#FFF1E3', nose: '#FF7F9A', tail: 'cat' },
  dog: { body: '#E6BE8A', belly: '#FFF1DD', ear: 'floppy', earC: '#A56F44', snout: 'muzzle', snoutC: '#FFF1DD', nose: INK, tail: 'short', patch: '#A56F44' },
  bunny: { body: '#FFF4EE', belly: '#FFE4EC', ear: 'long', inner: PINK, snout: 'muzzle', snoutC: '#FFFFFF', nose: PINK, tail: 'short', tailC: '#FFFFFF' },
  bear: { body: '#B47C52', belly: '#E9CBA7', ear: 'round', inner: '#E9CBA7', snout: 'muzzle', snoutC: '#E9CBA7', nose: INK, tail: 'short' },
  panda: { body: '#FDFDFD', ear: 'round', earC: '#2D2A32', inner: '#2D2A32', snout: 'muzzle', snoutC: '#FDFDFD', nose: '#2D2A32', tail: 'short', tailC: '#FDFDFD', armC: '#2D2A32', feet: '#2D2A32', patch: '#2D2A32', patchBoth: 1, cheek: 0 },
  fox: { body: '#FF9A4D', belly: '#FFF4E8', ear: 'point', inner: '#4A3030', snout: 'muzzle', snoutC: '#FFF4E8', nose: '#2E2530', tail: 'fluffy', tailC: '#FF8A3A', tipC: '#FFFFFF', feet: '#5A3A2E' },
  tiger: { body: '#FFC857', belly: '#FFF4DD', ear: 'round', inner: '#FFF4DD', snout: 'muzzle', snoutC: '#FFF4DD', nose: '#FF7F9A', tail: 'cat', stripes: '#8A4B1F' },
  pig: { body: '#FFB3C6', belly: '#FFD2DE', ear: 'point', earTilt: 0.9, inner: '#FF8FAE', snout: 'pig', tail: 'curl', feet: '#FF9DB5' },
  hamster: { body: '#F4C58A', belly: '#FFF4E6', ear: 'round', inner: PINK, snout: 'muzzle', snoutC: '#FFF4E6', nose: PINK, tail: 'none', bigCheek: '#FFE2BE', feet: '#FFB7C5', cheek: 0 },
  chick: { body: '#FFE066', snout: 'beak', beakC: '#FF9F43', tail: 'none', tuft: '#FFE066', feet: '#FF9F43', eyeY: 0.16, flipper: 1 },
  duck: { body: '#FFF0A8', snout: 'duck', tail: 'short', tailC: '#FFF0A8', feet: '#FFA63D', eyeY: 0.18, flipper: 1 },
  penguin: { body: '#40507A', belly: '#FFFFFF', bellyBig: 1, faceC: '#FFFFFF', snout: 'beak', beakC: '#FF9F43', tail: 'none', feet: '#FF9F43', eyeY: 0.14, flipper: 1, cheek: 0 },
  frog: { body: '#7ED67B', belly: '#E7F9C9', frog: 1, snout: 'none', tail: 'none', feet: '#6CC56A', wideMouth: 1 },
  dino: { body: '#7BD389', belly: '#FFF0B8', snout: 'muzzle', snoutC: '#9BE3A4', nose: '#4C8F5A', tail: 'dino', spikes: '#FFB347' },
  unicorn: { body: '#FFF6FB', belly: '#FFE3F0', ear: 'point', inner: PINK, snout: 'muzzle', snoutC: '#FFE3F0', nose: PINK, tail: 'fluffy', tailC: '#E8A6FF', horn: '#FFD36B', mane: ['#FFA6D5', '#B8A1FF', '#8FD9F0'] },
  slime: { body: '#7FE0A8', bodyO: { transparent: true, opacity: 0.88, roughness: 0.15 }, slime: 1, noFeet: 1, noArms: 1, snout: 'none', tail: 'none', eyeS: 1.25, eyeY: 0.05, dim: [1.04, 0.72, 0.95] },
  ghost: { body: '#FFFFFF', bodyO: { transparent: true, opacity: 0.93 }, ghost: 1, noFeet: 1, snout: 'none', tail: 'none', eyeS: 1.2, hem: 1 },
  robot: { body: '#B9C7E0', snout: 'none', tail: 'none', screen: '#2B3544', glow: 1, eyeC: '#5CF2FF', eyeX: 0.26, mouthC: '#5CF2FF', armC: '#7B8AA8', feet: '#7B8AA8', antenna: '#FF6B6B', bolts: '#7B8AA8', cheek: 0 }
};

function build(id) {
  const s = SPEC[id] || SPEC.cat;
  const dim = s.dim || [0.95, 0.874, 0.9025];
  const surf = (x, y) => dim[2] * Math.sqrt(Math.max(0.05, 1 - (x / dim[0]) ** 2 - (y / dim[1]) ** 2));
  const root = new THREE.Group(), core = new THREE.Group();
  const baseY = s.slime ? 0.8 : 0.98;
  core.position.y = baseY; core.userData.y = baseY; root.add(core);
  const A: any = { ears: [], arms: [], eyes: [] };
  const bodyMat = mat(s.body, s.bodyO);
  core.add(S(1, bodyMat, dim[0], dim[1], dim[2]));

  // 肚皮 / 脸部色块
  if (s.belly) core.add(P(S(s.bellyBig ? 0.68 : 0.5, s.belly, 1, s.bellyBig ? 1.1 : 1.0, 0.55), 0, s.bellyBig ? -0.28 : -0.52, dim[2] * 0.69));
  if (s.faceC) core.add(P(S(0.58, s.faceC, 1, 0.78, 0.42), 0, 0.12, surf(0, 0.12) - 0.17));
  if (s.screen) core.add(P(S(0.62, s.screen, 1, 0.62, 0.38), 0, 0.13, surf(0, 0.13) - 0.16));

  // 脚和手
  if (!s.noFeet) for (const d of [-1, 1]) root.add(P(S(0.2, s.feet || s.body, 1.1, 0.6, 1.3), d * 0.38, 0.1, 0.3));
  if (!s.noArms) for (const d of [-1, 1]) {
    const a = s.flipper ? S(0.13, s.armC || s.body, 0.55, 1.7, 1) : S(0.17, s.armC || s.body, 0.8, 1.25, 0.8);
    P(a, d * dim[0] * 0.95, -0.05, 0.08, 0, 0, d * 0.45); a.userData = { rz: d * 0.45, d }; A.arms.push(a); core.add(a);
  }

  // 眼睛
  const ink = s.eyeC || INK;
  const eyeMat = s.glow ? mat(ink, { emissive: ink, emissiveIntensity: 0.9 }) : mat(ink, { roughness: 0.3 });
  const eyeX = s.eyeX || 0.33, eyeY = s.eyeY ?? 0.12;
  for (const d of [-1, 1]) {
    const g = new THREE.Group();
    if (s.frog) {
      g.add(S(0.2, '#FFFFFF')); g.add(P(S(0.1, eyeMat), 0, 0, 0.17));
      g.position.set(d * 0.45, 0.74, 0.32);
    } else {
      const ez = (s.screen || s.faceC) ? surf(0, 0.13) + 0.065 : surf(eyeX, eyeY) + ((s.patch) ? 0.04 : -0.02);
      g.add(S(0.095, eyeMat, 1, 1.15, 0.7)); g.add(P(S(0.042, '#FFFFFF'), 0.03, 0.045, 0.06));
      g.position.set(d * eyeX, eyeY, ez);
    }
    g.scale.setScalar(s.eyeS || 1); g.userData.base = s.eyeS || 1;
    core.add(g); A.eyes.push(g);
  }
  if (s.patch) for (const d of s.patchBoth ? [-1, 1] : [1])
    core.add(P(S(0.17, s.patch, 1, 1.3, 0.5), d * 0.34, 0.12, surf(0.34, 0.12) - 0.02, 0, 0, d * 0.4));

  // 嘴巴 / 鼻子
  let mouthY = -0.12, mouthZ = surf(0, -0.12) + 0.0;
  if (s.snout === 'muzzle') {
    const z0 = surf(0, -0.14);
    core.add(P(S(0.27, s.snoutC, 1, 0.78, 0.62), 0, -0.14, z0 - 0.03));
    core.add(P(S(0.055, s.nose || INK, 1.3, 0.9, 0.9), 0, -0.045, z0 + 0.115));
    mouthY = -0.2; mouthZ = z0 + 0.13;
  } else if (s.snout === 'beak') {
    core.add(P(C(0.12, 0.28, s.beakC), 0, -0.06, surf(0, -0.06) + 0.08, Math.PI / 2));
    mouthY = null;
  } else if (s.snout === 'duck') {
    core.add(P(S(0.22, '#FFA63D', 1.25, 0.42, 0.95), 0, -0.1, surf(0, -0.1) + 0.07)); mouthY = null;
  } else if (s.snout === 'pig') {
    const z0 = surf(0, -0.1);
    core.add(P(Y(0.22, 0.22, 0.16, '#FF9FB5'), 0, -0.1, z0 + 0.03, Math.PI / 2));
    for (const d of [-1, 1]) core.add(P(S(0.035, '#C04E6C'), d * 0.08, -0.1, z0 + 0.115));
    mouthY = -0.34; mouthZ = surf(0, -0.34) - 0.0;
  } else if (s.screen) { mouthY = -0.14; mouthZ = surf(0, 0) + 0.03; }
  if (mouthY !== null) {
    const m = new THREE.Mesh(new THREE.TorusGeometry(0.075, 0.022, 8, 20, Math.PI), mat(s.mouthC || INK));
    P(m, 0, mouthY, mouthZ, 0, 0, Math.PI);
    if (s.wideMouth) { m.position.set(0, -0.14, surf(0, -0.14) + 0.01); }
    m.userData.bx = s.wideMouth ? 2.3 : 1; m.scale.x = m.userData.bx; core.add(m); A.mouth = m;
  }
  if (s.cheek !== 0) for (const d of [-1, 1])
    core.add(P(S(0.1, PINK, 1, 0.7, 0.35, { transparent: true, opacity: 0.75 }), d * 0.6, -0.12, surf(0.6, -0.12) - 0.03, 0, d * 0.75, 0));
  if (s.bigCheek) for (const d of [-1, 1]) core.add(P(S(0.3, s.bigCheek, 1, 0.9, 0.8), d * 0.58, -0.16, surf(0.58, -0.16) - 0.1));
  if (s.stripes) {
    for (const i of [-1, 0, 1]) core.add(P(S(0.045, s.stripes, 1, 3.6, 0.45), i * 0.2, 0.66, surf(i * 0.2, 0.66), -0.6, 0, -i * 0.15));
    for (const d of [-1, 1]) for (const y of [-0.02, -0.14]) core.add(P(S(0.035, s.stripes, 4, 1, 0.4), d * 0.8, y, surf(0.8, y) - 0.04, 0, d * 1.0, 0));
  }

  // 耳朵
  if (s.ear) for (const d of [-1, 1]) {
    const ec = s.earC || s.body, g = new THREE.Group();
    if (s.ear === 'point') {
      const rz = -d * (s.earTilt || 0.45);
      const o = C(0.3, 0.5, ec); o.scale.z = 0.6; const i = C(0.17, 0.32, s.inner); i.scale.z = 0.45;
      g.add(P(o, 0, 0, 0, 0, 0, 0), P(i, 0, -0.03, 0.15, 0, 0, 0)); g.position.set(d * 0.52, 0.76, -0.02); g.rotation.z = rz; g.userData.rz = rz;
      if (s.earTilt) g.rotation.x = 0.5;
    } else if (s.ear === 'round') {
      g.add(S(0.26, ec), P(S(0.15, s.inner || ec, 1, 1, 0.5), 0, 0, 0.2)); g.position.set(d * 0.64, 0.64, -0.04); g.userData.rz = 0;
    } else if (s.ear === 'long') {
      const rz = -d * 0.2;
      g.add(S(0.17, ec, 1, 2.3, 0.5), P(S(0.1, s.inner, 1, 2.2, 0.35), 0, 0, 0.08)); g.position.set(d * 0.34, 1.05, -0.05); g.rotation.z = rz; g.userData.rz = rz;
    } else if (s.ear === 'floppy') {
      const rz = -d * 0.35;
      g.add(S(0.22, ec, 0.7, 1.6, 0.5)); g.position.set(d * 0.84, 0.35, -0.02); g.rotation.z = rz; g.userData.rz = rz;
    }
    g.userData.d = d; core.add(g); A.ears.push(g);
  }

  // 尾巴
  if (s.tail && s.tail !== 'none') {
    const t = new THREE.Group(); t.position.set(0, -0.45, -0.8); t.userData.rz = 0;
    if (s.tail === 'cat') { t.add(P(new THREE.Mesh(new THREE.CapsuleGeometry(0.09, 0.55, 6, 12), mat(s.body)), 0, 0.38, 0)); t.rotation.set(-0.5, 0, 0.3); t.userData.rz = 0.3; }
    else if (s.tail === 'fluffy') {
      t.add(P(S(0.32, s.tailC || s.body, 0.85, 1.5, 0.85), 0, 0.5, 0)); if (s.tipC) t.add(P(S(0.21, s.tipC), 0, 0.88, 0));
      t.rotation.set(-0.7, 0, 0.1); t.userData.rz = 0.1;
    } else if (s.tail === 'short') t.add(P(S(0.2, s.tailC || s.body), 0, 0, -0.05));
    else if (s.tail === 'curl') t.add(P(new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.035, 8, 16, Math.PI * 1.6), mat('#FF9DB5')), 0, 0, -0.1, 0, Math.PI / 2, 0));
    else if (s.tail === 'dino') { t.add(P(C(0.26, 0.8, s.body), 0, 0, -0.35, -Math.PI / 2)); t.position.set(0, -0.5, -0.75); t.userData.ax = 'y'; }
    core.add(t); A.tail = t;
  }

  // 其他装饰
  if (s.tuft) for (const i of [-1, 0, 1]) core.add(P(C(0.06, 0.3, s.tuft), i * 0.1, 0.93, 0.05, 0, 0, -i * 0.4));
  if (s.spikes) [[0.88, 0.15, -0.3], [0.6, -0.55, -0.9], [0.15, -0.88, -1.3]].forEach(([y, z, rx]) => core.add(P(C(0.13, 0.3, s.spikes), 0, y, z, rx)));
  if (s.horn) core.add(P(C(0.1, 0.55, s.horn), 0, 1.02, 0.42, 0.4));
  if (s.mane) s.mane.forEach((c, i) => core.add(P(S(0.2, c), -0.5 - i * 0.08, 0.7 - i * 0.28, -0.2)));
  if (s.antenna) {
    const g = new THREE.Group(); g.add(P(Y(0.025, 0.025, 0.4, '#6B7A99'), 0, 0.2, 0), P(S(0.08, s.antenna, 1, 1, 1, { emissive: s.antenna, emissiveIntensity: 0.6 }), 0, 0.43, 0));
    g.position.set(0, 0.86, 0); core.add(g); A.ant = g;
  }
  if (s.bolts) for (const d of [-1, 1]) core.add(P(Y(0.1, 0.1, 0.18, s.bolts), d * 1.0, 0.05, 0, 0, 0, Math.PI / 2));
  if (s.hem) for (let i = 0; i < 7; i++) { const a = i / 7 * Math.PI * 2; core.add(P(S(0.21, bodyMat), Math.cos(a) * 0.68, -0.76, Math.sin(a) * 0.62)); }
  if (s.slime) {
    core.add(P(S(0.13, '#FFFFFF', 1, 0.6, 0.4, { transparent: true, opacity: 0.7 }), -0.45, 0.42, surf(-0.45, 0.42) - 0.03));
    core.add(P(C(0.2, 0.42, s.body), 0, 0.82, 0.0, 0.2));
  }
  return { root, core, A, tail: A.tail, ant: A.ant, dimY: dim[1], float: !!s.ghost, wobble: !!s.slime };
}

const symTex = (ch: string, color: string) => {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d'); x.font = 'bold 48px sans-serif'; x.fillStyle = color; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(ch, 32, 34);
  return new THREE.CanvasTexture(c);
};
const zTex = () => symTex('z', '#8E76E8');
const mkSprite = (ch: string, color: string) => new THREE.Sprite(new THREE.SpriteMaterial({ map: symTex(ch, color), transparent: true, depthTest: false }));

// 场景 + 动画（不依赖 WebGL，方便测试）
export class PetScene {
  scene: any; state: any; eye: number; top: number; right: number; sweat: any; sign: any; zzz: any[]; fx: any[]; symThink: any; symAlert: any; p: any; id: string; frame: any;
  constructor() {
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight('#FFFFFF', '#FFD9C8', 1.5));
    const dl = new THREE.DirectionalLight('#FFFFFF', 2.0); dl.position.set(2, 4, 5); this.scene.add(dl);
    this.state = { mood: 'idle', hot: false, risk: false };
    this.eye = 1; this.top = 2; this.right = 1;
    const fm = (c) => mat(c, { emissive: c, emissiveIntensity: 0.4 });
    this.sweat = new THREE.Group(); this.sweat.add(S(0.1, fm('#7CC8FF'), 0.8, 1.2, 0.6), P(new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.16, 12), fm('#7CC8FF')), 0, 0.15, 0));
    this.sign = new THREE.Group();
    const tri = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.07, 3), fm('#FFC857')); tri.rotation.x = -Math.PI / 2;
    this.sign.add(tri, P(new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.17, 0.03), mat(INK)), 0, 0.03, 0.05), P(S(0.04, INK), 0, -0.12, 0.05));
    this.zzz = [];
    if (typeof document !== 'undefined') for (let i = 0; i < 2; i++) {
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: zTex(), transparent: true, depthTest: false })); this.zzz.push(sp); this.scene.add(sp);
    }
    this.fx = [this.sweat, this.sign]; this.fx.forEach((o) => this.scene.add(o));
    this.symThink = mkSprite('?', '#8E76E8'); this.symAlert = mkSprite('!', '#FF8A3D'); this.scene.add(this.symThink, this.symAlert);
  }
  setPet(id) {
    if (this.p) { this.scene.remove(this.p.root); this.p.root.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
    this.id = id; this.p = build(id); this.scene.add(this.p.root); this.p.root.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(this.p.root);
    this.frame = { cy: (b.max.y + b.min.y) / 2, h: b.max.y - b.min.y, w: b.max.x - b.min.x };
    this.top = b.max.y; this.right = b.max.x;
  }
  setState(mood, hot, risk) { this.state = { mood, hot: !!hot, risk: !!risk }; }
  update(t, dt) {
    const p = this.p; if (!p) return;
    const { mood, hot, risk } = this.state, A = p.A, core = p.core;
    let hopH = 0, hopSpd = 0, breathe = 0.025, eyeT = 1, wag = 1.6, wagA = 0.22, look = 0.25, mouthS = 1;
    if (mood === 'sleep') { eyeT = 0.08; wagA = 0; look = 0; breathe = 0.03; }
    else if (mood === 'happy') { hopSpd = 3.2; hopH = 0.16; eyeT = 0.45; wag = 7; wagA = 0.45; mouthS = 1.35; look = 0; }
    else if (mood === 'rush') { hopSpd = 7; hopH = 0.28; eyeT = 0.4; wag = 14; wagA = 0.6; mouthS = 1.5; look = 0; }
    else if (mood === 'tired') { eyeT = 0.5; wag = 0.8; wagA = 0.06; look = 0; breathe = 0.04; }
    else if (mood === 'think') { eyeT = 0.75; wag = 2; wagA = 0.1; look = 0; breathe = 0.02; }
    else if (mood === 'sad') { eyeT = 0.5; wag = 1; wagA = 0; look = 0; breathe = 0.03; }
    else if (mood === 'alert') { eyeT = 1.25; wag = 9; wagA = 0.3; look = 0; breathe = 0.01; }
    else if ((t % 3.6) > 3.45) eyeT = 0.1;
    this.eye += (eyeT - this.eye) * Math.min(1, dt * 14);
    for (const e of A.eyes) e.scale.y = e.userData.base * Math.max(0.06, this.eye);
    const ph = t * hopSpd, h = hopSpd ? Math.abs(Math.sin(ph)) : 0;
    let sy = hopSpd ? 0.93 + 0.12 * h : 1 + Math.sin(t * (mood === 'sleep' ? 1.4 : 2.2)) * breathe;
    if (mood === 'alert') sy *= 1.06;
    let sx = 1 / Math.sqrt(sy);
    if (p.wobble) { const w = Math.sin(t * 5) * 0.05; sx *= 1 + w; sy *= 1 - w; }
    core.scale.set(sx, sy, sx);
    core.position.y = core.userData.y + p.dimY * (sy - 1);
    const lift = h * hopH + (p.float ? 0.12 + Math.sin(t * 2) * 0.07 : 0);
    p.root.position.y = lift;
    core.rotation.y = look ? Math.sin(t * 0.6) * look : core.rotation.y * 0.9;
    core.rotation.z = risk ? Math.sin(t * 28) * 0.06 : mood === 'sleep' ? 0 : mood === 'think' ? 0.17 + Math.sin(t * 1.5) * 0.03 : mood === 'sad' ? Math.sin(t * 1.2) * 0.02 : Math.sin(t * 1.3) * 0.015;
    core.rotation.x = mood === 'sleep' ? 0.14 : mood === 'tired' ? 0.09 : mood === 'sad' ? 0.13 : mood === 'alert' ? -0.05 : 0;
    if (p.tail) p.tail.rotation[p.tail.userData.ax || 'z'] = p.tail.userData.rz + Math.sin(t * wag) * wagA;
    A.ears.forEach((e, i) => { e.rotation.z = e.userData.rz + Math.sin(t * 2 + i) * 0.04 + (hopSpd ? (h - 0.5) * 0.25 * e.userData.d : 0) + (mood === 'sad' ? e.userData.d * 0.35 : 0) - (mood === 'alert' ? e.userData.d * 0.15 : 0); });
    A.arms.forEach((a) => { a.rotation.z = a.userData.rz + a.userData.d * (hopSpd ? h * 0.6 : Math.sin(t * 2) * 0.05); });
    if (A.mouth) { A.mouth.rotation.z = mood === 'sad' ? 0 : Math.PI; A.mouth.scale.set(A.mouth.userData.bx * (mood === 'think' ? 0.7 : mouthS), hopSpd ? mouthS : 1, 1); }
    if (p.ant) p.ant.rotation.z = Math.sin(t * 3) * 0.15;
    // 特效
    const sv = hot || mood === 'rush';
    this.sweat.visible = sv; this.sweat.position.set(this.right * 0.8, this.top * 0.72 + lift - ((t * 0.7) % 1) * 0.15, 0.5);
    this.sign.visible = !!risk; this.sign.position.set(-this.right * 0.82, this.top * 0.8 + lift + Math.sin(t * 6) * 0.04, 0.5); this.sign.scale.setScalar(0.85 + Math.sin(t * 8) * 0.06);
    this.symThink.visible = mood === 'think'; this.symThink.position.set(this.right * 0.62, this.top * 0.86 + lift + Math.sin(t * 2.5) * 0.06, 0.6); this.symThink.scale.setScalar(0.5);
    this.symAlert.visible = mood === 'alert'; this.symAlert.position.set(this.right * 0.55, this.top * 0.9 + lift, 0.6); this.symAlert.scale.setScalar(0.5 + Math.abs(Math.sin(t * 9)) * 0.08);
    this.zzz.forEach((sp, i) => {
      const on = mood === 'sleep' && !risk; sp.visible = on; if (!on) return;
      const q = ((t * 0.5) + i * 0.5) % 1;
      sp.position.set(this.right * 0.7 + q * 0.25, this.top * 0.8 + q * 0.6, 0.6); sp.material.opacity = Math.sin(q * Math.PI); sp.scale.setScalar(0.3 + q * 0.2);
    });
  }
}

export class Pet3D {
  w: number; h: number; ps: PetScene; r: any; cam: any; t: number; last: number; raf: number;
  constructor(canvas: HTMLCanvasElement, id: string, o: any = {}) {
    this.w = o.w || 150; this.h = o.h || 130;
    this.ps = new PetScene();
    this.r = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, premultipliedAlpha: true, preserveDrawingBuffer: !!o.preserve });
    this.r.setPixelRatio(o.pr || Math.min(window.devicePixelRatio || 1, 2)); this.r.setSize(this.w, this.h); this.r.setClearColor(0x000000, 0);
    this.cam = new THREE.PerspectiveCamera(26, this.w / this.h, 0.1, 50);
    this.t = 0; this.last = 0;
    this.setPet(id);
    if (!o.static) { const loop = (now) => {
      this.raf = requestAnimationFrame(loop);
      if (now - this.last < 33) return;
      const dt = Math.min(0.1, (now - this.last) / 1000); this.last = now; this.t += dt;
      this.ps.update(this.t, dt); this.render();
    }; this.raf = requestAnimationFrame(loop); }
  }
  setPet(id) {
    this.ps.setPet(id);
    const { cy, h, w } = this.ps.frame, k = 2 * Math.tan(13 * Math.PI / 180);
    const d = Math.max((h + 0.7) / k, (w + 0.5) / (k * this.w / this.h)) * 1.02;
    this.cam.position.set(0, cy + 0.3, d); this.cam.lookAt(0, cy, 0);
  }
  setState(m, h, r) { this.ps.setState(m, h, r); }
  resize(w: number, h: number) { this.w = w; this.h = h; this.r.setSize(w, h); this.cam.aspect = w / h; this.cam.updateProjectionMatrix(); this.setPet(this.ps.id); }
  render() { this.r.render(this.ps.scene, this.cam); }
  dispose() { cancelAnimationFrame(this.raf); this.r.dispose(); }
}

export function thumbnails(size = 112) {
  const canvas = document.createElement('canvas');
  const pet = new Pet3D(canvas, LIST[0].id, { w: size, h: size, preserve: true, static: true, pr: 2 });
  const out = [];
  for (const it of LIST) { pet.setPet(it.id); pet.ps.update(0.4, 0.016); pet.render(); out.push({ ...it, url: canvas.toDataURL('image/png') }); }
  pet.dispose(); return out;
}
