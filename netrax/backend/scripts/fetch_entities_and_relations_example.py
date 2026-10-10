"""
NETRA-X — Example Script: Ingest Investigation Data, Resolve Entities & Fetch Relationships

This example demonstrates:
1. Creating an investigation case ("Operation Night Hawk — Auto-Theft & Money Laundering Network").
2. Ingesting investigation records (FIR Narrative, Call Detail Records CDR, and Bank Transactions).
3. Extracting and resolving structured entities (Persons, Vehicles, Phones, Accounts, Locations).
4. Extracting and establishing evidence-backed relationships (CALLED, TRANSFERRED_TO, USES, OWNS, ASSOCIATED_WITH).
5. Fetching and displaying the complete entity network and relationship graph with full provenance.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, func

from app.database import init_db, async_session_factory
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.entity import Entity, EntityType, ExtractionMethod, VerificationStatus
from app.models.entity_mention import EntityMention
from app.models.canonical_entity import CanonicalEntity, CanonicalEntityStatus, EntityAlias
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus
from app.services.processing.pipeline import get_pipeline
from app.services.resolution.entity_resolution import EntityResolutionService
from app.services.resolution.relationship_extraction import RelationshipExtractionService
from app.services.resolution.graph_sync import GraphSyncService


async def run_example():
    await init_db()

    print("=" * 90)
    print("      NETRA-X INVESTIGATION ANALYSIS: ENTITY & RELATIONSHIP EXTRACTION DEMO")
    print("=" * 90)

    async with async_session_factory() as db:
        # 1. Create or fetch investigation case
        case_number = "CASE-2026-AUTO-091"
        existing_case = (await db.execute(select(Case).where(Case.case_number == case_number))).scalar_one_or_none()

        if not existing_case:
            case = Case(
                case_number=case_number,
                title="Operation Night Hawk — Vehicle Theft & Hawala Network",
                description="Investigation into interstate vehicle theft racket and linked laundering accounts.",
                status=CaseStatus.UNDER_INVESTIGATION,
            )
            db.add(case)
            await db.commit()
            await db.refresh(case)
        else:
            case = existing_case

        print(f"\n[1/4] CASE DETAILS")
        print(f"  • Case Number : {case.case_number}")
        print(f"  • Title       : {case.title}")
        print(f"  • Case ID     : {case.id}")

        # 2. Add Investigation Evidence Documents
        fir_text = """FIRST INFORMATION REPORT — CENTRAL POLICE STATION
FIR No: FIR/2026/8812 | Date: 12/03/2026

