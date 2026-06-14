"""
Table extraction using pdfplumber's `extract_tables()`.

Returns structured JSON: each table is a list of rows, where each row
is a list of cell strings. Coordinates (bounding box) are also returned
for the UI to highlight tables.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

from app.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage, ParserError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TableParser(BaseParser):
    """Extract structured tables from PDFs."""

    supported_extensions = [".pdf"]
    parser_name = "table"

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
            mime_type="application/pdf",
            parser_used=self.parser_name,
        )

        try:
            loop = asyncio.get_running_loop()
            pages = await loop.run_in_executor(
                None, self._extract_tables_sync, str(path), max_pages
            )
        except Exception as exc:
            logger.exception("Table extraction failed: %s", file_path)
            doc.error = str(exc)
            return doc

        doc.pages = pages
        doc.page_count = len(pages)
        doc.aggregate_text()
        total_tables = sum(len(p.tables) for p in pages)
        logger.info("Extracted %d tables from %s", total_tables, path.name)
        return doc

    def _extract_tables_sync(
        self,
        pdf_path: str,
        max_pages: Optional[int],
    ) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        cap = max_pages or 5
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages[:cap]):
                raw_tables = page.extract_tables() or []
                page_tables: List[Dict[str, Any]] = []
                for t_idx, table in enumerate(raw_tables):
                    cleaned_rows = [
                        [(cell or "").strip() for cell in row]
                        for row in table
                    ]
                    page_tables.append({
                        "table_index": t_idx,
                        "rows": cleaned_rows,
                        "row_count": len(cleaned_rows),
                        "col_count": max((len(r) for r in cleaned_rows), default=0),
                        "bbox": getattr(page.find_tables()[t_idx], "bbox", None)
                        if t_idx < len(page.find_tables()) else None,
                    })
                pages.append(ParsedPage(
                    page_number=i + 1,
                    text=(page.extract_text() or "").strip(),
                    has_tables=bool(page_tables),
                    tables=page_tables,
                    metadata={"table_count": len(page_tables)},
                ))
        return pages
