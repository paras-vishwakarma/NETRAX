"""
Document Processing Pipeline — orchestrates the complete Phase 1 extraction flow.

Pipeline Lifecycle:
1. Validate document and storage path
2. Extract text (page-by-page) via PyMuPDF / TXT / CSV extractors
3. Apply Tesseract OCR fallback for scanned/image pages
4. Clean and normalize extracted text
5. Run Regex pattern extraction
6. Run spaCy NER extraction
7. Run optional LLM extraction
8. Merge extraction results and deduplicate entities
9. Persist document pages, entities, and evidence mentions
10. Set processing status to READY_FOR_REVIEW
"""

import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.entity import Entity, EntityType, ExtractionMethod, VerificationStatus
from app.models.entity_mention import EntityMention
from app.services.extraction.text_extractor import TextExtractorFactory, ExtractionResult, PageText
from app.services.extraction.ocr_service import BaseOCRService, create_ocr_service
from app.services.extraction.regex_extractor import RegexEntityExtractor, ExtractedEntity
from app.services.nlp.ner_extractor import BaseNERExtractor, create_ner_extractor
from app.services.nlp.llm_extractor import BaseLLMExtractionService, create_llm_extractor
from app.services.normalization.text_cleaning import TextCleaningService
from app.services.normalization.entity_normalizer import EntityNormalizationService
from app.services.normalization.entity_merger import EntityMerger, MergedEntity
from app.config import settings

logger = logging.getLogger(__name__)