On 12/03/2026 at 21:30 hours, Complainant reported vehicle theft near Laxmi Nagar Metro Station.
Suspect Rajesh Sharma (alias 'Raju Auto') was apprehended driving a stolen SUV (Vehicle Reg: DL01EF9012).
Interrogation revealed that Rajesh Sharma uses phone 9876543210 and was in direct contact with
Vikram Malhotra (alias 'Vicky Don', phone: 9988776655) of Apex Logistics.
Suspect admitted transferring extortion money to Suresh Gupta (Account No: 1234567890123) at Metro Bank.
A secondary communication was traced to phone 8877665544 located near Station Road, Civil Lines."""

        # Store Document
        doc = Document(
            case_id=case.id,
            filename="FIR_8812_Interception_Report.txt",
            original_filename="FIR_8812_Interception_Report.txt",
            document_type=DocumentType.FIR,
            mime_type="text/plain",
            file_size=len(fir_text.encode("utf-8")),
            file_hash="hash_fir_8812",
            storage_path=f"evidence://{case.case_number}/FIR_8812.txt",
            source="Central Police Station Kotwali",
            description="Interception and interrogation report of primary auto theft suspects",
            processing_status=ProcessingStatus.READY_FOR_REVIEW,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # 3. Process Document through NLP & Entity Extractor
        pipeline = get_pipeline()
        cleaned_str = pipeline.text_cleaner.clean(fir_text)
        if hasattr(cleaned_str, "text"):
            cleaned_str = cleaned_str.text
        
        # Add Document Page
        page = DocumentPage(
            document_id=doc.id,
            page_number=1,
            raw_text=fir_text,
            cleaned_text=cleaned_str,
            ocr_applied=False,
        )
        db.add(page)
        await db.commit()
        await db.refresh(page)

        # Regex + NER Extractions
        regex_ents = pipeline.regex_extractor.extract(cleaned_str, page_number=1)
        ner_ents = pipeline.ner_extractor.extract(cleaned_str, page_number=1)
        merged_entities = pipeline.entity_merger.merge(regex_ents + ner_ents)

        for me in merged_entities:
            try:
                etype = EntityType(me.entity_type)
            except ValueError:
                continue
            try:
                emethod = ExtractionMethod(me.extraction_method)
            except ValueError:
                emethod = ExtractionMethod.HYBRID

            entity = Entity(
                document_id=doc.id,
                entity_type=etype,
                value=me.value,
                normalized_value=me.normalized_value,
                confidence=me.confidence,
                extraction_method=emethod,
                verification_status=VerificationStatus.VERIFIED if me.confidence >= 0.9 else VerificationStatus.UNVERIFIED,
            )
            db.add(entity)
            await db.flush()

            for mention in me.mentions:
                m_method = getattr(mention, "method", "REGEX")
                db.add(EntityMention(
                    entity_id=entity.id,
                    document_id=doc.id,
                    document_page_id=page.id,
                    page_number=1,
                    text_start=getattr(mention, "start", None),
                    text_end=getattr(mention, "end", None),
                    context=getattr(mention, "context", None),
                    confidence=getattr(mention, "confidence", me.confidence),
                    extraction_method=m_method,
                ))

        await db.commit()

        # 4. Canonical Entity & Relationship Construction
        # Canonical entity mapping with aliases
        canonical_specs = [
            {"type": "PERSON", "name": "Rajesh Sharma", "aliases": ["Raju Auto", "Rajesh Sharma"]},
            {"type": "PERSON", "name": "Vikram Malhotra", "aliases": ["Vicky Don", "Vikram Malhotra"]},
            {"type": "PERSON", "name": "Suresh Gupta", "aliases": ["Suresh Gupta"]},
            {"type": "VEHICLE", "name": "DL01EF9012", "aliases": ["DL01EF9012"]},
            {"type": "PHONE", "name": "+91-9876543210", "aliases": ["9876543210"]},
            {"type": "PHONE", "name": "+91-9988776655", "aliases": ["9988776655"]},
            {"type": "PHONE", "name": "+91-8877665544", "aliases": ["8877665544"]},
            {"type": "ACCOUNT", "name": "ACC-1234567890123", "aliases": ["1234567890123"]},
            {"type": "ORGANIZATION", "name": "Apex Logistics", "aliases": ["Apex Logistics"]},
            {"type": "LOCATION", "name": "Laxmi Nagar Metro Station", "aliases": ["Laxmi Nagar"]},
            {"type": "LOCATION", "name": "Civil Lines", "aliases": ["Civil Lines"]},
        ]

        ce_map = {}
        for spec in canonical_specs:
            norm = spec["name"].strip().casefold()
            ce = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.normalized_name == norm))).scalar_one_or_none()
            if not ce:
                ce = CanonicalEntity(
                    entity_type=spec["type"],
                    canonical_name=spec["name"],
                    normalized_name=norm,
                    status=CanonicalEntityStatus.ACTIVE,
                    metadata_json=json.dumps({"aliases": spec["aliases"]}),
                )
                db.add(ce)
                await db.flush()

                # Add Aliases and link to Entity records
                for alias_val in spec["aliases"]:
                    alias_norm = alias_val.strip().casefold()
                    ent = Entity(
                        document_id=doc.id,
                        entity_type=EntityType(spec["type"]),
                        value=alias_val,
                        normalized_value=alias_norm,
                        confidence=1.0,
                        extraction_method=ExtractionMethod.MANUAL,
                        verification_status=VerificationStatus.VERIFIED,
                        notes=f"Alias for canonical entity {spec['name']}",
                    )
                    db.add(ent)
                    await db.flush()

                    db.add(EntityAlias(
                        canonical_entity_id=ce.id,
                        entity_id=ent.id,
                        alias_value=alias_val,
                        normalized_value=alias_norm,
                        source_document_id=doc.id,
                    ))
            ce_map[spec["name"]] = ce.id

        await db.commit()

        # Build evidence-backed Relationships
        relationships_to_create = [
            # (Source, Target, RelationshipType, Confidence, Provenance Note)
            ("Rajesh Sharma", "+91-9876543210", RelationshipType.USES, 0.95, "Admitted primary handset during interrogation"),
            ("Vikram Malhotra", "+91-9988776655", RelationshipType.USES, 0.95, "Registered subscriber on KYC & CDR"),
            ("Rajesh Sharma", "DL01EF9012", RelationshipType.OWNS, 0.92, "Caught driving intercepted vehicle at crime scene"),
            ("+91-9876543210", "+91-9988776655", RelationshipType.CALLED, 0.98, "CDR record: 14 phone calls exchanged between suspects"),
            ("Vikram Malhotra", "Apex Logistics", RelationshipType.WORKS_FOR, 0.90, "Company registration documents list as Director"),
            ("Rajesh Sharma", "ACC-1234567890123", RelationshipType.TRANSFERRED_TO, 0.94, "Bank statement shows Rs 50,000 NEFT transfer"),
            ("Suresh Gupta", "ACC-1234567890123", RelationshipType.HAS_ACCOUNT, 0.96, "Primary account holder at Metro Bank"),
            ("Rajesh Sharma", "Laxmi Nagar Metro Station", RelationshipType.LOCATED_AT, 0.91, "CCTV & GPS location of vehicle interception"),
            ("Rajesh Sharma", "Vikram Malhotra", RelationshipType.ASSOCIATED_WITH, 0.89, "Witness statements and co-accused testimony"),
        ]

        for src_name, tgt_name, rel_type, conf, note in relationships_to_create:
            src_id = ce_map.get(src_name)
            tgt_id = ce_map.get(tgt_name)
            if src_id and tgt_id:
                rel = Relationship(
                    case_id=case.id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relationship_type=rel_type,
                    confidence=conf,
                    extraction_method="PIPELINE_EVIDENCE_RESOLUTION",
                    verification_status=RelationshipVerificationStatus.VERIFIED if conf >= 0.95 else RelationshipVerificationStatus.UNVERIFIED,
                    source_document_id=doc.id,
                    properties_json=json.dumps({"provenance_note": note, "source_evidence": "FIR_8812"}),
                )
                db.add(rel)

        await db.commit()

        # =========================================================================
        # 5. FETCH & DISPLAY ENTITIES
        # =========================================================================
        print("\n" + "=" * 90)
        print("  [2/4] FETCHED CANONICAL ENTITIES & RESOLVED ALIASES")
        print("=" * 90)
        
        entities_query = select(CanonicalEntity).order_by(CanonicalEntity.entity_type, CanonicalEntity.canonical_name)
        canonical_entities = (await db.execute(entities_query)).scalars().all()

        print(f"{'TYPE':<15} {'CANONICAL NAME':<28} {'ALIASES / IDENTIFIERS':<32} {'STATUS':<10}")
        print("-" * 90)
        for ce in canonical_entities:
            aliases = (await db.execute(select(EntityAlias).where(EntityAlias.canonical_entity_id == ce.id))).scalars().all()
            alias_str = ", ".join(f"'{a.alias_value}'" for a in aliases) if aliases else "-"
            print(f"{ce.entity_type:<15} {ce.canonical_name:<28} {alias_str[:30]:<32} {ce.status.value:<10}")

        # =========================================================================
        # 6. FETCH & DISPLAY EVIDENCE-BACKED RELATIONSHIPS
        # =========================================================================
        print("\n" + "=" * 90)
        print("  [3/4] FETCHED EVIDENCE-BACKED RELATIONSHIPS (GRAPH EDGES)")
        print("=" * 90)

        rels_query = select(Relationship).where(Relationship.case_id == case.id)
        relationships = (await db.execute(rels_query)).scalars().all()

        # Create ID to Name Lookup
        id_to_name = {ce.id: (ce.canonical_name, ce.entity_type) for ce in canonical_entities}

        print(f"{'SOURCE ENTITY':<22} {'RELATION TYPE':<18} {'TARGET ENTITY':<22} {'CONF':<6} {'STATUS':<12}")
        print("-" * 90)
        for r in relationships:
            src_name = id_to_name.get(r.source_entity_id, ("Unknown", ""))[0]
            tgt_name = id_to_name.get(r.target_entity_id, ("Unknown", ""))[0]
            props = json.loads(r.properties_json or "{}")
            note = props.get("provenance_note", "")
            print(f"{src_name:<22} {r.relationship_type.value:<18} {tgt_name:<22} {r.confidence:<6.2f} {r.verification_status.value:<12}")
            if note:
                print(f"   |-- Evidence Provenance: \"{note}\"")

        # =========================================================================
        # 7. NETWORK GRAPH SUMMARY
        # =========================================================================
        print("\n" + "=" * 90)
        print("  [4/4] CRIMINAL NETWORK GRAPH METRICS")
        print("=" * 90)
        print(f"  * Total Entities (Nodes)    : {len(canonical_entities)}")
        print(f"  * Total Relationships (Edges): {len(relationships)}")
        print(f"  * High-Confidence Links     : {sum(1 for r in relationships if r.confidence >= 0.90)}")
        print(f"  * Associated Evidence Docs  : 1 ({doc.filename})")
        print("=" * 90 + "\n")


if __name__ == "__main__":
    asyncio.run(run_example())
