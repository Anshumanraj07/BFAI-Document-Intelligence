"""
Specialised OCR for handwritten documents.

Tesseract's LSTM engine has a `--oem 1` mode and the `script/Latin`
traineddata is reasonably good for clean handwriting. For production
accuracy, swap in TrOCR, EasyOCR, or a cloud Vision API.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image, ImageOps

from app.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage, ParserError
from app.parsers.image_parser import ImageParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Tesseract config tuned for handwriting:
#   --oem 1   → LSTM engine
#   --psm 6   → assume a single uniform block of text
_HANDWRITING_CONFIG = "--oem 1 --psm 6"


class HandwrittenParser(BaseParser):
    """OCR pipeline optimised for handwritten content."""

    supported_extensions = [".png", ".jpg", ".jpeg", ".pdf"]
    parser_name = "handwritten"

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
            raise ParserError(f"File not found: {file_path}")

        doc = ParsedDocument(
            filename=path.name,
            file_path=str(path.absolute()),
            mime_type="handwriting",
            parser_used=self.parser_name,
        )

        try:
            if path.suffix.lower() == ".pdf":
                # Render PDF pages first, then OCR each
                loop = asyncio.get_running_loop()
                image_paths = await self._image_parser.pdf_to_images(
                    str(path), max_pages=max_pages
                )
                pages = []
                for i, img_path in enumerate(image_paths, start=1):
                    text = await loop.run_in_executor(
                        None, self._ocr_handwritten, img_path
                    )
                    pages.append(ParsedPage(
                        page_number=i,
                        text=text,
                        image_path=img_path,
                        has_handwriting=True,
                        metadata={"ocr_engine": "tesseract-lstm"},
                    ))
            else:
                loop = asyncio.get_running_loop()
                text = await loop.run_in_executor(
                    None, self._ocr_handwritten, str(path)
                )
                pages = [ParsedPage(
                    page_number=1,
                    text=text,
                    image_path=str(path.absolute()),
                    has_handwriting=True,
                    metadata={"ocr_engine": "tesseract-lstm"},
                )]
        except Exception as exc:
            logger.exception("Handwritten OCR failed: %s", file_path)
            doc.error = str(exc)
            return doc

        doc.pages = pages
        doc.page_count = len(pages)
        doc.aggregate_text()
        logger.info("Handwritten OCR complete: %s (%d pages)", path.name, doc.page_count)
        return doc

    def _ocr_handwritten(self, image_path: str) -> str:
        """Run Tesseract with handwriting-tuned config (sync, in threadpool)."""
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Light preprocessing: grayscale + autocontrast
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        return pytesseract.image_to_string(img, config=_HANDWRITING_CONFIG).strip()
