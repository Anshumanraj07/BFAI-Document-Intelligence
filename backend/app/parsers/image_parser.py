"""
Image parser — converts images (PNG/JPG/JPEG) to text via Tesseract.
Can also convert PDF pages to images for OCR-only scenarios.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import pytesseract
from PIL import Image

from app.config import settings
from app.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage, ParserError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ImageParser(BaseParser):
    """OCR for standalone images and PDF-to-image conversion."""

    supported_extensions = [".png", ".jpg", ".jpeg"]
    parser_name = "image"

    async def parse(
        self,
        file_path: str,
        *,
        max_pages: Optional[int] = None,
    ) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"Image file not found: {file_path}")

        doc = ParsedDocument(
            filename=path.name,
            file_path=str(path.absolute()),
            mime_type=f"image/{path.suffix.lstrip('.').lower()}",
            parser_used=self.parser_name,
        )

        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(None, self._ocr_image, str(path))
        except Exception as exc:
            logger.exception("Image OCR failed: %s", file_path)
            doc.error = str(exc)
            return doc

        page = ParsedPage(
            page_number=1,
            text=text,
            image_path=str(path.absolute()),
            metadata={"ocr_engine": "tesseract"},
        )
        doc.pages = [page]
        doc.page_count = 1
        doc.aggregate_text()
        logger.info("OCR'd image %s (%d chars)", path.name, len(text))
        return doc

    def _ocr_image(self, image_path: str) -> str:
        """Run Tesseract on a single image file (sync, runs in threadpool)."""
        img = Image.open(image_path)
        # Convert to RGB if necessary (e.g., RGBA → RGB)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return pytesseract.image_to_string(img).strip()

    async def pdf_to_images(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        dpi: int = 200,
        max_pages: Optional[int] = None,
    ) -> List[str]:
        """
        Convert each page of a PDF to a PNG image and return the file paths.
        """
        from pdf2image import convert_from_path

        out_dir = Path(output_dir or (Path(settings.LOCAL_STORAGE_PATH) / "images"))
        out_dir.mkdir(parents=True, exist_ok=True)
        cap = max_pages or settings.MAX_PAGES_PER_DOC

        loop = asyncio.get_running_loop()
        images = await loop.run_in_executor(
            None, lambda: convert_from_path(pdf_path, dpi=dpi, last_page=cap)
        )

        paths: List[str] = []
        base = Path(pdf_path).stem
        for i, img in enumerate(images, start=1):
            out_path = out_dir / f"{base}_p{i}.png"
            img.save(out_path, "PNG")
            paths.append(str(out_path))
        logger.info("Converted %s to %d images", pdf_path, len(paths))
        return paths
