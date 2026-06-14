"""
PDF parser using pdfplumber (native text) with a Tesseract OCR fallback
for scanned pages. Also renders each page to an image for the UI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import pdfplumber

from app.config import settings
from app.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage, ParserError
from app.parsers.image_parser import ImageParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PDFParser(BaseParser):
    """Extract text + images from PDFs."""

    supported_extensions = [".pdf"]
    parser_name = "pdf"

    def __init__(self) -> None:
        self._image_parser = ImageParser()

    async def parse(
        self,
        file_path: str,
        *,
        max_pages: Optional[int] = None,
    ) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"PDF file not found: {file_path}")
        if not path.suffix.lower() == ".pdf":
            raise ParserError(f"File is not a PDF: {file_path}")

        cap = max_pages or settings.MAX_PAGES_PER_DOC
        doc = ParsedDocument(
            filename=path.name,
            file_path=str(path.absolute()),
            mime_type="application/pdf",
            parser_used=self.parser_name,
        )

        try:
            loop = asyncio.get_running_loop()
            # pdfplumber is sync → run in threadpool
            pages_data = await loop.run_in_executor(
                None, self._parse_sync, str(path), cap
            )
        except Exception as exc:
            logger.exception("PDF parsing failed: %s", file_path)
            doc.error = str(exc)
            return doc

        doc.pages = pages_data
        doc.page_count = len(pages_data)
        doc.aggregate_text()
        doc.metadata = {
            "source": "pdfplumber",
            "ocr_fallback_used": any(
                p.metadata.get("ocr_fallback") for p in pages_data
            ),
        }
        logger.info("Parsed PDF %s: %d pages", path.name, doc.page_count)
        return doc

    # ============================================================
    # Sync helper (runs in threadpool)
    # ============================================================
    def _parse_sync(self, file_path: str, max_pages: int) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                text = (page.extract_text() or "").strip()
                ocr_fallback = False

                # If native extraction is weak, fall back to OCR
                if len(text) < 30:
                    logger.debug("Page %d has little native text; trying OCR", i + 1)
                    text = self._ocr_page(file_path, i + 1)
                    ocr_fallback = True

                # Render page to image
                image_path = self._render_page(file_path, i + 1)

                page_obj = ParsedPage(
                    page_number=i + 1,
                    text=text,
                    image_path=image_path,
                    metadata={"ocr_fallback": ocr_fallback, "width": page.width, "height": page.height},
                )
                pages.append(page_obj)
        return pages

    # ============================================================
    # Helpers
    # ============================================================
    def _ocr_page(self, pdf_path: str, page_num: int) -> str:
        """Run Tesseract OCR on a single rendered PDF page."""
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(
                pdf_path, dpi=200, first_page=page_num, last_page=page_num
            )
            if not images:
                return ""
            return pytesseract.image_to_string(images[0]).strip()
        except Exception as exc:  # pragma: no cover
            logger.warning("OCR fallback failed for page %d: %s", page_num, exc)
            return ""

    def _render_page(self, pdf_path: str, page_num: int) -> Optional[str]:
        """Render a page to a PNG and save it locally. Returns the path."""
        try:
            from pdf2image import convert_from_path

            out_dir = Path(settings.LOCAL_STORAGE_PATH) / "images"
            out_dir.mkdir(parents=True, exist_ok=True)

            base = Path(pdf_path).stem
            out_path = out_dir / f"{base}_p{page_num}.png"
            if out_path.exists():
                return str(out_path)

            images = convert_from_path(
                pdf_path, dpi=150, first_page=page_num, last_page=page_num
            )
            if images:
                images[0].save(out_path, "PNG")
                return str(out_path)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to render page %d: %s", page_num, exc)
        return None
