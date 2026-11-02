// usage: node capture.mjs <html> <outDir> <frames: "0,24,48" | "all">
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
const t0 = Date.now();
for (const f of frames) {
  const data = await page.evaluate((fr) => { window.__renderAt(fr); return document.getElementById('view').toDataURL('image/png'); }, f);
  fs.writeFileSync(path.join(outDir, `f${String(f).padStart(4, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
}
console.log(`rendered ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
await browser.close();
