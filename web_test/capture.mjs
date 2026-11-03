// usage: node capture.mjs <html> <outDir> <frames: "0,24,48" | "all">
// works for <canvas id="view"> and <svg id="view"> pages that expose window.__renderAt(frame) and window.__ready
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';
const [, , htmlPath, outDir, which = 'all'] = process.argv;
const LOCAL = path.resolve(path.dirname(new URL(import.meta.url).pathname), 'node_modules/three');
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome',
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  proxy: { server: process.env.HTTPS_PROXY },
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('console:', m.text()); });
await page.route(/cdn\.jsdelivr\.net\/npm\/three@0\.160\.0\/(.*)$/, async (route) => {
  const rel = route.request().url().match(/three@0\.160\.0\/(.*)$/)[1];
  await route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(path.join(LOCAL, rel)) });
});
await page.goto('file://' + path.resolve(htmlPath) + '?capture');
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
const frames = which === 'all' ? [...Array(96).keys()] : which.split(',').map(Number);
// <canvas id="view"> pages (three.js, 2D canvas) are read back with toDataURL; <svg id="view"> pages — and canvases that
// draw local image files (a file:// page taints the canvas, so toDataURL is refused) — are screenshotted instead
let isCanvas = await page.evaluate(() => {
  const v = document.getElementById('view');
  if (!(v instanceof HTMLCanvasElement)) return false;
  try { window.__renderAt(0); v.toDataURL('image/png'); return true; } catch (e) { return false; }
});
const t0 = Date.now();
for (const f of frames) {
  const out = path.join(outDir, `f${String(f).padStart(4, '0')}.png`);
  if (isCanvas) {
    const data = await page.evaluate((fr) => { window.__renderAt(fr); return document.getElementById('view').toDataURL('image/png'); }, f);
    fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
  } else {
    await page.evaluate((fr) => window.__renderAt(fr), f);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
  }
}
console.log(`rendered ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
await browser.close();
