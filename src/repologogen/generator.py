"""Image generation and metadata helpers using OpenAI-compatible APIs."""

import base64
import json
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx

from repologogen.config import get_api_key


class ImageGeneratorError(Exception):
    """Raised when image generation fails."""

    pass


class ImageGenerator:
    """Client for generating images via OpenAI-compatible APIs."""

    DEFAULT_TEMPLATE = (
        "A {STYLE} logo for {PROJECT_NAME}.{PROJECT_DESCRIPTION} {VISUAL_METAPHOR}.\n"
        "Clean vector style. Icon colors from: {ICON_COLORS}.\n"
        "Pure {KEY_COLOR} background only. Do not use similar tones in the design.\n"
        "{TEXT_INSTRUCTIONS} Single centered icon, geometric shapes. "
        "The icon must fill the entire canvas edge-to-edge with minimal padding. "
        "No empty space around the design. Scalable to small sizes."
    )

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 120.0,
        project_path: Path | None = None,
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
    ) -> dict[str, Any]:
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


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _fallback_metadata(
    project_name: str,
    project_type: str,
    project_description: str = "",
) -> dict[str, Any]:
    description = (
        project_description.strip()
        or f"{project_name} is a {project_type} project.".replace(" unknown ", " ")
    )
    title = project_name
    return {
        "title": title,
        "short_description": description,
        "social_title": title,
        "social_description": description,
        "keywords": [
            value for value in [project_name.lower(), project_type] if value and value != "unknown"
        ],
    }


def _normalize_metadata(
    payload: dict[str, Any],
    project_name: str,
    project_type: str,
    project_description: str = "",
) -> dict[str, Any]:
    fallback = _fallback_metadata(project_name, project_type, project_description)
    keywords = payload.get("keywords", fallback["keywords"])

    if isinstance(keywords, str):
        keywords = [item.strip() for item in keywords.split(",") if item.strip()]
    elif isinstance(keywords, list):
        keywords = [str(item).strip() for item in keywords if str(item).strip()]
    else:
        keywords = fallback["keywords"]

    return {
        "title": str(payload.get("title") or fallback["title"]),
        "short_description": str(payload.get("short_description") or fallback["short_description"]),
        "social_title": str(
            payload.get("social_title") or payload.get("title") or fallback["title"]
        ),
        "social_description": str(
            payload.get("social_description")
            or payload.get("short_description")
            or fallback["short_description"]
        ),
        "keywords": keywords or fallback["keywords"],
    }


def build_prompt(
    project_name: str,
    style: str,
    icon_colors: list[str] | str,
    key_color: str,
    visual_metaphor: str,
    include_repo_name: bool,
    additional_instructions: str = "",
    prompt_template: str | None = None,
    template_vars: dict[str, str] | None = None,
    project_description: str = "",
) -> str:
    """Build the image generation prompt."""
    template = prompt_template or ImageGenerator.DEFAULT_TEMPLATE

    text_instructions = (
        f'Include "{project_name}" as stylized text.'
        if include_repo_name
        else "No text, no letters, no words."
    )

    # Format description: " A tool that does X." or empty
    desc_fragment = f" {project_description.rstrip('.')}." if project_description else ""

    # Built-in template variables
    colors_str = icon_colors if isinstance(icon_colors, str) else ", ".join(icon_colors)
    built_in_vars = {
        "PROJECT_NAME": project_name,
        "STYLE": style,
        "ICON_COLORS": colors_str,
        "KEY_COLOR": key_color,
        "VISUAL_METAPHOR": visual_metaphor,
        "TEXT_INSTRUCTIONS": text_instructions,
        "PROJECT_DESCRIPTION": desc_fragment,
    }

    # Merge with CLI-provided template vars (CLI vars override built-in)
    if template_vars:
        built_in_vars.update(template_vars)

    # Pre-resolve placeholders in config values (e.g. {PROJECT_NAME} in style)
    # so that template.format() produces a fully resolved prompt
    for key, value in built_in_vars.items():
        if isinstance(value, str) and "{" in value:
            with suppress(KeyError, ValueError):
                built_in_vars[key] = value.format(**built_in_vars)

    prompt = template.format(**built_in_vars)

    if additional_instructions:
        prompt = f"{prompt}\n{additional_instructions}"

    return prompt


