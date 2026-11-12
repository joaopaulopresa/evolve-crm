// Helpers for the demo recordings: an on-screen caption, a visible cursor, and MP4 export.

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

import type { Locator, Page } from "@playwright/test";

export const MEDIA_DIR = path.resolve(import.meta.dirname, "../../docs/media");

// Times are seconds since the recording started.
type Span = { start: number; end: number; seconds: number };
let recordingStarted = 0;
let waits: Span[] = []; // stretches of waiting, played back in `seconds`
let heroClips: Span[] = []; // moments that make up the short looping animation
const now = () => (Date.now() - recordingStarted) / 1000;

/** Adds the caption bar and a cursor dot to every page the recording visits. */
export async function installOverlay(page: Page) {
  recordingStarted = Date.now();
  waits = [];
  heroClips = [];
  position = { x: 640, y: 360 };
  await page.addInitScript(() => {
    const setup = () => {
      if (document.getElementById("demo-caption")) return;
      const caption = document.createElement("div");
      caption.id = "demo-caption";
      caption.style.cssText =
        "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;" +
        "background:rgba(27,36,64,.94);color:#fff;font:600 19px/1.35 system-ui,sans-serif;" +
        "padding:10px 20px;border-radius:8px;max-width:80vw;text-align:center;" +
        "box-shadow:0 8px 24px rgba(0,0,0,.25);opacity:0;transition:opacity .25s;pointer-events:none";
      const cursor = document.createElement("div");
      cursor.id = "demo-cursor";
      cursor.style.cssText =
        "position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;z-index:99999;" +
        "border-radius:50%;background:rgba(14,124,102,.55);border:2px solid #fff;" +
        "box-shadow:0 0 0 1px rgba(27,36,64,.5);pointer-events:none";
      document.body.append(caption, cursor);
      document.addEventListener(
        "mousemove",
        (event) => {
          cursor.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
        },
        true,
      );
    };
    if (document.body) setup();
    else document.addEventListener("DOMContentLoaded", setup);
  });
}

/** Shows a caption and holds long enough to read it. Pass "" to hide it. */
export async function caption(page: Page, text: string, holdMs = 1800) {
  await page.evaluate((value) => {
    const element = document.getElementById("demo-caption");
    if (!element) return;
    element.textContent = value;
    element.style.opacity = value ? "1" : "0";
  }, text);
  await page.waitForTimeout(holdMs);
}

let position = { x: 640, y: 360 };

/** Moves the cursor to the element at a human pace. */
export async function glideTo(page: Page, target: Locator) {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) throw new Error("glideTo: element is not visible");
  const goal = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  const steps = 24;
  for (let step = 1; step <= steps; step++) {
    const eased = 1 - Math.pow(1 - step / steps, 3);
    await page.mouse.move(
      position.x + (goal.x - position.x) * eased,
      position.y + (goal.y - position.y) * eased,
    );
    await page.waitForTimeout(14);
  }
  position = goal;
}

export async function click(page: Page, target: Locator, afterMs = 600) {
  await glideTo(page, target);
  await page.waitForTimeout(150);
  await target.click();
  await page.waitForTimeout(afterMs);
}

export async function type(page: Page, target: Locator, text: string) {
  await click(page, target, 100);
  await target.pressSequentially(text, { delay: 45 });
  await page.waitForTimeout(300);
}

/** Drags with real mouse events so the recording shows the card travelling. */
export async function drag(page: Page, source: Locator, destination: Locator) {
  await glideTo(page, source);
  await page.mouse.down();
  await glideTo(page, destination);
  await page.waitForTimeout(200);
  await page.mouse.up();
  await page.waitForTimeout(700);
}

export async function screenshot(page: Page, name: string) {
  mkdirSync(MEDIA_DIR, { recursive: true });
  await page.evaluate(() => {
    for (const id of ["demo-caption", "demo-cursor"]) {
      const element = document.getElementById(id);
      if (element) element.style.visibility = "hidden";
    }
  });
  await page.screenshot({ path: path.join(MEDIA_DIR, `${name}.png`) });
  await page.evaluate(() => {
    for (const id of ["demo-caption", "demo-cursor"]) {
      const element = document.getElementById(id);
      if (element) element.style.visibility = "";
    }
  });
}

/** Waits for something slow (the agent, a deploy). The video plays this stretch in `seconds`. */
export async function fastForward(page: Page, text: string, wait: () => Promise<unknown>, seconds = 6) {
  await caption(page, `${text} (sped up)`, 400);
  const start = now();
  await wait();
  waits.push({ start, end: now(), seconds });
}

/** Marks what happens inside as part of the short hero animation, played in `seconds`. */
export async function heroClip(seconds: number, action: () => Promise<unknown>) {
  const start = now();
  await action();
  heroClips.push({ start, end: now(), seconds });
}

/** An ffmpeg filter that plays each span in its target time and joins them. */
function retime(spans: Span[], tail: string): string {
  const parts = spans.map(
    ({ start, end, seconds }, index) =>
      `[0:v]trim=start=${start.toFixed(2)}:end=${end.toFixed(2)},` +
      `setpts=(PTS-STARTPTS)*${(seconds / Math.max(end - start, 0.1)).toFixed(4)}[p${index}]`,
  );
  const inputs = spans.map((_, index) => `[p${index}]`).join("");
  return `${parts.join(";")};${inputs}concat=n=${spans.length}:v=1${tail}`;
}

/** Closes the page and converts its recording to docs/media/<name>.mp4 (H.264), with the
 * waiting stretches sped up. With hero clips marked, also writes docs/media/hero.gif. */
export async function saveVideo(page: Page, name: string) {
  mkdirSync(MEDIA_DIR, { recursive: true });
  const video = page.video();
  const total = now();
  await page.context().close();
  const source = await video!.path();
  const target = path.join(MEDIA_DIR, `${name}.mp4`);

  // The whole recording as spans: normal speed, except the waits.
  const spans: Span[] = [];
  let cursor = 0;
  for (const wait of waits) {
    if (wait.start > cursor) spans.push({ start: cursor, end: wait.start, seconds: wait.start - cursor });
    spans.push({ ...wait, seconds: Math.min(wait.seconds, wait.end - wait.start) });
    cursor = wait.end;
  }
  spans.push({ start: cursor, end: total, seconds: total - cursor });

  execFileSync("ffmpeg", [
    "-y", "-loglevel", "error", "-i", source,
    "-filter_complex", retime(spans, "[out]"), "-map", "[out]", "-r", "25",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", "-an",
    target,
  ]);
  console.log(`saved ${target}`);

  if (heroClips.length > 0) {
    const gif = path.join(MEDIA_DIR, "hero.gif");
    const filter =
      retime(heroClips, ",fps=12,scale=960:-1:flags=lanczos,split[a][b]") +
      ";[a]palettegen=max_colors=128:stats_mode=diff[palette];[b][palette]paletteuse=dither=bayer:bayer_scale=4";
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", source, "-filter_complex", filter, gif]);
    try {
      // Smaller file when gifsicle is installed; the GIF is fine without it.
      execFileSync("gifsicle", ["-O3", "--lossy=60", "--batch", gif], { stdio: "ignore" });
    } catch {
      /* gifsicle is optional */
    }
    console.log(`saved ${gif}`);
  }
}
