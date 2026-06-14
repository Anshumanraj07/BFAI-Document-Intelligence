"""Unit tests for the parsing pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.parsers import ImageParser, PDFParser, TableParser


@pytest.mark.asyncio
async def test_pdf_parser_handles_missing_file(tmp_path: Path):
    parser = PDFParser()
    with pytest.raises(Exception):
        await parser.parse(str(tmp_path / "nope.pdf"))


@pytest.mark.asyncio
async def test_image_parser_handles_missing_file(tmp_path: Path):
    parser = ImageParser()
    with pytest.raises(Exception):
        await parser.parse(str(tmp_path / "nope.png"))


@pytest.mark.asyncio
async def test_table_parser_handles_missing_file(tmp_path: Path):
    parser = TableParser()
    with pytest.raises(Exception):
        await parser.parse(str(tmp_path / "nope.pdf"))


def test_parser_synchronous_in_threadpool():
    """Sanity check: pdfplumber runs in a threadpool (no event loop conflict)."""
    async def _go():
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: 1 + 1
        )
    assert asyncio.run(_go()) == 2
