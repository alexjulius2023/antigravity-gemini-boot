"""Utility script to rebuild neon blueprint line-art and transparent character cutouts."""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def remove_white_bg_floodfill(img: Image.Image, thresh: int = 242, feather_thresh: int = 215) -> Image.Image:
    """Remove exterior white background via border flood-fill + anti-aliased edge matting."""
    rgb = np.array(img.convert("RGB"), dtype=np.int16)
    h, w, _ = rgb.shape
    min_c = rgb.min(axis=2)
    max_c = rgb.max(axis=2)
    chroma = max_c - min_c
    is_white = (min_c >= thresh) & (chroma <= 22)

    bg = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        if is_white[0, x]:
            bg[0, x] = True
            q.append((0, x))
        if is_white[h - 1, x]:
            bg[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if is_white[y, 0] and not bg[y, 0]:
            bg[y, 0] = True
            q.append((y, 0))
        if is_white[y, w - 1] and not bg[y, w - 1]:
            bg[y, w - 1] = True
            q.append((y, w - 1))

    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not bg[ny, nx] and is_white[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))

    alpha = np.where(bg, 0, 255).astype(np.uint8)
    bg_dilated = bg.copy()
    for _ in range(2):
        padded = np.pad(bg_dilated, 1, mode="constant", constant_values=True)
        bg_dilated = (
            padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:] |
            padded[:-2, :-2] | padded[:-2, 2:] | padded[2:, :-2] | padded[2:, 2:]
        )
    edge = bg_dilated & (~bg)
    soft_white = edge & (min_c >= feather_thresh) & (chroma <= 35)
    t = np.clip((252.0 - min_c[soft_white]) / max(1.0, (252.0 - feather_thresh)), 0.0, 1.0)
    alpha[soft_white] = (t * 255).astype(np.uint8)

    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    out = Image.fromarray(rgba, mode="RGBA")
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out


def build_hero_neon(hero_path: Path, out_path: Path) -> None:
    """Generate pixel-aligned glowing cyan-violet-pink neon blueprint line-art from hero CG."""
    hero = Image.open(hero_path).convert("RGB")
    arr = np.array(hero, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
    edge = np.clip((np.hypot(gx, gy) - 16.0) / 70.0, 0.0, 1.0)

    h, w = edge.shape
    xg = np.linspace(0.0, 1.0, w)[None, :]
    yg = np.linspace(0.0, 1.0, h)[:, None]
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, 0] = np.clip(85 * (1 - yg) + 244 * yg, 0, 255).astype(np.uint8)
    out[:, :, 1] = np.clip(220 * (1 - xg * 0.5) + 120 * (xg * 0.5), 0, 255).astype(np.uint8)
    out[:, :, 2] = np.clip(255 * (1 - yg * 0.35) + 190 * (yg * 0.35), 0, 255).astype(np.uint8)
    out[:, :, 3] = np.clip(edge * 255.0, 0, 255).astype(np.uint8)

    line = Image.fromarray(out, mode="RGBA")
    glow = line.filter(ImageFilter.GaussianBlur(radius=3.0))
    Image.alpha_composite(glow, line).save(out_path)
    print(f"Saved neon blueprint: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild neon line-art for custom hero CG")
    parser.add_argument("--hero", type=Path, default=ASSETS / "gemini_catgirl_hero.jpg")
    parser.add_argument("--out", type=Path, default=ASSETS / "gemini_catgirl_hero_neon.png")
    args = parser.parse_args()
    build_hero_neon(args.hero, args.out)


if __name__ == "__main__":
    main()
