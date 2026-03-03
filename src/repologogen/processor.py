"""Image processing utilities for chromakey transparency and compression."""

import shutil
import tempfile
from pathlib import Path
from typing import Dict

from PIL import Image


def _save_image(img: Image.Image, input_path: Path, output_path: Path) -> None:
    """Save image to output path, handling in-place overwrites."""
    if input_path == output_path:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        img.save(tmp_path, "PNG")
        shutil.move(tmp_path, output_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")


def chromakey_to_transparent(
    input_path: Path, output_path: Path, key_color: str = "#00FF00", tolerance: int = 70
) -> Dict:
    """Convert chromakey background to transparent."""
    key_rgb = tuple(int(key_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

    img = Image.open(input_path).convert("RGBA")
    pixels = img.load()
    width, height = img.size
    transparent_pixels = 0
    total = width * height

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            distance = (abs(r - key_rgb[0]) + abs(g - key_rgb[1]) + abs(b - key_rgb[2])) / 3
            if distance <= tolerance:
                pixels[x, y] = (0, 0, 0, 0)
                transparent_pixels += 1

    _save_image(img, input_path, output_path)

    return {
        "processed": True,
        "transparent_pixels": transparent_pixels,
        "total_pixels": total,
        "transparency_ratio": round(transparent_pixels / total, 3),
    }


def trim_transparent(input_path: Path, output_path: Path, margin: int = 5) -> Dict:
    """Trim transparent padding from a PNG image."""
    img = Image.open(input_path).convert("RGBA")
    original_width, original_height = img.size

    alpha = img.split()[3]
    bbox = alpha.getbbox()

    if bbox is None:
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
        return {"trimmed": False, "reason": "fully_transparent"}

    content_width = bbox[2] - bbox[0]
    content_height = bbox[3] - bbox[1]
    content_ratio = round((content_width * content_height) / (original_width * original_height), 3)

    larger_dim = max(original_width, original_height)
    margin_px = int(larger_dim * margin / 100)

    expanded_bbox = (
        max(0, bbox[0] - margin_px),
        max(0, bbox[1] - margin_px),
        min(original_width, bbox[2] + margin_px),
        min(original_height, bbox[3] + margin_px),
    )

    cropped = img.crop(expanded_bbox)
    try:
        resized = cropped.resize((original_width, original_height), Image.Resampling.LANCZOS)
    except AttributeError:
        resized = cropped.resize((original_width, original_height), Image.LANCZOS)

    _save_image(resized, input_path, output_path)

    return {
        "trimmed": True,
        "content_ratio": content_ratio,
        "original_size": [original_width, original_height],
    }


def compress_png(input_path: Path, output_path: Path, quality: int = 80) -> Dict:
    """Compress a PNG image."""
    img = Image.open(input_path)
    compression = max(1, min(9, 10 - (quality // 10)))
    original_size = input_path.stat().st_size

    if input_path == output_path:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        img.save(tmp_path, "PNG", optimize=True, compress_level=compression)
        shutil.move(tmp_path, output_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", optimize=True, compress_level=compression)

    final_size = output_path.stat().st_size
    reduction = round((1 - final_size / original_size) * 100, 1) if original_size > 0 else 0

    return {
        "compressed": True,
        "original_size": original_size,
        "final_size": final_size,
        "reduction_percent": reduction,
    }


def get_image_info(path: Path) -> Dict:
    """Get information about an image file."""
    img = Image.open(path)
    has_alpha = img.mode in ("RGBA", "LA", "PA")
    transparency_percent = 0.0

    if has_alpha and img.mode == "RGBA":
        alpha = img.split()[3]
        transparent = sum(1 for p in alpha.getdata() if p == 0)
        total = alpha.size[0] * alpha.size[1]
        transparency_percent = round((transparent / total) * 100, 1)

    return {
        "path": str(path),
        "format": img.format,
        "mode": img.mode,
        "size": img.size,
        "has_transparency": has_alpha,
        "transparency_percent": transparency_percent,
        "file_size": path.stat().st_size if path.exists() else 0,
    }
