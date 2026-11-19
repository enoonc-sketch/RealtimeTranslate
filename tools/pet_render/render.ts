// 帧渲染：把每只宠物的每个动画渲染成透明背景 PNG（224×224）。由 render.js(Electron) 加载，不随软件发布。
import * as THREE from 'three';
import { PetScene } from './pets3d';
import { PETS } from './petlist';
declare const require: any;
const fs = require('fs'), path = require('path');
const OUT = (window as any).FRAMES_DIR as string, SIZE = 224;
// 每个动画：心情、帧数、一个循环的时长（要和 pets3d.ts 里对应的动画周期一致，这样循环首尾能接上）
const ANIMS: Record<string, { mood: string; n: number; period: number }> = {
  idle: { mood: 'idle', n: 4, period: (2 * Math.PI) / 2.2 }, sleep: { mood: 'sleep', n: 4, period: (2 * Math.PI) / 1.4 },
  think: { mood: 'think', n: 4, period: (2 * Math.PI) / 1.5 }, happy: { mood: 'happy', n: 6, period: Math.PI / 3.2 },
  sad: { mood: 'sad', n: 3, period: (2 * Math.PI) / 1.2 }, alert: { mood: 'alert', n: 3, period: (2 * Math.PI) / 9 }
};
const canvas = document.createElement('canvas');
const r = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true, premultipliedAlpha: false });
r.setPixelRatio(1); r.setSize(SIZE, SIZE); r.setClearColor(0x000000, 0);
const cam = new THREE.PerspectiveCamera(26, 1, 0.1, 50);
const ps = new PetScene();
const save = (file: string) => { r.render(ps.scene, cam); fs.writeFileSync(file, Buffer.from(canvas.toDataURL('image/png').split(',')[1], 'base64')); };
let count = 0;
for (const pet of PETS) {
  ps.setPet(pet.id); ps.eye = 1;
  const { cy, h, w } = ps.frame, k = 2 * Math.tan((13 * Math.PI) / 180), d = Math.max((h + 0.7) / k, (w + 0.5) / k) * 1.02;
  cam.position.set(0, cy + 0.3, d); cam.lookAt(0, cy, 0);
  const dir = path.join(OUT, pet.id); fs.mkdirSync(dir, { recursive: true });
  const run = (mood: string, t: number, blink = false) => {
    ps.setState(mood, false, false);
    for (let i = 12; i >= 1; i--) ps.update(t - i * 0.05, 0.05); // 让眼睛等平滑量收敛到该心情
    if (blink) ps.eye = 0.08;
    ps.update(t, blink ? 0 : 0.05);
  };
  for (const [name, a] of Object.entries(ANIMS)) for (let i = 0; i < a.n; i++) { run(a.mood, 4 + 0.1 + (i * a.period) / a.n); save(path.join(dir, `${name}_${i}.png`)); count++; }
  run('idle', 4.3, true); save(path.join(dir, 'blink_0.png')); count++;
}
(window as any).RENDER_DONE = count;
