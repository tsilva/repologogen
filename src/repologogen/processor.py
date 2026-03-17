"""Image processing utilities for chromakey transparency and brand asset exports."""

import json
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont


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


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    candidates = (
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf"] if bold else ["DejaVuSans.ttf", "Arial.ttf"]
    )

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue

    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    max_width: int,
    *,
    max_lines: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break

    remaining_words = words[len(" ".join(lines + [current]).split()) :]
    if remaining_words and len(lines) == max_lines - 1:
        tail = f"{current} {' '.join(remaining_words)}".strip()
        while tail:
            bbox = draw.textbbox((0, 0), f"{tail}...", font=font)
            if bbox[2] <= max_width or len(tail) <= 1:
                if bbox[2] <= max_width:
                    current = f"{tail}..."
                else:
                    current = tail[: max(1, len(tail) - 1)] + "..."
                break
            tail = tail[:-1]

    lines.append(current)
    return lines[:max_lines]


def chromakey_to_transparent(
    input_path: Path, output_path: Path, key_color: str = "#00FF00", tolerance: int = 70
) -> dict[str, object]:
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


def trim_transparent(input_path: Path, output_path: Path, margin: int = 5) -> dict[str, object]:
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


def compress_png(input_path: Path, output_path: Path, quality: int = 80) -> dict[str, object]:
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


def resize_png(input_path: Path, output_path: Path, size: tuple[int, int]) -> dict[str, object]:
    """Resize an image to a target PNG size."""
    img = Image.open(input_path).convert("RGBA")
    resized = img.resize(size, Image.Resampling.LANCZOS)
    _save_image(resized, input_path, output_path)
    return {"path": str(output_path), "size": size}


def export_favicon_set(
    input_path: Path,
    output_dir: Path,
    sizes: Iterable[int] = (16, 32, 48),
) -> dict[str, object]:
    """Export favicon PNG variants and a combined ICO file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(input_path).convert("RGBA")
    size_values = tuple(sizes)

    png_outputs: list[str] = []
    resized_images: list[Image.Image] = []
    for size in size_values:
        resized = source.resize((size, size), Image.Resampling.LANCZOS)
        png_path = output_dir / f"favicon-{size}.png"
        resized.save(png_path, "PNG")
        png_outputs.append(str(png_path))
        resized_images.append(resized)

    ico_path = output_dir / "favicon.ico"
    resized_images[-1].save(ico_path, format="ICO", sizes=[(size, size) for size in size_values])

    return {"pngs": png_outputs, "ico": str(ico_path)}


def compose_social_card(
    icon_path: Path,
    output_path: Path,
    *,
    project_name: str,
    title: str,
    description: str,
    accent_color: str = "#58a6ff",
) -> dict[str, object]:
    """Compose a deterministic social share card using the generated icon."""
    width, height = 1200, 630
    canvas = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(canvas)

    start = ImageColor.getrgb("#0b1220")
    end = ImageColor.getrgb("#172a45")
    accent = (
        ImageColor.getrgb(accent_color)
        if accent_color.startswith("#")
        else ImageColor.getrgb("#58a6ff")
    )

    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color, width=1)

    draw.rounded_rectangle(
        (48, 48, width - 48, height - 48),
        radius=36,
        outline=(255, 255, 255, 30),
        width=2,
    )
    draw.ellipse((860, -120, 1260, 280), fill=accent + (45,))
    draw.ellipse((-100, 420, 280, 820), fill=accent + (25,))

    icon = Image.open(icon_path).convert("RGBA").resize((280, 280), Image.Resampling.LANCZOS)
    icon_bg = Image.new("RGBA", (340, 340), (255, 255, 255, 18))
    icon_draw = ImageDraw.Draw(icon_bg)
    icon_draw.rounded_rectangle((0, 0, 339, 339), radius=42, fill=(255, 255, 255, 18))
    canvas.alpha_composite(icon_bg, dest=(88, 145))
    canvas.alpha_composite(icon, dest=(118, 175))

    eyebrow_font = _load_font(28, bold=False)
    title_font = _load_font(60, bold=True)
    body_font = _load_font(28, bold=False)

    text_left = 470
    draw.text((text_left, 120), project_name.upper(), fill=(180, 198, 227), font=eyebrow_font)

    title_lines = _wrap_text(draw, title, title_font, 620, max_lines=3)
    y_offset = 180
    for line in title_lines:
        draw.text((text_left, y_offset), line, fill=(255, 255, 255), font=title_font)
        line_bbox = draw.textbbox((text_left, y_offset), line, font=title_font)
        y_offset = line_bbox[3] + 8

    body_lines = _wrap_text(draw, description, body_font, 560, max_lines=4)
    y_offset += 24
    for line in body_lines:
        draw.text((text_left, y_offset), line, fill=(210, 220, 238), font=body_font)
        line_bbox = draw.textbbox((text_left, y_offset), line, font=body_font)
        y_offset = line_bbox[3] + 6

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG")
    return {"path": str(output_path), "size": (width, height)}


def write_site_webmanifest(
    output_path: Path,
    *,
    name: str,
    description: str,
    icons: list[dict[str, str]],
) -> dict[str, object]:
    """Write a minimal web app manifest for SEO/web install surfaces."""
    payload = {
        "name": name,
        "short_name": name,
        "description": description,
        "icons": icons,
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "display": "standalone",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"path": str(output_path)}


def get_image_info(path: Path) -> dict[str, object]:
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
