"""
Text Extractor — extracts text page-by-page from PDFs, TXT, and CSV documents.
PyMuPDF (fitz) is used for PDFs with multi-strategy text extraction and OCR fallback.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    """Represents extracted text from a single page."""
    page_number: int
    raw_text: str
    ocr_applied: bool = False


@dataclass
class ExtractionResult:
    """Result of text extraction from a document."""
    pages: list[PageText] = field(default_factory=list)
    total_pages: int = 0
    errors: list[str] = field(default_factory=list)


class PDFTextExtractor:
    """
    Extracts text from PDF documents page-by-page using PyMuPDF.
    If a page has no extractable digital text, it is flagged for OCR fallback processing.
    """

    MIN_TEXT_LENGTH = 10  # Minimum characters to consider a page as having digital text

    def extract(self, file_path: str | Path) -> ExtractionResult:
        file_path = Path(file_path)
        result = ExtractionResult()

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        if fitz is None:
            result.errors.append("PyMuPDF (fitz) is not installed")
            return result

        doc = None
        try:
            doc = fitz.open(str(file_path.resolve()))
            result.total_pages = len(doc)

            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    
                    # 1. Try standard text extraction
                    text = page.get_text("text") or ""
                    
                    # 2. If text is sparse, try blocks extraction
                    if len(text.strip()) < self.MIN_TEXT_LENGTH:
                        blocks = page.get_text("blocks") or []
                        block_texts = [b[4] for b in blocks if len(b) > 4 and isinstance(b[4], str) and b[4].strip()]
                        if block_texts:
                            text = "\n".join(block_texts)

                    needs_ocr = len(text.strip()) < self.MIN_TEXT_LENGTH

                    result.pages.append(PageText(
                        page_number=page_num + 1,  # 1-indexed
                        raw_text=text,
                        ocr_applied=False,
                    ))

                    if needs_ocr:
                        logger.info(f"Page {page_num + 1} in {file_path.name} has minimal digital text, flagged for OCR")

                except Exception as e:
                    logger.error(f"Error extracting page {page_num + 1} from {file_path.name}: {e}")
                    result.errors.append(f"Page {page_num + 1}: {str(e)}")
                    result.pages.append(PageText(
                        page_number=page_num + 1,
                        raw_text="",
                        ocr_applied=False,
                    ))

        except Exception as e:
            logger.error(f"Error opening PDF {file_path}: {e}")
            result.errors.append(f"Failed to open PDF: {str(e)}")
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

        return result


class TXTTextExtractor:
    """Extracts text from plain text files with robust encoding support."""

    def extract(self, file_path: str | Path) -> ExtractionResult:
        file_path = Path(file_path)
        result = ExtractionResult()

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        encodings_to_try = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
        text = None

        for enc in encodings_to_try:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    text = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if text is None:
            # Fallback with replacement
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                result.errors.append(f"Failed to read file: {str(e)}")
                return result

        result.total_pages = 1
        result.pages.append(PageText(
            page_number=1,
            raw_text=text or "",
            ocr_applied=False,
        ))

        return result


class CSVTextExtractor:
    """
    Extracts text from CSV/TSV files.
    Splits rows into manageable page chunks and formats them for NER & regex analysis.
    """

    ROWS_PER_PAGE = 100

    def extract(self, file_path: str | Path) -> ExtractionResult:
        file_path = Path(file_path)
        result = ExtractionResult()

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        content = None

        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                result.errors.append(f"Failed to read CSV: {str(e)}")
                return result

        try:
            # Detect delimiter
            delimiter = ","
            first_line = content.split("\n")[0] if content else ""
            if "\t" in first_line and "," not in first_line:
                delimiter = "\t"
            elif ";" in first_line and "," not in first_line:
                delimiter = ";"

            reader = csv.reader(content.splitlines(), delimiter=delimiter)
            rows = [r for r in reader if any(field.strip() for field in r)]

            if not rows:
                result.errors.append("CSV file is empty or contains no valid rows")
                return result

            header = rows[0]
            data_rows = rows[1:]

            if not data_rows:
                result.pages.append(PageText(
                    page_number=1,
                    raw_text=" | ".join(header),
                    ocr_applied=False,
                ))
                result.total_pages = 1
                return result

            # Split into chunks of ROWS_PER_PAGE
            page_num = 1
            step = max(self.ROWS_PER_PAGE, 1)
            
            for i in range(0, len(data_rows), step):
                chunk = data_rows[i:i + step]
                lines = [" | ".join(header)]
                for row in chunk:
                    lines.append(" | ".join(row))
                text = "\n".join(lines)

                result.pages.append(PageText(
                    page_number=page_num,
                    raw_text=text,
                    ocr_applied=False,
                ))
                page_num += 1

            result.total_pages = len(result.pages)

        except Exception as e:
            logger.error(f"Error parsing CSV {file_path}: {e}")
            result.errors.append(f"Failed to parse CSV: {str(e)}")

        return result


class TextExtractorFactory:
    """Factory for creating appropriate text extractors based on MIME type or file extension."""

    _extractors = {
        # PDF
        "application/pdf": PDFTextExtractor,
        "application/x-pdf": PDFTextExtractor,
        ".pdf": PDFTextExtractor,
        # Text
        "text/plain": TXTTextExtractor,
        "text/markdown": TXTTextExtractor,
        "text/html": TXTTextExtractor,
        ".txt": TXTTextExtractor,
        ".text": TXTTextExtractor,
        ".md": TXTTextExtractor,
        # CSV & Tabular
        "text/csv": CSVTextExtractor,
        "application/csv": CSVTextExtractor,
        "text/x-csv": CSVTextExtractor,
        "application/vnd.ms-excel": CSVTextExtractor,
        "text/comma-separated-values": CSVTextExtractor,
        "text/tab-separated-values": CSVTextExtractor,
        ".csv": CSVTextExtractor,
        ".tsv": CSVTextExtractor,
    }

    @classmethod
    def get_extractor(cls, mime_type: str, file_path: str | Path | None = None):
        """
        Get the appropriate extractor for the given MIME type or file path.
        Fallback to file extension and safe defaults if MIME is generic.
        """
        cleaned_mime = (mime_type or "").strip().lower().split(";")[0]

        # 1. Match by MIME type
        if cleaned_mime in cls._extractors:
            return cls._extractors[cleaned_mime]()

        # 2. Match by file extension
        if file_path:
            ext = Path(file_path).suffix.lower()
            if ext in cls._extractors:
                return cls._extractors[ext]()

        # 3. Keyword matches
        if "pdf" in cleaned_mime:
            return PDFTextExtractor()
        if "csv" in cleaned_mime or "excel" in cleaned_mime or "tab-separated" in cleaned_mime:
            return CSVTextExtractor()
        if "text/" in cleaned_mime or "plain" in cleaned_mime:
            return TXTTextExtractor()

        raise ValueError(f"Unsupported file type: {mime_type}")

    @classmethod
    def register_extractor(cls, key: str, extractor_class):
        """Register a new extractor for a MIME type or extension."""
        cls._extractors[key.lower()] = extractor_class
