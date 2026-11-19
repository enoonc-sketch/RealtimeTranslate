// Electron 入口：node render.js <输出目录>
const { app, BrowserWindow } = require('electron'); const path = require('path');
['use-gl:angle', 'use-angle:swiftshader', 'enable-unsafe-swiftshader', 'ignore-gpu-blocklist'].forEach((x) => { const [k, v] = x.split(':'); app.commandLine.appendSwitch(k, v); });
const out = path.resolve(process.argv[process.argv.length - 1]);
app.whenReady().then(async () => {
  const w = new BrowserWindow({ show: false, webPreferences: { nodeIntegration: true, contextIsolation: false } });
  await w.loadFile(path.join(__dirname, 'render.html'), { query: { out } });
  await w.webContents.executeJavaScript(`window.FRAMES_DIR=${JSON.stringify(out)}`);
  await w.webContents.executeJavaScript("var s=document.createElement('script');s.src='render.bundle.js';document.body.appendChild(s);new Promise(r=>s.onload=r)");
  const n = await w.webContents.executeJavaScript('window.RENDER_DONE');
  console.log('RENDERED', n); app.quit();
});
