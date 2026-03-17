"""Tests for repologogen processor module."""

from pathlib import Path

import pytest
from PIL import Image

from repologogen.processor import (
    chromakey_to_transparent,
    compose_marketing_graphic,
    compose_social_card,
    compress_png,
    export_favicon_set,
    get_image_info,
    resize_cover_png,
    resize_png,
    trim_transparent,
    write_site_webmanifest,
)


class TestChromakeyToTransparent:
    """Test chromakey_to_transparent function."""

    def test_converts_green_background(self, tmp_path):
        """Test converting green chromakey background."""
        # Create image with green background and red square
        img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        pixels = img.load()
        for x in range(40, 60):
            for y in range(40, 60):
                pixels[x, y] = (255, 0, 0)

        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        img.save(input_path, "PNG")

        result = chromakey_to_transparent(input_path, output_path)

        assert result["processed"] is True
        assert result["transparency_ratio"] > 0.7  # Most should be transparent

        # Verify output has transparency
        output_img = Image.open(output_path)
        assert output_img.mode == "RGBA"

    def test_handles_nonexistent_input(self, tmp_path):
        """Test handling of non-existent input file."""
        with pytest.raises(FileNotFoundError):
            chromakey_to_transparent(tmp_path / "nonexistent.png", tmp_path / "output.png")


class TestTrimTransparent:
    """Test trim_transparent function."""

    def test_trims_padding(self, tmp_path):
        """Test trimming transparent padding."""
        # Create image with small content in center
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        for x in range(75, 125):
            for y in range(75, 125):
                img.putpixel((x, y), (255, 0, 0, 255))

        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        img.save(input_path, "PNG")

        result = trim_transparent(input_path, output_path, margin=5)

        assert result["trimmed"] is True
        assert result["content_ratio"] < 0.1  # Original has lots of padding

        # Output should maintain original dimensions
        output_img = Image.open(output_path)
        assert output_img.size == (200, 200)

    def test_handles_fully_transparent(self, tmp_path):
        """Test handling of fully transparent image."""
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        img.save(input_path, "PNG")

        result = trim_transparent(input_path, output_path)

        assert result["trimmed"] is False
        assert result["reason"] == "fully_transparent"

    def test_inplace_overwrite(self, tmp_path):
        """Test in-place file modification."""
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        img.putpixel((50, 50), (255, 255, 255, 255))

        path = tmp_path / "image.png"
        img.save(path, "PNG")

        result = trim_transparent(path, path)

        assert result["trimmed"] is True
        assert path.exists()


class TestCompressPng:
    """Test compress_png function."""

    def test_reduces_file_size(self, tmp_path):
        """Test that compression reduces file size."""
        # Create a simple image
        img = Image.new("RGBA", (500, 500), (255, 0, 0, 255))
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        img.save(input_path, "PNG")

        result = compress_png(input_path, output_path, quality=80)

        assert result["compressed"] is True
        assert result["final_size"] <= result["original_size"]
        assert "reduction_percent" in result

    def test_inplace_compression(self, tmp_path):
        """Test in-place compression."""
        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        path = tmp_path / "image.png"
        img.save(path, "PNG")

        result = compress_png(path, path, quality=90)

        assert result["compressed"] is True
        assert path.exists()


class TestGetImageInfo:
    """Test get_image_info function."""

    def test_returns_correct_info(self, tmp_path):
        """Test image info extraction."""
        img = Image.new("RGBA", (100, 200), (0, 0, 255, 128))
        path = tmp_path / "test.png"
        img.save(path, "PNG")

        info = get_image_info(path)

        assert info["path"] == str(path)
        assert info["format"] == "PNG"
        assert info["mode"] == "RGBA"
        assert info["size"] == (100, 200)
        assert info["has_transparency"] is True
        assert info["file_size"] > 0

    def test_detects_no_transparency(self, tmp_path):
        """Test detection of non-transparent images."""
        img = Image.new("RGB", (50, 50), (255, 0, 0))
        path = tmp_path / "test.jpg"
        img.save(path, "JPEG")

        info = get_image_info(path)

        assert info["has_transparency"] is False
        assert info["transparency_percent"] == 0.0


class TestResizePng:
    """Test PNG resizing."""

    def test_resizes_png(self, tmp_path):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        img.save(input_path, "PNG")

        result = resize_png(input_path, output_path, (32, 32))

        assert result["size"] == (32, 32)
        assert Image.open(output_path).size == (32, 32)


class TestResizeCoverPng:
    """Test cover resize for exact-size wide exports."""

    def test_resizes_with_center_crop(self, tmp_path):
        img = Image.new("RGBA", (1600, 900), (255, 0, 0, 255))
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        img.save(input_path, "PNG")

        result = resize_cover_png(input_path, output_path, (1200, 630))

        assert result["size"] == (1200, 630)
        assert Image.open(output_path).size == (1200, 630)


class TestExportFaviconSet:
    """Test favicon export helpers."""

    def test_exports_pngs_and_ico(self, tmp_path):
        img = Image.new("RGBA", (128, 128), (255, 0, 0, 255))
        input_path = tmp_path / "icon.png"
        img.save(input_path, "PNG")

        result = export_favicon_set(input_path, tmp_path / "favicon")

        assert len(result["pngs"]) == 3
        assert Path(result["ico"]).exists()


class TestComposeSocialCard:
    """Test deterministic social card composition."""

    def test_creates_social_card(self, tmp_path):
        img = Image.new("RGBA", (512, 512), (0, 128, 255, 255))
        icon_path = tmp_path / "icon.png"
        output_path = tmp_path / "social-card.png"
        img.save(icon_path, "PNG")

        result = compose_social_card(
            icon_path,
            output_path,
            project_name="RepoLogoGen",
            title="RepoLogoGen brand assets",
            description="Generate a brand kit for any repository.",
        )

        assert result["size"] == (1200, 630)
        assert Image.open(output_path).size == (1200, 630)


class TestComposeMarketingGraphic:
    """Test generic marketing graphic composition."""

    def test_creates_exact_size_marketing_graphic(self, tmp_path):
        img = Image.new("RGBA", (512, 512), (0, 128, 255, 255))
        brand_path = tmp_path / "brand.png"
        output_path = tmp_path / "feature.png"
        img.save(brand_path, "PNG")

        result = compose_marketing_graphic(
            brand_path,
            output_path,
            project_name="RepoLogoGen",
            title="RepoLogoGen Brand Pack",
            description="Generate platform assets from a base logo.",
            size=(1024, 500),
        )

        assert result["size"] == (1024, 500)
        assert Image.open(output_path).size == (1024, 500)


class TestWriteSiteWebmanifest:
    """Test site webmanifest generation."""

    def test_writes_manifest_json(self, tmp_path):
        output_path = tmp_path / "site.webmanifest"

        result = write_site_webmanifest(
            output_path,
            name="RepoLogoGen",
            description="Generate brand assets.",
            icons=[
                {"src": "android-chrome-192.png", "sizes": "192x192", "type": "image/png"},
            ],
        )

        assert result["path"] == str(output_path)
        payload = output_path.read_text(encoding="utf-8")
        assert "RepoLogoGen" in payload
        assert "android-chrome-192.png" in payload
