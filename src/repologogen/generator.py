"""Image generation module using OpenAI-compatible APIs."""

import base64
from pathlib import Path
from typing import Optional

import httpx

from repologogen.config import get_api_key


class ImageGeneratorError(Exception):
    """Raised when image generation fails."""

    pass


class ImageGenerator:
    """Client for generating images via OpenAI-compatible APIs."""

    DEFAULT_TEMPLATE = """A {STYLE} logo for {PROJECT_NAME}: {VISUAL_METAPHOR}.
Clean vector style. Icon colors from: {ICON_COLORS}.
Pure {KEY_COLOR} background only. Do not use similar tones in the design.
{TEXT_INSTRUCTIONS} Single centered icon, geometric shapes. The icon must fill the entire canvas edge-to-edge with minimal padding. No empty space around the design. Scalable to small sizes."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 120.0,
        project_path: Optional[Path] = None,
    ):
        """Initialize the image generator."""
        self.api_key = api_key or get_api_key(project_path)
        if not self.api_key:
            raise ImageGeneratorError(
                "API key required. Set OPENROUTER_API_KEY environment variable or "
                "configure ~/.repologogen/config.yaml"
            )

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        model: str,
        output_path: Path,
        size: str = "1K",
        aspect_ratio: str = "1:1",
    ) -> dict:
        """Generate an image and save it to the output path."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "image_config": {
                "aspect_ratio": aspect_ratio,
                "image_size": size,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()

                if "choices" not in data or not data["choices"]:
                    raise ImageGeneratorError(f"No choices in response: {data.keys()}")

                message = data["choices"][0].get("message", {})
                images = message.get("images", [])

                if not images:
                    raise ImageGeneratorError(f"No images in response: {message.keys()}")

                image_data = images[0]
                image_url = image_data.get("image_url", {}).get("url", "")

                if image_url.startswith("data:image"):
                    # Extract base64 data from data URL
                    base64_data = image_url.split(",")[1]
                    output_path.write_bytes(base64.b64decode(base64_data))
                elif image_url.startswith("http"):
                    img_response = client.get(image_url)
                    img_response.raise_for_status()
                    output_path.write_bytes(img_response.content)
                else:
                    raise ImageGeneratorError(f"Unexpected image URL format: {image_url[:50]}...")

                return {"success": True, "model": model, "output_path": str(output_path)}

        except httpx.HTTPStatusError as e:
            raise ImageGeneratorError(
                f"API error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise ImageGeneratorError(f"Request failed: {e}") from e
        except Exception as e:
            raise ImageGeneratorError(f"Unexpected error: {e}") from e


def build_prompt(
    project_name: str,
    style: str,
    icon_colors: list[str],
    key_color: str,
    visual_metaphor: str,
    include_repo_name: bool,
    additional_instructions: str = "",
    prompt_template: Optional[str] = None,
    template_vars: Optional[dict] = None,
) -> str:
    """Build the image generation prompt."""
    template = prompt_template or ImageGenerator.DEFAULT_TEMPLATE

    text_instructions = (
        f'Include "{project_name}" as stylized text.'
        if include_repo_name
        else "No text, no letters, no words."
    )

    # Built-in template variables
    built_in_vars = {
        "PROJECT_NAME": project_name,
        "STYLE": style,
        "ICON_COLORS": ", ".join(icon_colors),
        "KEY_COLOR": key_color,
        "VISUAL_METAPHOR": visual_metaphor,
        "TEXT_INSTRUCTIONS": text_instructions,
    }

    # Merge with CLI-provided template vars (CLI vars override built-in)
    if template_vars:
        built_in_vars.update(template_vars)

    prompt = template.format(**built_in_vars)

    if additional_instructions:
        prompt = f"{prompt}\n{additional_instructions}"

    return prompt
