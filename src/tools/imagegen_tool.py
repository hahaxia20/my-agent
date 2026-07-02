"""Image generation tool for creating raster assets inside the workspace."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
import requests
from openai import OpenAI

from src.config import PROJECT_ROOT, get_settings_safe
from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ImageGenTool(BaseTool):
    """Generate bitmap images and save them inside the project workspace."""

    def __init__(self):
        super().__init__()
        self.name = "imagegen_tool"
        self.description = (
            "Generate raster images from prompts and save them under the project workspace. "
            "Use this tool for posters, illustrations, covers, social-media cards, and other new image assets."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The final image-generation prompt",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional output path relative to the project root; defaults to data/uploads/images/...png",
                },
                "model": {
                    "type": "string",
                    "description": "Optional image-generation model override",
                },
                "size": {
                    "type": "string",
                    "description": "Optional image size such as 1024x1024, 1536x1024, or 1024x1536",
                },
                "quality": {
                    "type": "string",
                    "description": "Optional quality hint such as low, medium, high, auto, or provider-specific values",
                },
                "background": {
                    "type": "string",
                    "description": "Optional background hint for providers that support it",
                },
            },
            "required": ["prompt"],
        }
        self.timeout = 180
        self.retry_count = 0

    def _ensure_within_project(self, path: Path) -> Path:
        resolved = path.resolve()
        project_root = PROJECT_ROOT.resolve()
        if not resolved.is_relative_to(project_root):
            raise ValueError(f"path must stay within project root: {project_root}")
        return resolved

    def _slugify(self, text: str, max_length: int = 48) -> str:
        compact = re.sub(r"\s+", "-", text.strip().lower())
        compact = re.sub(r"[^a-z0-9一-鿿\-]+", "-", compact)
        compact = re.sub(r"-+", "-", compact).strip("-")
        return (compact or "image")[:max_length].strip("-") or "image"

    def _default_output_dir(self) -> Path:
        settings = get_settings_safe()
        configured = getattr(settings, "IMAGEGEN_OUTPUT_DIR", "data/uploads/images")
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return self._ensure_within_project(candidate)

    def _resolve_output_path(self, output_path: Optional[str], prompt: str) -> Path:
        if output_path:
            candidate = Path(output_path)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{self._slugify(prompt)}.png"
            candidate = self._default_output_dir() / filename

        resolved = self._ensure_within_project(candidate)
        if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            resolved = resolved.with_suffix(".png")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _new_requests_session(self) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        return session

    def _download_binary(self, url: str) -> bytes:
        with self._new_requests_session() as session:
            response = session.get(url, timeout=120)
            response.raise_for_status()
            return response.content

    def _extract_image_bytes(self, payload: Any, output_path: Path) -> bytes:
        data = payload.data if hasattr(payload, "data") else payload.get("data")
        if not data:
            raise RuntimeError("image generation returned no data")

        first = data[0]
        if hasattr(first, "b64_json") and first.b64_json:
            return base64.b64decode(first.b64_json)
        if isinstance(first, dict) and first.get("b64_json"):
            return base64.b64decode(first["b64_json"])

        url = getattr(first, "url", None)
        if not url and isinstance(first, dict):
            url = first.get("url")
        if url:
            return self._download_binary(url)

        raise RuntimeError(
            "image generation returned an unsupported payload format; "
            f"cannot save result to {output_path}"
        )

    def _is_dashscope_native(self, api_base_url: str) -> bool:
        parsed = urlparse(api_base_url)
        return parsed.netloc.endswith("dashscope.aliyuncs.com")

    def _build_dashscope_endpoint(self, api_base_url: str) -> str:
        parsed = urlparse(api_base_url)
        return f"{parsed.scheme}://{parsed.netloc}/api/v1/services/aigc/text2image/image-synthesis"

    def _build_dashscope_task_endpoint(self, api_base_url: str, task_id: str) -> str:
        parsed = urlparse(api_base_url)
        return f"{parsed.scheme}://{parsed.netloc}/api/v1/tasks/{task_id}"

    def _normalize_dashscope_size(self, size: Optional[str]) -> Optional[str]:
        if not size:
            return None
        normalized = str(size).lower().replace("x", "*")
        parts = normalized.split("*")
        if len(parts) != 2:
            return normalized
        try:
            width = int(parts[0])
            height = int(parts[1])
        except ValueError:
            return normalized

        max_edge = 1440
        min_edge = 512
        scale = min(1.0, max_edge / max(width, height))
        width = max(min_edge, int(width * scale))
        height = max(min_edge, int(height * scale))
        return f"{width}*{height}"

    def _extract_dashscope_result_url(self, payload: Dict[str, Any]) -> Optional[str]:
        output = payload.get("output") or {}
        results = output.get("results") or []
        if results and isinstance(results[0], dict):
            if results[0].get("url"):
                return results[0]["url"]
        if output.get("result_url"):
            return output["result_url"]
        if output.get("url"):
            return output["url"]
        return None

    def _generate_via_dashscope(
        self,
        api_key: str,
        api_base_url: str,
        model_name: str,
        prompt: str,
        target_path: Path,
        size: Optional[str],
    ) -> Dict[str, Any]:
        endpoint = self._build_dashscope_endpoint(api_base_url)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload: Dict[str, Any] = {
            "model": model_name,
            "input": {"prompt": prompt.strip()},
            "parameters": {},
        }
        normalized_size = self._normalize_dashscope_size(size)
        if normalized_size:
            payload["parameters"]["size"] = normalized_size

        logger.info("imagegen_tool dashscope request model=%s endpoint=%s output=%s", model_name, endpoint, target_path)

        with self._new_requests_session() as session:
            response = session.post(endpoint, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            created = response.json()

            direct_url = self._extract_dashscope_result_url(created)
            if direct_url:
                target_path.write_bytes(self._download_binary(direct_url))
                return {
                    "success": True,
                    "operation": "generate",
                    "provider": "dashscope",
                    "model": model_name,
                    "prompt": prompt,
                    "output_path": str(target_path.relative_to(PROJECT_ROOT)),
                    "size": size,
                    "task_id": None,
                    "result_url": direct_url,
                }

            output = created.get("output") or {}
            task_id = output.get("task_id") or output.get("taskId")
            if not task_id:
                raise RuntimeError(f"dashscope image generation did not return task_id: {created}")

            task_endpoint = self._build_dashscope_task_endpoint(api_base_url, task_id)
            deadline = time.time() + self.timeout
            last_payload: Dict[str, Any] = created

            while time.time() < deadline:
                poll_response = session.get(task_endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
                poll_response.raise_for_status()
                last_payload = poll_response.json()
                task_output = last_payload.get("output") or {}
                task_status = (
                    task_output.get("task_status")
                    or task_output.get("taskStatus")
                    or last_payload.get("task_status")
                    or last_payload.get("taskStatus")
                    or ""
                )
                task_status = str(task_status).upper()

                if task_status == "SUCCEEDED":
                    result_url = self._extract_dashscope_result_url(last_payload)
                    if not result_url:
                        raise RuntimeError(f"dashscope task succeeded but no result url was returned: {last_payload}")
                    target_path.write_bytes(self._download_binary(result_url))
                    return {
                        "success": True,
                        "operation": "generate",
                        "provider": "dashscope",
                        "model": model_name,
                        "prompt": prompt,
                        "output_path": str(target_path.relative_to(PROJECT_ROOT)),
                        "size": size,
                        "task_id": task_id,
                        "result_url": result_url,
                    }

                if task_status in {"FAILED", "FAIL", "CANCELED", "CANCELLED"}:
                    message = last_payload.get("message") or task_output.get("message") or last_payload
                    raise RuntimeError(f"dashscope task failed: status={task_status}, detail={message}")

                time.sleep(3)

        raise TimeoutError(f"dashscope image generation timed out waiting for task result: {task_id}")

    def _generate_via_openai_compatible(
        self,
        api_key: str,
        api_base_url: str,
        model_name: str,
        prompt: str,
        target_path: Path,
        size: Optional[str],
        quality: Optional[str],
        background: Optional[str],
    ) -> Dict[str, Any]:
        http_client = httpx.Client(trust_env=False, timeout=120)
        client = OpenAI(api_key=api_key, base_url=api_base_url, http_client=http_client)

        request_kwargs: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt.strip(),
            "n": 1,
        }
        if size:
            request_kwargs["size"] = size
        if quality:
            request_kwargs["quality"] = quality
        if background:
            request_kwargs["background"] = background

        logger.info("imagegen_tool openai-compatible request model=%s output=%s", model_name, target_path)

        try:
            response = client.images.generate(**request_kwargs)
        finally:
            http_client.close()

        image_bytes = self._extract_image_bytes(response, target_path)
        target_path.write_bytes(image_bytes)

        revised_prompt = None
        data = response.data if hasattr(response, "data") else response.get("data")
        if data:
            first = data[0]
            revised_prompt = getattr(first, "revised_prompt", None)
            if revised_prompt is None and isinstance(first, dict):
                revised_prompt = first.get("revised_prompt")

        return {
            "success": True,
            "operation": "generate",
            "provider": "openai-compatible",
            "model": model_name,
            "prompt": prompt,
            "revised_prompt": revised_prompt,
            "output_path": str(target_path.relative_to(PROJECT_ROOT)),
            "size": size,
            "quality": quality,
            "background": background,
        }

    def _generate_sync(
        self,
        prompt: str,
        output_path: Optional[str],
        model: Optional[str],
        size: Optional[str],
        quality: Optional[str],
        background: Optional[str],
    ) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            raise ValueError("prompt is required")

        settings = get_settings_safe()
        api_key = settings.OPENAI_API_KEY
        api_base_url = settings.API_BASE_URL
        model_name = model or getattr(settings, "IMAGEGEN_MODEL", None) or "wanx2.1-t2i-plus"
        target_path = self._resolve_output_path(output_path, prompt)

        try:
            if self._is_dashscope_native(api_base_url):
                return self._generate_via_dashscope(
                    api_key=api_key,
                    api_base_url=api_base_url,
                    model_name=model_name,
                    prompt=prompt,
                    target_path=target_path,
                    size=size,
                )

            return self._generate_via_openai_compatible(
                api_key=api_key,
                api_base_url=api_base_url,
                model_name=model_name,
                prompt=prompt,
                target_path=target_path,
                size=size,
                quality=quality,
                background=background,
            )
        except Exception as exc:
            raise RuntimeError(
                f"image generation failed with model '{model_name}'. "
                "Check whether IMAGEGEN_MODEL points to a provider-supported image model, "
                "whether API_BASE_URL matches the provider, and whether local proxy settings are invalid. "
                f"Original error: {exc}"
            ) from exc

    async def execute(
        self,
        prompt: str,
        output_path: Optional[str] = None,
        model: Optional[str] = None,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        background: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            return await asyncio.to_thread(
                self._generate_sync,
                prompt,
                output_path,
                model,
                size,
                quality,
                background,
            )
        except Exception as exc:
            logger.error("imagegen_tool failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "operation": "generate",
                "error": str(exc),
            }
