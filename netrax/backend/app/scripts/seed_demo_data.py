"""
NETRA-X Demo Data Seeder
Populates the database with realistic synthetic cases, documents, entities,
entity mentions, canonical entities, match candidates, and graph relationships.
"""

import asyncio
import os
import shutil
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import select, delete, func
from app.database import async_session_factory, init_db
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.entity import Entity, EntityType, ExtractionMethod, VerificationStatus
from app.models.entity_mention import EntityMention
from app.models.canonical_entity import CanonicalEntity, EntityAlias, CanonicalEntityStatus
from app.models.entity_match_candidate import EntityMatchCandidate
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus
from app.services.processing.pipeline import DocumentProcessingPipeline
from app.services.resolution.entity_resolution import EntityResolutionService
from app.services.resolution.relationship_extraction import RelationshipExtractionService
from app.services.resolution.graph_sync import GraphSyncService
from app.scripts.generate_synthetic_data import generate_all_synthetic_data
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo_data")


async def seed_data(reset: bool = False):
    await init_db()

    backend_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = backend_dir / "data" / "synthetic"
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ensure fresh synthetic files are generated
    logger.info("Generating synthetic data files...")
    generate_all_synthetic_data(str(data_dir))

    async with async_session_factory() as db:
        if reset:
            logger.info("Resetting existing database records...")
            await db.execute(delete(Relationship))
            await db.execute(delete(EntityMatchCandidate))
            await db.execute(delete(EntityAlias))
            await db.execute(delete(CanonicalEntity))
            await db.execute(delete(EntityMention))
            await db.execute(delete(Entity))
            await db.execute(delete(DocumentPage))
            await db.execute(delete(Document))
            await db.execute(delete(Case))
            await db.commit()

        # Check if cases already exist
        existing_cases = (await db.execute(select(Case))).scalars().all()
        if existing_cases and not reset:
            logger.info(f"Database already contains {len(existing_cases)} cases. Populating missing data...")

        # 2. Create Investigation Cases
        cases_def = [
            {
                "case_number": "CASE-2024-001",
                "title": "Inter-State Vehicle Theft & Chop Shop Syndicate",
                "description": "Investigation into organized vehicle theft network operating across Delhi NCR, Rajasthan, and Madhya Pradesh.",
                "status": CaseStatus.UNDER_INVESTIGATION,
            },
            {
                "case_number": "CASE-2024-002",
                "title": "Cyber Financial Fraud & Hawala Layering Ring",
                "description": "Probe into multi-account financial transfers and suspicious banking transactions linked to cyber extortion.",
                "status": CaseStatus.UNDER_INVESTIGATION,
            },
            {
                "case_number": "CASE-2024-003",
                "title": "Narcotics Distribution & High-Frequency Telecom Links",
                "description": "Surveillance and call data record analysis of narcotics distribution nexus across transit hubs.",
                "status": CaseStatus.OPEN,
            },
        ]

        case_map = {}
        for cdata in cases_def:
            res = await db.execute(select(Case).where(Case.case_number == cdata["case_number"]))
            case = res.scalar_one_or_none()
            if not case:
                case = Case(
                    case_number=cdata["case_number"],
                    title=cdata["title"],
                    description=cdata["description"],
                    status=cdata["status"],
                )
                db.add(case)
                await db.flush()
                logger.info(f"Created case: {case.case_number} - {case.title}")
            case_map[cdata["case_number"]] = case

        await db.commit()

        # 3. Document mapping
        docs_to_ingest = [
            # Case 1 Documents
            {"case_num": "CASE-2024-001", "file": data_dir / "fir" / "FIR_001.pdf", "type": DocumentType.FIR, "mime": "application/pdf"},
            {"case_num": "CASE-2024-001", "file": data_dir / "fir" / "FIR_002.pdf", "type": DocumentType.FIR, "mime": "application/pdf"},
            {"case_num": "CASE-2024-001", "file": data_dir / "cdr" / "CDR_001.csv", "type": DocumentType.CDR, "mime": "text/csv"},
            
            # Case 2 Documents
            {"case_num": "CASE-2024-002", "file": data_dir / "fir" / "FIR_003.pdf", "type": DocumentType.FIR, "mime": "application/pdf"},
            {"case_num": "CASE-2024-002", "file": data_dir / "financial" / "transactions_001.csv", "type": DocumentType.FINANCIAL_RECORD, "mime": "text/csv"},
            {"case_num": "CASE-2024-002", "file": data_dir / "financial" / "transactions_002.csv", "type": DocumentType.FINANCIAL_RECORD, "mime": "text/csv"},

            # Case 3 Documents
            {"case_num": "CASE-2024-003", "file": data_dir / "fir" / "FIR_004.pdf", "type": DocumentType.FIR, "mime": "application/pdf"},
            {"case_num": "CASE-2024-003", "file": data_dir / "fir" / "FIR_005.pdf", "type": DocumentType.FIR, "mime": "application/pdf"},
            {"case_num": "CASE-2024-003", "file": data_dir / "cdr" / "CDR_002.csv", "type": DocumentType.CDR, "mime": "text/csv"},
        ]

        pipeline = DocumentProcessingPipeline()

        for ddef in docs_to_ingest:
            file_path = ddef["file"]
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue

            case = case_map[ddef["case_num"]]
            filename = file_path.name

            # Check if document already exists
            existing_doc = (await db.execute(
                select(Document).where(Document.case_id == case.id, Document.original_filename == filename)
            )).scalar_one_or_none()

            if existing_doc:
                logger.info(f"Document {filename} already exists in case {case.case_number}. Skipping creation.")
                doc = existing_doc
            else:
                doc_id = str(uuid.uuid4())
                dest_dir = uploads_dir / doc_id
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = (dest_dir / filename).resolve()
                shutil.copy2(file_path, dest_file)

                content_bytes = file_path.read_bytes()
                import hashlib
                fhash = hashlib.sha256(content_bytes).hexdigest()

                doc = Document(
                    id=doc_id,
                    case_id=case.id,
                    filename=filename,
                    original_filename=filename,
                    document_type=ddef["type"],
                    mime_type=ddef["mime"],
                    file_size=len(content_bytes),
                    file_hash=fhash,
                    storage_path=str(dest_file),
                    processing_status=ProcessingStatus.UPLOADED,
                    source="Synthetic Investigation Dataset",
                )
                db.add(doc)
                await db.commit()
                await db.refresh(doc)
                logger.info(f"Created document record: {doc.original_filename} (ID: {doc.id})")

            # Process document if not ready
            if doc.processing_status != ProcessingStatus.READY_FOR_REVIEW:
                logger.info(f"Processing document {doc.original_filename}...")
                await pipeline.process(doc, db)
                await db.refresh(doc)
                logger.info(f"Finished processing document: {doc.original_filename} -> {doc.processing_status}")

        # 4. Verify entities to enable canonical resolution
        logger.info("Approving and verifying extracted entities...")
        entities_res = await db.execute(select(Entity))
        entities = entities_res.scalars().all()
        for ent in entities:
            ent.verification_status = VerificationStatus.VERIFIED
        await db.commit()
        logger.info(f"Verified {len(entities)} entities.")

        # 5. Entity Resolution & Canonical Sync
        logger.info("Running Entity Resolution Sync...")
        res_service = EntityResolutionService()
        synced_count = await res_service.sync_all_entities(db, include_unverified=True)
        logger.info(f"Synced {synced_count} canonical entities.")

        # 6. Extract Relationships (CDR calls, Financial transfers, FIR co-occurrences)
        logger.info("Extracting evidence-backed relationships...")
        rel_service = RelationshipExtractionService()
        rels_count = await rel_service.extract_all(db)
        logger.info(f"Extracted {rels_count} relationships.")

        # 7. Generate cross-case match candidates
        logger.info("Generating entity match candidates...")
        candidates_count = await res_service.generate_candidates(db, min_score=0.35, include_unverified=True)
        logger.info(f"Generated {candidates_count} entity match candidates.")

        # 8. Graph Projection check
        logger.info("Testing graph projection...")
        graph_service = GraphSyncService()
        total_nodes = 0
        total_edges = 0
        for case in case_map.values():
            case_graph = await graph_service.get_case_graph(db, case_id=case.id)
            total_nodes += len(case_graph.nodes)
            total_edges += len(case_graph.edges)
            logger.info(f"Case {case.case_number} graph: {len(case_graph.nodes)} nodes, {len(case_graph.edges)} edges")

        # Final DB summary
        case_count = (await db.execute(select(func.count(Case.id)))).scalar()
        doc_count = (await db.execute(select(func.count(Document.id)))).scalar()
        ent_count = (await db.execute(select(func.count(Entity.id)))).scalar()
        can_count = (await db.execute(select(func.count(CanonicalEntity.id)))).scalar()
        rel_count = (await db.execute(select(func.count(Relationship.id)))).scalar()
        cand_count = (await db.execute(select(func.count(EntityMatchCandidate.id)))).scalar()

        print("\n" + "=" * 60)
        print("  NETRA-X DATA CONFIGURATION COMPLETE")
        print("=" * 60)
        print(f"  * Cases:              {case_count}")
        print(f"  * Documents:          {doc_count}")
        print(f"  * Entities:           {ent_count}")
        print(f"  * Canonical Entities: {can_count}")
        print(f"  * Relationships:      {rel_count}")
        print(f"  * Match Candidates:   {cand_count}")
        print(f"  * Total Graph Nodes:  {total_nodes}")
        print(f"  * Total Graph Edges:  {total_edges}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_data(reset=True))
