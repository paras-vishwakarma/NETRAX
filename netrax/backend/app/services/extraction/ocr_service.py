"""
OCR Service — modular OCR abstraction for scanned document processing.
Uses Tesseract as the default implementation with auto-detection for Windows and Linux.
"""

import io
import os
import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass
from typing import Any

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result of OCR processing."""
    text: str
    confidence: float = 0.0
    success: bool = True
    error: str | None = None


class BaseOCRService(ABC):
    """Abstract base class for OCR services. Implement to swap OCR providers."""

    @abstractmethod
    def extract_text(self, image: Any) -> OCRResult:
        """Extract text from an image (PIL Image, bytes, or file path)."""
        ...

    @abstractmethod
    def extract_text_from_pdf_page(self, pdf_path: str | Path, page_number: int) -> OCRResult:
        """Extract text from a specific PDF page using OCR (0-indexed)."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the OCR service is available."""
        ...


def _find_tesseract_binary(custom_path: str | None = None) -> str | None:
    """
    Search for Tesseract executable across custom paths, PATH, and standard OS directories.
    """
    if custom_path and Path(custom_path).is_file():
        return str(Path(custom_path).resolve())

    # 1. Check system PATH
    which_path = shutil.which("tesseract")
    if which_path:
        return which_path

    # 2. Common Windows paths
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        r"C:\tools\tesseract\tesseract.exe",
        # Common Linux / macOS paths
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())

    return None


class TesseractOCRService(BaseOCRService):
    """
    OCR implementation using Tesseract.
    Auto-detects Tesseract binary and falls back gracefully if not found.
    """

    def __init__(self, tesseract_cmd: str | None = None):
        self._available = False
        self._tesseract_path: str | None = None

        try:
            import pytesseract
            self._tesseract_path = _find_tesseract_binary(tesseract_cmd)

            if self._tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path

            # Test availability
            version = pytesseract.get_tesseract_version()
            self._available = True
            logger.info(f"Tesseract OCR is available (version: {version}, path: {self._tesseract_path or 'PATH'})")
        except Exception as e:
            logger.warning(f"Tesseract OCR is not available: {e}")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def extract_text(self, image: Any) -> OCRResult:
        """Extract text from a PIL Image, image bytes, or file path."""
        if not self._available:
            return OCRResult(text="", success=False, error="Tesseract is not available")

        try:
            import pytesseract
            from PIL import Image

            if isinstance(image, (str, Path)):
                with Image.open(str(image)) as img:
                    pil_image = img.copy()
            elif isinstance(image, (bytes, bytearray)):
                with Image.open(io.BytesIO(image)) as img:
                    pil_image = img.copy()
            elif isinstance(image, Image.Image):
                pil_image = image
            else:
                return OCRResult(text="", success=False, error=f"Unsupported image input type: {type(image)}")

            # Convert to RGB to avoid alpha/palette issues in pytesseract
            if pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")

            # Ensure tesseract command is set
            if self._tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path

            # Extract text
            text = pytesseract.image_to_string(pil_image) or ""

            # Calculate confidence score
            avg_confidence = 0.0
            try:
                data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
                confidences = []
                for c in data.get('conf', []):
                    try:
                        val = int(c)
                        if val > 0:
                            confidences.append(val)
                    except (ValueError, TypeError):
                        pass
                if confidences:
                    avg_confidence = (sum(confidences) / len(confidences)) / 100.0
                elif text.strip():
                    avg_confidence = 0.85
            except Exception:
                avg_confidence = 0.80 if text.strip() else 0.0

            return OCRResult(
                text=text.strip(),
                confidence=avg_confidence,
                success=True,
            )

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return OCRResult(text="", success=False, error=str(e))

    def extract_text_from_pdf_page(self, pdf_path: str | Path, page_number: int) -> OCRResult:
        """
        Extract text from a specific PDF page by rendering it as an image first.
        page_number is 0-indexed.
        """
        if not self._available:
            return OCRResult(text="", success=False, error="Tesseract is not available")

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return OCRResult(text="", success=False, error=f"PDF file not found: {pdf_path}")

        if fitz is None:
            return OCRResult(text="", success=False, error="PyMuPDF (fitz) is not installed")

        doc = None
        try:
            doc = fitz.open(str(pdf_path.resolve()))
            if page_number < 0 or page_number >= len(doc):
                return OCRResult(text="", success=False, error=f"Page index {page_number} out of bounds (0-{len(doc)-1})")

            page = doc[page_number]

            # Render page as image at 300 DPI for optimal OCR recognition
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            return self.extract_text(img_bytes)

        except Exception as e:
            logger.error(f"OCR PDF page extraction failed: {e}")
            return OCRResult(text="", success=False, error=str(e))
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass


class NoOpOCRService(BaseOCRService):
    """No-op OCR service when OCR is disabled or unavailable."""

    def extract_text(self, image: Any) -> OCRResult:
        return OCRResult(text="", success=False, error="OCR is disabled")

    def extract_text_from_pdf_page(self, pdf_path: str | Path, page_number: int) -> OCRResult:
        return OCRResult(text="", success=False, error="OCR is disabled")

    def is_available(self) -> bool:
        return False


def create_ocr_service(enabled: bool = True, tesseract_cmd: str | None = None) -> BaseOCRService:
    """Factory function to create the appropriate OCR service."""
    if not enabled:
        return NoOpOCRService()

    service = TesseractOCRService(tesseract_cmd=tesseract_cmd)
    if not service.is_available():
        logger.warning("Falling back to NoOp OCR — Tesseract not found")
        return NoOpOCRService()

    return service
