#!/usr/bin/env python3
"""Generate all icon sizes from img/logo-justgivenup.png.

Outputs:
  extension/icons/icon{16,32,48,128}.png
  app/web/favicon.png  app/web/icon128.png
  packaging/deb/usr/share/icons/hicolor/{16x16,32x32,48x48,128x128}/apps/justgivenup.png
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "img" / "logo-justgivenup.png"
SIZES = [16, 32, 48, 128, 256]


def square(img: Image.Image) -> Image.Image:
    """Pad to a transparent square canvas (icons must be square)."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    side = max(img.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas


def save(img: Image.Image, path: pathlib.Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((size, size), Image.LANCZOS).save(path, "PNG")
    print(f"  {path.relative_to(ROOT)} ({size}x{size})")


def main() -> int:
    if not SOURCE.is_file():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    base = square(Image.open(SOURCE))

    print("extension icons:")
    for size in (16, 32, 48, 128):
        save(base, ROOT / "extension" / "icons" / f"icon{size}.png", size)

    print("web assets:")
    save(base, ROOT / "app" / "web" / "favicon.png", 32)
    save(base, ROOT / "app" / "web" / "icon128.png", 128)

    print("debian hicolor icons:")
    for size in (16, 32, 48, 128):
        save(base,
             ROOT / "packaging" / "deb" / "usr" / "share" / "icons" / "hicolor"
             / f"{size}x{size}" / "apps" / "justgivenup.png",
             size)

    # app/web hero (256)
    save(base, ROOT / "app" / "web" / "logo.png", 256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
