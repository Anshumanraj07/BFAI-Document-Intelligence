"""
Abstract base class for all document parsers.

Every concrete parser (PDF, image, handwritten, table) must implement
`parse()` and return a `ParsedDocument` containing pages with text and
optional image references.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ParsedPage:
    """Represents a single parsed page."""
    page_number: int
    text: str = ""
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    has_handwriting: bool = False
    has_tables: bool = False
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """The full parsed output of a document."""
    filename: str
    file_path: str
    mime_type: str
    page_count: int = 0
    pages: List[ParsedPage] = field(default_factory=list)
    full_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    parser_used: str = ""

    @property
    def is_successful(self) -> bool:
        return self.error is None and self.page_count > 0

    def aggregate_text(self) -> str:
        """Concatenate all page texts with page markers."""
        parts = []
        for p in self.pages:
            parts.append(f"--- Page {p.page_number} ---\n{p.text}")
        self.full_text = "\n\n".join(parts)
        return self.full_text


class BaseParser(ABC):
    """Abstract parser interface."""

    supported_extensions: List[str] = []
    parser_name: str = "base"

    @abstractmethod
    async def parse(self, file_path: str, *, max_pages: Optional[int] = None) -> ParsedDocument:
        """
        Parse a document and return a `ParsedDocument`.

        Args:
            file_path: Absolute or relative path to the file.
            max_pages: Optional cap on pages to process (safety for free tier).

        Raises:
            ParserError: on any unrecoverable parsing failure.
        """
        raise NotImplementedError


class ParserError(Exception):
    """Raised by parsers on failure."""
    pass
