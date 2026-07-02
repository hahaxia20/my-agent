"""PDF execution tool for runtime PDF operations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
from pypdf import PdfReader, PdfWriter

from src.config import PROJECT_ROOT
from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


class PdfTool(BaseTool):
    """Runtime PDF tool used by the lightweight pdf skill."""

    def __init__(self):
        super().__init__()
        self.name = "pdf_tool"
        self.description = (
            "Execute PDF operations inside the project workspace, including inspect, extract_text, "
            "extract_tables, merge, and split. Use this tool instead of describing PDF steps from memory."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "PDF operation: inspect, extract_text, extract_tables, merge, or split",
                },
                "input_path": {
                    "type": "string",
                    "description": "Input PDF path relative to the project root or an absolute path inside the project root",
                },
                "input_paths": {
                    "type": "array",
                    "description": "Input PDF paths for merge operations",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional output file or output directory path inside the project root",
                },
                "start_page": {
                    "type": "integer",
                    "description": "1-based start page for extraction or split operations",
                    "default": 1,
                },
                "end_page": {
                    "type": "integer",
                    "description": "1-based end page for extraction or split operations",
                },
                "password": {
                    "type": "string",
                    "description": "Optional password for encrypted PDFs",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Safety guard for extraction size",
                    "default": 20,
                },
            },
            "required": ["operation"],
        }
        self.timeout = 120
        self.retry_count = 1
        self.output_root = PROJECT_ROOT / "data" / "pdf_outputs"

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
        if resolved.suffix.lower() != ".pdf":
            raise ValueError(f"input file must be a PDF: {resolved}")
        return resolved

    def _resolve_output_path(self, raw_path: Optional[str], default_name: str, is_dir: bool = False) -> Path:
        if raw_path:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
        else:
            candidate = self.output_root / default_name
        resolved = self._ensure_within_project(candidate)
        if is_dir:
            resolved.mkdir(parents=True, exist_ok=True)
        else:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _open_reader(self, pdf_path: Path, password: Optional[str] = None) -> PdfReader:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted and password:
            reader.decrypt(password)
        return reader

    def _normalized_page_range(
        self,
        page_count: int,
        start_page: Optional[int],
        end_page: Optional[int],
        max_pages: int,
    ) -> range:
        start = max(1, start_page or 1)
        end = min(page_count, end_page or page_count)
        if end < start:
            raise ValueError("end_page must be greater than or equal to start_page")
        if (end - start + 1) > max_pages:
            raise ValueError(f"requested page range exceeds max_pages={max_pages}")
        return range(start - 1, end)

    def _inspect_sync(self, input_path: str, password: Optional[str]) -> Dict[str, Any]:
        pdf_path = self._resolve_input_file(input_path)
        reader = self._open_reader(pdf_path, password)
        field_map = reader.get_fields() or {}
        metadata = reader.metadata or {}
        return {
            "success": True,
            "operation": "inspect",
            "input_path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "page_count": len(reader.pages),
            "is_encrypted": reader.is_encrypted,
            "has_fillable_fields": bool(field_map),
            "field_ids": list(field_map.keys())[:100],
            "metadata": {str(k): str(v) for k, v in metadata.items()},
        }

    def _extract_text_sync(
        self,
        input_path: str,
        start_page: Optional[int],
        end_page: Optional[int],
        max_pages: int,
    ) -> Dict[str, Any]:
        pdf_path = self._resolve_input_file(input_path)
        pages_out: List[Dict[str, Any]] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            page_range = self._normalized_page_range(len(pdf.pages), start_page, end_page, max_pages)
            for page_index in page_range:
                text = (pdf.pages[page_index].extract_text() or "").strip()
                pages_out.append(
                    {
                        "page": page_index + 1,
                        "text": text,
                        "char_count": len(text),
                    }
                )
        combined = "\n\n".join(
            f"[Page {item['page']}]\n{item['text']}" for item in pages_out if item["text"]
        )
        return {
            "success": True,
            "operation": "extract_text",
            "input_path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "pages": pages_out,
            "combined_text": combined,
        }

    def _extract_tables_sync(
        self,
        input_path: str,
        start_page: Optional[int],
        end_page: Optional[int],
        max_pages: int,
    ) -> Dict[str, Any]:
        pdf_path = self._resolve_input_file(input_path)
        page_tables: List[Dict[str, Any]] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            page_range = self._normalized_page_range(len(pdf.pages), start_page, end_page, max_pages)
            for page_index in page_range:
                tables = pdf.pages[page_index].extract_tables() or []
                page_tables.append(
                    {
                        "page": page_index + 1,
                        "table_count": len(tables),
                        "tables": tables,
                    }
                )
        return {
            "success": True,
            "operation": "extract_tables",
            "input_path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "pages": page_tables,
        }

    def _merge_sync(self, input_paths: List[str], output_path: Optional[str]) -> Dict[str, Any]:
        if not input_paths or len(input_paths) < 2:
            raise ValueError("merge requires at least two input_paths")
        resolved_inputs = [self._resolve_input_file(path) for path in input_paths]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self._resolve_output_path(output_path, f"merged_{timestamp}.pdf")

        writer = PdfWriter()
        total_pages = 0
        for pdf_path in resolved_inputs:
            reader = PdfReader(str(pdf_path))
            for page in reader.pages:
                writer.add_page(page)
                total_pages += 1

        with output_file.open("wb") as fh:
            writer.write(fh)

        return {
            "success": True,
            "operation": "merge",
            "input_paths": [str(path.relative_to(PROJECT_ROOT)) for path in resolved_inputs],
            "output_path": str(output_file.relative_to(PROJECT_ROOT)),
            "page_count": total_pages,
        }

    def _split_sync(
        self,
        input_path: str,
        output_path: Optional[str],
        start_page: Optional[int],
        end_page: Optional[int],
        max_pages: int,
    ) -> Dict[str, Any]:
        pdf_path = self._resolve_input_file(input_path)
        reader = PdfReader(str(pdf_path))
        page_range = self._normalized_page_range(len(reader.pages), start_page, end_page, max_pages)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = self._resolve_output_path(output_path, f"split_{timestamp}", is_dir=True)

        outputs: List[str] = []
        for page_index in page_range:
            writer = PdfWriter()
            writer.add_page(reader.pages[page_index])
            out_file = output_dir / f"page_{page_index + 1}.pdf"
            with out_file.open("wb") as fh:
                writer.write(fh)
            outputs.append(str(out_file.relative_to(PROJECT_ROOT)))

        return {
            "success": True,
            "operation": "split",
            "input_path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "output_dir": str(output_dir.relative_to(PROJECT_ROOT)),
            "outputs": outputs,
        }

    async def execute(
        self,
        operation: str,
        input_path: Optional[str] = None,
        input_paths: Optional[List[str]] = None,
        output_path: Optional[str] = None,
        start_page: Optional[int] = 1,
        end_page: Optional[int] = None,
        password: Optional[str] = None,
        max_pages: int = 20,
        **kwargs,
    ) -> Dict[str, Any]:
        operation = (operation or "").strip().lower()
        if not operation:
            return {"success": False, "error": "operation is required"}

        try:
            if operation == "inspect":
                return await asyncio.to_thread(self._inspect_sync, input_path, password)
            if operation == "extract_text":
                return await asyncio.to_thread(self._extract_text_sync, input_path, start_page, end_page, max_pages)
            if operation == "extract_tables":
                return await asyncio.to_thread(self._extract_tables_sync, input_path, start_page, end_page, max_pages)
            if operation == "merge":
                return await asyncio.to_thread(self._merge_sync, input_paths or [], output_path)
            if operation == "split":
                return await asyncio.to_thread(self._split_sync, input_path, output_path, start_page, end_page, max_pages)
            return {
                "success": False,
                "error": "unsupported operation; use inspect, extract_text, extract_tables, merge, or split",
            }
        except Exception as exc:
            logger.error("pdf_tool failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "operation": operation,
                "error": str(exc),
            }
