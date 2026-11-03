// one-off: background plate + foreground tablet for the motion-comic test, rendered from the 2D page's vector scene
// usage: node mc_plates.mjs <abs path to cut06_2d.html> <outDir>   → plate_raw.png, tablet_raw.png (blurred afterwards into ../assets)
import { chromium } from 'playwright-core';
const [, , htmlPath, outDir] = process.argv;
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', proxy: { server: process.env.HTTPS_PROXY } });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('file://' + htmlPath + '?capture');
await page.waitForFunction(() => window.__ready === true);
// plate: yard wall, roofs, sea, headland + lighthouse — no people, no tablet; framed for a close-up
await page.evaluate(() => {
  window.__renderAt(70);
  for (const id of ['C', 'P', 'tablet', 'speed', 'nodMarks']) document.getElementById(id).style.display = 'none';
  for (const id of ['layFar', 'layMid', 'layWall', 'layNear']) document.getElementById(id).setAttribute('transform', '');
  const s = 1920 / 920;
  document.getElementById('cam').setAttribute('transform', `scale(${s}) translate(-1000 -150)`);
  const svg = document.getElementById('view');
  [...svg.children].filter((n) => n.tagName === 'rect').forEach((r) => (r.style.display = 'none'));   // warm + vignette overlays
});
await page.screenshot({ path: `${outDir}/plate_raw.png`, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
// foreground: the tablet alone (② highlighted state), large, on a transparent background
await page.evaluate(() => {
  window.__renderAt(70);
  for (const id of ['C', 'P', 'speed', 'nodMarks', 'layFar', 'layMid', 'layWall']) document.getElementById(id).style.display = 'none';
  document.getElementById('tablet').style.display = '';
  const near = document.getElementById('layNear');
  near.setAttribute('transform', '');
  [...near.children].forEach((n) => { if (n.id !== 'tablet') n.style.display = 'none'; });
  document.getElementById('cam').setAttribute('transform', 'translate(60 40) scale(2.6) translate(-790 -400)');
  document.body.style.background = 'transparent';
  document.getElementById('stage').style.background = 'transparent';
});
await page.screenshot({ path: `${outDir}/tablet_raw.png`, clip: { x: 0, y: 0, width: 1920, height: 1080 }, omitBackground: true });
await browser.close();
console.log('ok');