class DocumentProcessingPipeline:
    """
    Orchestrates the complete document processing pipeline.
    Modular design allows swapping or extending any component.
    """

    def __init__(
        self,
        ocr_service: BaseOCRService | None = None,
        ner_extractor: BaseNERExtractor | None = None,
        llm_extractor: BaseLLMExtractionService | None = None,
        text_cleaner: TextCleaningService | None = None,
        entity_normalizer: EntityNormalizationService | None = None,
        entity_merger: EntityMerger | None = None,
    ):
        self.ocr_service = ocr_service or create_ocr_service(
            enabled=settings.OCR_ENABLED,
            tesseract_cmd=settings.TESSERACT_CMD,
        )
        self.ner_extractor = ner_extractor or create_ner_extractor(
            model_name=settings.NER_MODEL
        )
        self.llm_extractor = llm_extractor or create_llm_extractor(
            enabled=settings.LLM_ENABLED,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            provider=settings.LLM_PROVIDER,
        )
        self.text_cleaner = text_cleaner or TextCleaningService()
        self.entity_normalizer = entity_normalizer or EntityNormalizationService()
        self.entity_merger = entity_merger or EntityMerger(self.entity_normalizer)
        self.regex_extractor = RegexEntityExtractor()

    async def process(self, document: Document, db: AsyncSession) -> None:
        """
        Process a document through the complete pipeline.
        
        Args:
            document: The Document model instance to process.
            db: Active async database session.
        """
        try:
            logger.info(f"Starting pipeline for document {document.id}: {document.original_filename}")

            # Step 1: Update status to PROCESSING
            document.processing_status = ProcessingStatus.PROCESSING
            await db.flush()

            # Step 2: Extract text from file (with OCR fallback)
            await self._extract_text(document, db)

            # Step 3: Update status to TEXT_EXTRACTED
            document.processing_status = ProcessingStatus.TEXT_EXTRACTED
            await db.flush()

            # Step 4: Extract entities across all pages
            document.processing_status = ProcessingStatus.ENTITY_EXTRACTION
            await db.flush()

            await self._extract_entities(document, db)

            # Step 5: Mark ready for human review
            document.processing_status = ProcessingStatus.READY_FOR_REVIEW
            document.processing_error = None
            await db.commit()

            logger.info(f"Pipeline completed successfully for document {document.id} ({document.original_filename})")

        except Exception as e:
            logger.error(f"Pipeline failed for document {document.id}: {e}", exc_info=True)
            document.processing_status = ProcessingStatus.FAILED
            document.processing_error = str(e)
            await db.commit()

    async def _extract_text(self, document: Document, db: AsyncSession) -> None:
        """Extract text from document using appropriate extractor + OCR fallback."""
        logger.info(f"Extracting text from {document.original_filename} (type: {document.mime_type})")

        # Resolve storage path
        file_path = Path(document.storage_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Document storage file not found at: {document.storage_path}")

        extractor = TextExtractorFactory.get_extractor(document.mime_type, file_path=file_path)
        result: ExtractionResult = extractor.extract(file_path)

        if result.errors and not result.pages:
            raise ValueError(f"Text extraction failed: {'; '.join(result.errors)}")

        document.total_pages = result.total_pages or len(result.pages)
        is_pdf = "pdf" in (document.mime_type or "").lower() or file_path.suffix.lower() == ".pdf"

        for page_data in result.pages:
            raw_text = page_data.raw_text or ""
            ocr_applied = False

            # OCR fallback for pages with sparse or no digital text
            if len(raw_text.strip()) < 10 and is_pdf:
                if self.ocr_service.is_available():
                    logger.info(f"Applying OCR to page {page_data.page_number} of {document.original_filename}")
                    try:
                        ocr_result = self.ocr_service.extract_text_from_pdf_page(
                            file_path, page_data.page_number - 1  # 0-indexed
                        )
                        if ocr_result.success and ocr_result.text.strip():
                            raw_text = ocr_result.text
                            ocr_applied = True
                    except Exception as ocr_err:
                        logger.warning(f"OCR failed for page {page_data.page_number}: {ocr_err}")

            # Clean and normalize text while preserving raw text
            cleaned_text = self.text_cleaner.clean(raw_text) if raw_text else ""

            # Save DocumentPage record
            page = DocumentPage(
                document_id=document.id,
                page_number=page_data.page_number,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                ocr_applied=ocr_applied,
            )
            db.add(page)

        await db.flush()
        logger.info(f"Extracted and saved {len(result.pages)} pages for document {document.id}")

    async def _extract_entities(self, document: Document, db: AsyncSession) -> None:
        """Run all entity extractors on each page and merge/deduplicate results."""
        logger.info(f"Extracting entities from {document.original_filename}")

        # Reload pages from database
        pages_result = await db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
        pages = pages_result.scalars().all()

        all_document_entities: list[tuple[MergedEntity, DocumentPage]] = []

        for page in pages:
            text = page.cleaned_text or page.raw_text or ""
            if not text.strip():
                continue

            page_entities: list[ExtractedEntity] = []

            # 1. Regex extraction (Phones, Emails, Vehicles, FIR Numbers, Accounts, IMEIs, Dates)
            try:
                regex_results = self.regex_extractor.extract(text, page.page_number)
                page_entities.extend(regex_results)
            except Exception as e:
                logger.warning(f"Regex extraction error on page {page.page_number}: {e}")

            # 2. Pretrained NER extraction (Persons, Locations, Organizations, Dates)
            if self.ner_extractor.is_available():
                try:
                    ner_results = self.ner_extractor.extract(text, page.page_number)
                    page_entities.extend(ner_results)
                except Exception as e:
                    logger.warning(f"NER extraction error on page {page.page_number}: {e}")

            # 3. Optional LLM extraction
            if self.llm_extractor.is_available():
                try:
                    llm_results = await self.llm_extractor.extract_entities(text, page.page_number)
                    page_entities.extend(llm_results)
                except Exception as e:
                    logger.warning(f"LLM extraction error on page {page.page_number}: {e}")

            # Merge entities for this page
            if page_entities:
                merged = self.entity_merger.merge(page_entities)
                for merged_entity in merged:
                    all_document_entities.append((merged_entity, page))

        # Deduplicate across pages to produce unified Document Entities with all Evidence Mentions
        entity_map: dict[tuple[str, str], dict] = {}

        for merged_entity, page in all_document_entities:
            key = (merged_entity.entity_type, merged_entity.normalized_value)

            if key not in entity_map:
                entity_map[key] = {
                    "entity_type": merged_entity.entity_type,
                    "value": merged_entity.value,
                    "normalized_value": merged_entity.normalized_value,
                    "confidence": merged_entity.confidence,
                    "extraction_method": merged_entity.extraction_method,
                    "mentions": [],
                }
            else:
                # Update confidence and mark HYBRID if multiple methods detected
                if merged_entity.confidence > entity_map[key]["confidence"]:
                    entity_map[key]["confidence"] = merged_entity.confidence
                    entity_map[key]["value"] = merged_entity.value
                if merged_entity.extraction_method != entity_map[key]["extraction_method"]:
                    entity_map[key]["extraction_method"] = "HYBRID"

            # Add mentions from this page
            for mention in merged_entity.mentions:
                entity_map[key]["mentions"].append({
                    "page": page,
                    "mention": mention,
                })

        # Persist entities and evidence mentions to database
        for entity_data in entity_map.values():
            try:
                entity_type_enum = EntityType(entity_data["entity_type"])
            except ValueError:
                logger.warning(f"Unknown entity type '{entity_data['entity_type']}', skipping")
                continue

            try:
                method_enum = ExtractionMethod(entity_data["extraction_method"])
            except ValueError:
                method_enum = ExtractionMethod.HYBRID if entity_data["extraction_method"] == "HYBRID" else ExtractionMethod.REGEX

            entity = Entity(
                document_id=document.id,
                entity_type=entity_type_enum,
                value=entity_data["value"],
                normalized_value=entity_data["normalized_value"],
                confidence=entity_data["confidence"],
                extraction_method=method_enum,
                verification_status=VerificationStatus.UNVERIFIED,
            )
            db.add(entity)
            await db.flush()

            # Save evidence mentions with precise character spans
            for mention_info in entity_data["mentions"]:
                page_obj = mention_info["page"]
                m = mention_info["mention"]

                m_start = getattr(m, "start", None)
                m_end = getattr(m, "end", None)
                m_context = getattr(m, "context", None)
                m_conf = getattr(m, "confidence", entity_data["confidence"])
                m_method = getattr(m, "method", method_enum.value)

                entity_mention = EntityMention(
                    entity_id=entity.id,
                    document_id=document.id,
                    document_page_id=page_obj.id,
                    page_number=page_obj.page_number,
                    text_start=m_start,
                    text_end=m_end,
                    context=m_context,
                    confidence=m_conf,
                    extraction_method=str(m_method),
                )
                db.add(entity_mention)

        await db.flush()
        logger.info(f"Saved {len(entity_map)} entities and their mentions for document {document.id}")


# Singleton pipeline instance (initialized lazily)
_pipeline_instance: DocumentProcessingPipeline | None = None


def get_pipeline(force_reload: bool = False) -> DocumentProcessingPipeline:
    """Get or create the singleton pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None or force_reload:
        _pipeline_instance = DocumentProcessingPipeline()
    return _pipeline_instance
