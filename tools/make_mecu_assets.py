"""One-off helper: turn the MECU Interactive brand files into web assets.

    py tools/make_mecu_assets.py "<folder with mecu-pfp.png, mecu-banner.png, mecu-intro.mp4>"

Needs Pillow, and ffmpeg on PATH for the video poster. The logo files are white on black, so the
brightness becomes the alpha channel: the page can then tint the mark with CSS (mask-image).
"""
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "images" / "mecu"
BONE = (244, 241, 230)


def mask(source, box=None, width=1200):
    """Brightness to alpha, cropped to the artwork, tinted bone."""
    gray = Image.open(source).convert("L")
    if box:
        gray = gray.crop(box)
    gray = ImageOps.autocontrast(gray, cutoff=(2, 0))
    # Flatten compression noise in the solid areas (keeps the soft edges, shrinks the file a lot).
    gray = gray.point(lambda v: 0 if v < 28 else 255 if v > 228 else v)
    gray = gray.crop(gray.point(lambda v: 255 if v > 40 else 0).getbbox())
    gray = gray.resize((width, round(gray.height * width / gray.width)), Image.LANCZOS)
    image = Image.new("RGBA", gray.size, BONE + (0,))
    image.putalpha(gray)
    return image


def main(folder):
    folder = Path(folder)
    OUT.mkdir(parents=True, exist_ok=True)
    pfp, banner = folder / "mecu-pfp.png", folder / "mecu-banner.png"

    mark = mask(pfp, width=1000)
    mark.save(OUT / "mark.webp", lossless=True)
    print("mark", mark.size)

    wide = Image.open(banner)
    w, h = wide.size
    lockup = mask(banner, width=1600)
    lockup.save(OUT / "lockup.webp", lossless=True)
    # The wordmark is the right-hand part of the banner (everything after the eagle).
    wordmark = mask(banner, box=(round(w * 0.34), 0, w, h), width=1600)
    wordmark.save(OUT / "wordmark.webp", lossless=True)
    print("lockup", lockup.size, "wordmark", wordmark.size)

    # Share card (1200×630) and app icons on solid black.
    card = Image.new("RGB", (1200, 630), "black")
    fitted = lockup.resize((960, round(lockup.height * 960 / lockup.width)), Image.LANCZOS)
    card.paste(fitted, ((1200 - fitted.width) // 2, (630 - fitted.height) // 2), fitted)
    card.save(OUT / "og-card.jpg", quality=86, optimize=True)
    for size in (192, 512):
        Image.open(pfp).convert("RGB").resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png", optimize=True)

    # Square cover for the highlight ring and a 4:5 tile for the Instagram grid.
    tile = Image.new("RGB", (1080, 1350), "black")
    art = mark.resize((760, round(mark.height * 760 / mark.width)), Image.LANCZOS)
    tile.paste(art, ((1080 - art.width) // 2, (1350 - art.height) // 2 - 40), art)
    word = wordmark.resize((700, round(wordmark.height * 700 / wordmark.width)), Image.LANCZOS)
    tile.paste(word, ((1080 - word.width) // 2, (1350 + art.height) // 2 + 10), word)
    tile.save(OUT / "ig-intro.jpg", quality=84, optimize=True)
    Image.open(pfp).convert("RGB").resize((320, 320), Image.LANCZOS).save(OUT / "hl-intro.jpg", quality=84, optimize=True)
    banner_rgb = Image.open(banner).convert("RGB")
    square = Image.new("RGB", (640, 640), "black")
    scaled = banner_rgb.resize((640, round(banner_rgb.height * 640 / banner_rgb.width)), Image.LANCZOS)
    square.paste(scaled, (0, (640 - scaled.height) // 2))
    square.resize((320, 320), Image.LANCZOS).save(OUT / "hl-brand.jpg", quality=84, optimize=True)
    banner_rgb.resize((1600, round(banner_rgb.height * 1600 / banner_rgb.width)), Image.LANCZOS).save(
        OUT / "banner.jpg", quality=84, optimize=True)

    video = folder / "mecu-intro.mp4"
    if video.exists():
        (ROOT / "media").mkdir(exist_ok=True)
        shutil.copyfile(video, ROOT / "media" / "mecu-intro.mp4")
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3.5", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=1280:-2", "-q:v", "4", str(OUT / "intro-poster.jpg")], check=True)
    print("done:", OUT)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
