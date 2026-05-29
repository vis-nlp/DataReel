import asyncio
import subprocess
import shutil
from pathlib import Path
from playwright.async_api import async_playwright
import sys

HTML_FILE = sys.argv[1] if len(sys.argv) > 1 else None
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else None
DURATION = float(sys.argv[3]) if len(sys.argv) > 3 else None

if not HTML_FILE or not OUTPUT or not DURATION:
    raise RuntimeError(
        "Usage: python render.py <html_file> <output_video> <duration_seconds>"
    )

FRAMES_DIR = "frames"
FPS = 30


async def capture():
    Path(FRAMES_DIR).mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Load HTML and wait for full JS execution
        await page.goto(
            Path(HTML_FILE).absolute().as_uri(),
            wait_until="load"
        )

        # Ensure chart + animation hooks exist
        await page.wait_for_selector("#chart", timeout=10000)
        await page.wait_for_function(
            "() => window.resetChart && window.scheduleNow",
            timeout=10000
        )

        total_frames = int(DURATION * FPS)

        # Read chart size from SVG
        width, height = await page.evaluate("""
            () => {
                const svg = document.querySelector("#chart");
                if (!svg) throw new Error("SVG #chart not found");

                const w = svg.viewBox.baseVal.width || svg.width.baseVal.value;
                const h = svg.viewBox.baseVal.height || svg.height.baseVal.value;
                return [Math.ceil(w), Math.ceil(h)];
            }
        """)

        # Resize viewport exactly to chart
        await page.set_viewport_size({
            "width": width,
            "height": height
        })

        print(f"🎬 Capturing {total_frames} frames @ {FPS}fps")
        print(f"🖼️  Chart size: {width}x{height}")

        # Start animation
        await page.evaluate("""
            resetChart();
            scheduleNow();
        """)

        svg = await page.query_selector("#chart")

        for i in range(total_frames):
            await svg.screenshot(
                path=f"{FRAMES_DIR}/frame_{i:05d}.png"
            )

            if i % FPS == 0:
                print(f"  ⏱ {i // FPS}s")

        await browser.close()


def encode_and_cleanup():
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", f"{FRAMES_DIR}/frame_%05d.png",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-movflags", "+faststart",
        OUTPUT
    ], check=True)

    shutil.rmtree(FRAMES_DIR)


async def main():
    await capture()
    encode_and_cleanup()
    print("🎬 Video written to", OUTPUT)


if __name__ == "__main__":
    asyncio.run(main())
