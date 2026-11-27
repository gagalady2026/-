// usage: node social_text.mjs SPEC.json OUT_DIR
// Renders each text item of SPEC (the social cuts' title, subtitles and end-card words, written by
// `python3 tools/social_cut.py spec`) to a transparent PNG, with the page's own web fonts (Noto Sans KR, Gowun Dodum from
// Google Fonts), so the words look as they do in the film. An item is { id, text, family, weight, size, color, shadow } or
// { id, parts: [{ text, family, weight, size, color }, ...], shadow } (parts set side by side on one baseline).
// Needs playwright-core next to it (as capture.mjs); CHROME overrides the browser path.
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const [, , specPath, outDir] = process.argv;
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome',
  proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined,
});
const page = await browser.newPage();
await page.setContent('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" '
  + 'href="https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Noto+Sans+KR:wght@400;500;700;800;900&display=swap">'
  + '</head><body></body></html>', { waitUntil: 'load' });
const items = await page.evaluate(async (spec) => {
  const out = [];
  for (const it of spec) {
    const parts = it.parts || [it];
    const fonts = parts.map((p) => `${p.weight} ${p.size}px ${p.family}`);
    for (let i = 0; i < parts.length; i++) await document.fonts.load(fonts[i], parts[i].text);
    const c = document.createElement('canvas'), g = c.getContext('2d');
    let w = 0, asc = 0, desc = 0;
    const ws = parts.map((p, i) => {
      g.font = fonts[i]; const m = g.measureText(p.text);
      asc = Math.max(asc, m.fontBoundingBoxAscent); desc = Math.max(desc, m.fontBoundingBoxDescent);
      return m.width;
    });
    w = ws.reduce((a, b) => a + b, 0);
    const pad = Math.ceil((it.shadow || 0) * 1.5 + 4);
    c.width = Math.ceil(w) + 2 * pad; c.height = Math.ceil(asc + desc) + 2 * pad;
    if (it.shadow) { g.shadowColor = 'rgba(8,6,14,0.55)'; g.shadowBlur = it.shadow; g.shadowOffsetY = 2; }
    g.textBaseline = 'alphabetic'; g.textAlign = 'left';
    let x = pad;
    parts.forEach((p, i) => { g.font = fonts[i]; g.fillStyle = p.color; g.fillText(p.text, x, pad + asc); x += ws[i]; });
    out.push({ id: it.id, url: c.toDataURL('image/png') });
  }
  return out;
}, spec);
for (const it of items) fs.writeFileSync(path.join(outDir, `${it.id}.png`), Buffer.from(it.url.split(',')[1], 'base64'));
console.log('texts', items.length);
await browser.close();
