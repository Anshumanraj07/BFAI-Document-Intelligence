"""Document parsing pipeline: text, OCR, tables, handwriting."""

from app.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage
from app.parsers.pdf_parser import PDFParser
from app.parsers.image_parser import ImageParser
from app.parsers.handwritten_parser import HandwrittenParser
from app.parsers.table_parser import TableParser

__all__ = [
    "BaseParser",
    "ParsedDocument",
    "ParsedPage",
    "PDFParser",
    "ImageParser",
    "HandwrittenParser",
    "TableParser",
]
