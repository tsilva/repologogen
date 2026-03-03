"""Tests for repologogen processor module."""

from pathlib import Path

import pytest
from PIL import Image

from repologogen.processor import (
    chromakey_to_transparent,
    trim_transparent,
    compress_png,
    get_image_info,
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
        original_size = path.stat().st_size

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