def digest_readme(
    readme_content: str,
    api_key: str,
    text_model: str = "google/gemini-3-flash-preview",
    base_url: str = "https://openrouter.ai/api/v1",
) -> str:
    """Send README content to an LLM to produce a concise project description.

    Args:
        readme_content: Raw README file content
        api_key: OpenRouter API key
        text_model: Model to use for text processing
        base_url: API base URL

    Returns:
        A concise project description, or empty string on any error
    """
    if not readme_content.strip():
        return ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": text_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a project analyst. Given a README file, produce a single "
                    "concise sentence (under 100 words) describing what this project does "
                    "and what it's for. Focus on the core purpose. No markdown formatting."
                ),
            },
            {"role": "user", "content": readme_content},
        ],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
            content: str = data["choices"][0]["message"]["content"]
            return content.strip()
    except Exception:
        return ""


def extract_repo_metadata(
    readme_content: str,
    api_key: str,
    project_name: str,
    project_type: str,
    *,
    project_description: str = "",
    text_model: str = "google/gemini-3-flash-preview",
    base_url: str = "https://openrouter.ai/api/v1",
) -> dict[str, Any]:
    """Extract minimal reusable metadata fields for bundle manifests."""
    if not readme_content.strip():
        return _fallback_metadata(project_name, project_type, project_description)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": text_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an SEO metadata editor for software repositories. "
                    "Return valid JSON only "
                    'with keys: "title", "short_description", "social_title", '
                    '"social_description", and "keywords". '
                    '"keywords" must be an array of short strings. '
                    "Descriptions should be concise, factual, and suitable for a "
                    "repo landing page."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Project name: {project_name}\n"
                    f"Project type: {project_type}\n"
                    f"Known summary: {project_description or 'none'}\n\n"
                    f"README:\n{readme_content}"
                ),
            },
        ],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
            content: str = data["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise ValueError("Metadata response must be a JSON object")
            return _normalize_metadata(
                parsed,
                project_name,
                project_type,
                project_description,
            )
    except Exception:
        return _fallback_metadata(project_name, project_type, project_description)


def refine_prompt(
    raw_prompt: str,
    target_model: str,
    api_key: str,
    text_model: str = "google/gemini-3-flash-preview",
    base_url: str = "https://openrouter.ai/api/v1",
) -> str:
    """Refine an image-generation prompt via LLM to remove redundancy and contradictions.

    Args:
        raw_prompt: The assembled image-generation prompt
        target_model: The image model the prompt will be sent to
        api_key: OpenRouter API key
        text_model: Model to use for text processing
        base_url: API base URL

    Returns:
        Refined prompt, or original on any error
    """
    if not raw_prompt.strip():
        return raw_prompt

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": text_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are an image-prompt editor. The following prompt will be sent to "
                    f"the '{target_model}' image model. Your job:\n"
                    "- Remove redundant or duplicate instructions\n"
                    "- Resolve contradictions (keep the more specific directive)\n"
                    "- Tighten verbose language into concise directives\n"
                    "- Preserve ALL hex color codes exactly as given\n"
                    "- Preserve the core creative intent and style\n"
                    "- Do NOT add new concepts, styles, or instructions\n"
                    "- Return ONLY the refined prompt text, nothing else"
                ),
            },
            {"role": "user", "content": raw_prompt},
        ],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
            content: str = data["choices"][0]["message"]["content"]
            refined = content.strip()
            return refined if refined else raw_prompt
    except Exception:
        return raw_prompt
