// Renders radar.html frame by frame into radar.mp4 (silent).
// Usage: node render.js            -> full video
//        node render.js 12 33 108  -> still images at these seconds (still-12.png ...)
// Needs Chrome/Chromium and ffmpeg. Set CHROME_PATH if Chrome is not in the default macOS location.
const { chromium } = require('playwright-core');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const FPS = 30;
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async () => {
  const stills = process.argv.slice(2).map(Number);
  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  await page.goto(pathToFileURL(path.join(__dirname, 'radar.html')).href + '?capture');
  if (stills.length) {
    for (const s of stills) { await page.evaluate(t => render(t), s); await page.screenshot({ path: path.join(__dirname, `still-${s}.png`) }); }
    return browser.close();
  }
  const dir = path.join(__dirname, 'frames');
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const total = Math.round(await page.evaluate(() => DURATION) * FPS);
  for (let f = 0; f < total; f++) {
    await page.evaluate(t => render(t), f / FPS);
    await page.screenshot({ path: path.join(dir, String(f).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 92 });
  }
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(dir, '%05d.jpg'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', path.join(__dirname, 'radar.mp4')]);
  console.log(`done: ${total} frames -> radar.mp4`);
})();
