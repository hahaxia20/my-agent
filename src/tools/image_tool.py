"""Image execution tool for local image inspection and multimodal analysis."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI
from PIL import Image

from src.config import PROJECT_ROOT, get_settings_safe
from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ImageTool(BaseTool):
    """Runtime image tool used by the lightweight image skill."""

    def __init__(self):
        super().__init__()
        self.name = "image_tool"
        self.description = (
            "Execute local image operations inside the project workspace, including inspect and analyze. "
            "Use this tool for uploaded PNG/JPG/JPEG files instead of guessing image content."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Image operation: inspect or analyze",
                },
                "input_path": {
                    "type": "string",
                    "description": "Input image path relative to the project root or an absolute path inside the project root",
                },
                "prompt": {
                    "type": "string",
                    "description": "Optional analysis instruction for the model",
                },
                "model": {
                    "type": "string",
                    "description": "Optional multimodal model override",
                },
            },
            "required": ["operation", "input_path"],
        }
        self.timeout = 120
        self.retry_count = 1
        self.supported_suffixes = {".png", ".jpg", ".jpeg"}

    def _ensure_within_project(self, path: Path) -> Path:
        resolved = path.resolve()
        project_root = PROJECT_ROOT.resolve()
        if not resolved.is_relative_to(project_root):
            raise ValueError(f"path must stay within project root: {project_root}")
        return resolved

    def _resolve_input_file(self, raw_path: str) -> Path:
        if not raw_path:
            raise ValueError("input_path is required")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        resolved = self._ensure_within_project(candidate)
        if not resolved.exists():
            raise FileNotFoundError(f"input file not found: {resolved}")
        if resolved.suffix.lower() not in self.supported_suffixes:
            raise ValueError(f"input file must be one of: {sorted(self.supported_suffixes)}")
        return resolved

    def _inspect_sync(self, input_path: str) -> Dict[str, Any]:
        image_path = self._resolve_input_file(input_path)
        with Image.open(image_path) as image:
            width, height = image.size
            return {
                "success": True,
                "operation": "inspect",
                "input_path": str(image_path.relative_to(PROJECT_ROOT)),
                "format": image.format,
                "mode": image.mode,
                "width": width,
                "height": height,
                "has_transparency": image.mode in {"RGBA", "LA"} or "transparency" in image.info,
                "metadata": {str(k): str(v) for k, v in image.info.items()},
            }

    def _guess_mime_type(self, image_path: Path) -> str:
        suffix = image_path.suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        return "application/octet-stream"

    def _analyze_sync(self, input_path: str, prompt: Optional[str], model: Optional[str]) -> Dict[str, Any]:
        image_path = self._resolve_input_file(input_path)
        settings = get_settings_safe()
        mime_type = self._guess_mime_type(image_path)
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime_type};base64,{image_b64}"
        client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.API_BASE_URL)
        model_name = model or getattr(settings, "IMAGE_MODEL", None) or "qwen-vl-max"
        user_prompt = prompt or (
            "Analyze this image carefully. Describe the main content, visible text, layout, "
            "and any actionable details in a structured way."
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=0.2,
            )
        except Exception as exc:
            message = str(exc)
            if "Unexpected item type in content" in message or "invalid_parameter_error" in message:
                raise RuntimeError(
                    f"image analysis failed with model '{model_name}'. "
                    "The current model likely does not support image input. "
                    "Try qwen-vl-max or set IMAGE_MODEL=qwen-vl-max."
                ) from exc
            raise
        message = response.choices[0].message.content if response.choices else ""
        usage = getattr(response, "usage", None)
        usage_dict = usage.model_dump() if usage and hasattr(usage, "model_dump") else None

        return {
            "success": True,
            "operation": "analyze",
            "input_path": str(image_path.relative_to(PROJECT_ROOT)),
            "model": model_name,
            "prompt": user_prompt,
            "analysis": message,
            "usage": usage_dict,
        }

    async def execute(
        self,
        operation: str,
        input_path: str,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        operation = (operation or "").strip().lower()
        if not operation:
            return {"success": False, "error": "operation is required"}

        try:
            if operation == "inspect":
                return await asyncio.to_thread(self._inspect_sync, input_path)
            if operation == "analyze":
                return await asyncio.to_thread(self._analyze_sync, input_path, prompt, model)
            return {"success": False, "error": "unsupported operation; use inspect or analyze"}
        except Exception as exc:
            logger.error("image_tool failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "operation": operation,
                "error": str(exc),
            }

