"""Safely import the fictional legacy NetraX CSV dataset into the current backend.

Run from backend/:
  python scripts/import_legacy_netrax_csv.py --data-dir "D:\\path\\NetraX_Step1_CSV_Data" --dry-run
  python scripts/import_legacy_netrax_csv.py --data-dir "D:\\path\\NetraX_Step1_CSV_Data"

Design goals:
- Never delete or update existing unrelated cases/graph data.
- Keep the friend's existing graph untouched.
- Namespace imported canonical entities by source dataset + legacy ID, rather than
  merging them with similarly named entities in the friend's case.
- Preserve legacy aliases, IDs, evidence, CDRs, transactions, and original labels.
- Keep imported relationships UNVERIFIED.
- Make repeated imports idempotent.
"""


from __future__ import annotations


import argparse
import asyncio
import csv



import argparse
import asyncio
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.database import async_session_factory, init_db
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.entity import Entity, EntityType, ExtractionMethod, VerificationStatus
from app.models.canonical_entity import CanonicalEntity, CanonicalEntityStatus, EntityAlias
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

DATASET_KEY = "NetraX_Step1_CSV_Data"
RELATIONSHIP_MAP = {
    "CALLED": "CALLED",
    "OWNS": "OWNS",
    "USES": "USES",
    "STOLE": "USES",
    "TRANSFERRED_MONEY": "TRANSFERRED_TO",
    "TRANSFERRED_TO": "TRANSFERRED_TO",
    "WITNESSED_WITH": "ASSOCIATED_WITH",
    "ASSOCIATED_WITH": "ASSOCIATED_WITH",
    "SEEN_AT": "LOCATED_AT",
    "LOCATED_AT": "LOCATED_AT",
    "HAS_ACCOUNT": "HAS_ACCOUNT",
    "INVOLVED_IN": "INVOLVED_IN",
}
ENTITY_TYPES = {
    "PERSON": EntityType.PERSON,
    "VEHICLE": EntityType.VEHICLE,
    "PHONE": EntityType.PHONE,
    "LOCATION": EntityType.LOCATION,
    "ACCOUNT": EntityType.ACCOUNT,
}


def read_csv(folder: Path, filename: str) -> list[dict[str, str]]:
    path = folder / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def document_type(value: str) -> DocumentType:
    value = (value or "").upper()
    if value in DocumentType.__members__:
        return DocumentType[value]
    return DocumentType.OTHER


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def import_data(folder: Path, dry_run: bool) -> None:
    required = ["cases.csv", "persons.csv", "vehicles.csv", "phones.csv", "locations.csv",
                "bank_accounts.csv", "relationships.csv", "evidence.csv", "cdr.csv", "transactions.csv"]
    missing = [name for name in required if not (folder / name).is_file()]
    if missing:
        raise SystemExit("Missing required CSV file(s): " + ", ".join(missing))

    cases = read_csv(folder, "cases.csv")
    persons = read_csv(folder, "persons.csv")
    vehicles = read_csv(folder, "vehicles.csv")
    phones = read_csv(folder, "phones.csv")
    locations = read_csv(folder, "locations.csv")
    accounts = read_csv(folder, "bank_accounts.csv")
    evidence = read_csv(folder, "evidence.csv")
    legacy_relationships = read_csv(folder, "relationships.csv")
    cdrs = read_csv(folder, "cdr.csv")
    transactions = read_csv(folder, "transactions.csv")
    resolutions = read_csv(folder, "entity_resolution.csv")

    if not cases:
        raise SystemExit("cases.csv contains no case rows.")
    case_row = cases[0]
    case_number = case_row.get("case_id") or "CASE-1023"
    if not evidence:
        raise SystemExit("evidence.csv contains no rows; evidence is required for provenance.")

    # Build all entities by their stable legacy IDs. Names are display labels, not keys.
    specs: dict[str, dict[str, Any]] = {}
    for r in persons:
        specs[r["person_id"]] = {"type": "PERSON", "label": r["name"], "meta": dict(r)}
    for r in vehicles:
        # Include registration in the label so two vehicles of the same model don't merge.
        label = " — ".join(x for x in [r.get("model", ""), r.get("registration", "")] if x)
        specs[r["vehicle_id"]] = {"type": "VEHICLE", "label": label or r["vehicle_id"], "meta": dict(r)}
    for r in phones:
        specs[r["phone_id"]] = {"type": "PHONE", "label": r["phone_number"], "meta": dict(r)}
    for r in locations:
        specs[r["location_id"]] = {"type": "LOCATION", "label": r["name"], "meta": dict(r)}
    for r in accounts:
        specs[r["account_id"]] = {"type": "ACCOUNT", "label": r["masked_account"], "meta": dict(r)}

    unknown_types = sorted({r.get("relationship_type", "").upper() for r in legacy_relationships} - set(RELATIONSHIP_MAP))
    unresolved_legacy = [r.get("relationship_id", "") for r in legacy_relationships
                         if r.get("source_id") not in specs or r.get("target_id") not in specs]
    print("Legacy dataset validation")
    print(f"  Case: {case_number} — {case_row.get('title', 'Vehicle Theft Network')}")
    print(f"  Entity IDs: {len(specs)} (people={len(persons)}, vehicles={len(vehicles)}, phones={len(phones)}, locations={len(locations)}, accounts={len(accounts)})")
    print(f"  Evidence records: {len(evidence)} | original relationships: {len(legacy_relationships)} | CDRs: {len(cdrs)} | transactions: {len(transactions)}")
    print(f"  Unknown relationship labels: {unknown_types or 'none'}")
    print(f"  Relationship rows with missing entity IDs: {unresolved_legacy or 'none'}")
    if dry_run:
        print("DRY RUN: no records were inserted or changed.")
        print("Planned graph edges include original relationships, phone-to-phone CDR calls, account transfers, person-to-phone links, and person-to-account links.")
        return

    # init_db can configure the SQLite fallback/session factory, so call it first.
    await init_db()
    async with async_session_factory() as db:
        existing_case = (await db.execute(select(Case).where(Case.case_number == case_number))).scalar_one_or_none()
        if existing_case and existing_case.title != (case_row.get("title") or "Vehicle Theft Network"):
            raise SystemExit(
                f"Safety stop: {case_number} already belongs to a different case title "
                f"({existing_case.title!r}). No changes made. Choose a different legacy case number first."
            )
        case = existing_case
        if case is None:
            status_raw = (case_row.get("status") or "OPEN").upper()
            status = CaseStatus.UNDER_INVESTIGATION if status_raw in {"ACTIVE", "UNDER_INVESTIGATION"} else CaseStatus.OPEN
            case = Case(
                case_number=case_number[:50],
                title=(case_row.get("title") or "Vehicle Theft Network")[:255],
                description=(case_row.get("description") or "Imported fictional NetraX vehicle-theft dataset.")
                            + f"\n[Legacy dataset: {DATASET_KEY}]",
                status=status,
            )
            db.add(case)
            await db.flush()
        case_id = case.id

        # Helper: reuse imported documents only when case + filename + marker match.
        async def get_or_create_doc(filename: str, dtype: DocumentType, content: str, source: str) -> Document:
            doc = (await db.execute(select(Document).where(
                Document.case_id == case_id,
                Document.filename == filename,
                Document.uploaded_by == f"legacy-csv-import:{DATASET_KEY}",
            ))).scalar_one_or_none()
            if doc:
                return doc
            doc = Document(
                case_id=case_id,
                filename=filename[:255], original_filename=filename[:255],
                document_type=dtype, mime_type="text/plain",
                file_size=len(content.encode("utf-8")), file_hash=digest(content),
                storage_path=f"legacy-csv://{case_number}/{filename}",
                source=source[:255], description=content,
                processing_status=ProcessingStatus.COMPLETED,
                uploaded_by=f"legacy-csv-import:{DATASET_KEY}",
            )
            db.add(doc)
            await db.flush()
            return doc

        # Evidence documents preserve their own evidence IDs and content.
        evidence_doc_by_id: dict[str, str] = {}
        for ev in evidence:
            ev_id = ev.get("evidence_id", "")
            content = ev.get("content", "")
            doc = await get_or_create_doc(
                ev.get("filename") or f"{ev_id}.txt",
                document_type(ev.get("type", "")),
                content,
                ev.get("source") or f"Legacy evidence {ev_id}",
            )
            evidence_doc_by_id[ev_id] = doc.id

        # Dedicated provenance documents for structured CDR and transaction records.
        cdr_doc = await get_or_create_doc(
            "legacy_cdr_records.csv", DocumentType.CDR,
            json.dumps(cdrs, ensure_ascii=False), "Legacy CDR CSV records",
        )
        tx_doc = await get_or_create_doc(
            "legacy_transactions.csv", DocumentType.FINANCIAL_RECORD,
            json.dumps(transactions, ensure_ascii=False), "Legacy financial transaction CSV records",
        )
        manifest_text = json.dumps({"dataset": DATASET_KEY, "entity_ids": list(specs.keys())}, ensure_ascii=False)
        manifest_doc = await get_or_create_doc(
            "legacy_dataset_index.json", DocumentType.OTHER, manifest_text, "Legacy dataset index and entity provenance",
        )

        # Locate existing imported canonical entities by dataset marker + legacy ID.
        # Do NOT merge by display name with the friend's already-working case.
        existing_ces = (await db.execute(select(CanonicalEntity))).scalars().all()
        ce_by_legacy_id: dict[str, CanonicalEntity] = {}
        for ce in existing_ces:
            try:
                meta = json.loads(ce.metadata_json or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if meta.get("legacy_dataset") == DATASET_KEY and meta.get("legacy_case_number") == case_number:
                legacy_id = meta.get("legacy_id")
                if legacy_id:
                    ce_by_legacy_id[legacy_id] = ce

        canonical_id_by_legacy_id: dict[str, str] = {}
        for legacy_id, spec in specs.items():
            ce = ce_by_legacy_id.get(legacy_id)
            if ce is None:
                metadata = dict(spec["meta"])
                metadata.update({"legacy_dataset": DATASET_KEY, "legacy_case_number": case_number,
                                 "legacy_id": legacy_id, "legacy_entity_type": spec["type"]})
                ce = CanonicalEntity(
                    entity_type=spec["type"], canonical_name=spec["label"][:500],
                    normalized_name=normalize(spec["label"])[:500],
                    status=CanonicalEntityStatus.ACTIVE,
                    metadata_json=json.dumps(metadata, ensure_ascii=False),
                )
                db.add(ce)
                await db.flush()
                ce_by_legacy_id[legacy_id] = ce
            canonical_id_by_legacy_id[legacy_id] = ce.id

            # Create a Phase-1 entity + alias on the dataset index document if absent.
            existing_aliases = (await db.execute(select(EntityAlias).where(
                EntityAlias.canonical_entity_id == ce.id,
                EntityAlias.source_document_id == manifest_doc.id,
            ))).scalars().all()
            existing_alias_norms = {normalize(a.alias_value) for a in existing_aliases}
            alias_candidates = [spec["label"]]
            if spec["type"] == "PERSON":
                person_row = next((r for r in persons if r["person_id"] == legacy_id), {})
                if person_row.get("alias"):
                    alias_candidates.append(person_row["alias"])
                for resolution in resolutions:
                    if resolution.get("resolved_person_id") == legacy_id:
                        alias_candidates.extend([resolution.get("record_a", ""), resolution.get("record_b", "")])
            for alias_value in dict.fromkeys(x.strip() for x in alias_candidates if x and x.strip()):
                alias_norm = normalize(alias_value)
                if alias_norm in existing_alias_norms:
                    continue
                entity = Entity(
                    document_id=manifest_doc.id,
                    entity_type=ENTITY_TYPES[spec["type"]],
                    value=alias_value[:500], normalized_value=alias_norm[:500],
                    confidence=1.0, extraction_method=ExtractionMethod.MANUAL,
                    verification_status=VerificationStatus.UNVERIFIED,
                    notes=f"Legacy alias from {DATASET_KEY}; legacy entity ID={legacy_id}. Alias does not imply wrongdoing.",
                )
                db.add(entity)
                await db.flush()
                db.add(EntityAlias(
                    canonical_entity_id=ce.id, entity_id=entity.id,
                    alias_value=alias_value[:500], normalized_value=alias_norm[:500],
                    source_document_id=manifest_doc.id,
                ))
                existing_alias_norms.add(alias_norm)

        await db.flush()

        created = 0
        skipped = 0

        async def add_relationship(source_legacy: str, target_legacy: str, rel_type: str,
                                  source_record_id: str, source_document_id: str | None,
                                  confidence: float, properties: dict[str, Any]) -> None:
            nonlocal created, skipped
            if source_legacy not in canonical_id_by_legacy_id or target_legacy not in canonical_id_by_legacy_id:
                skipped += 1
                return
            existing = (await db.execute(select(Relationship).where(
                Relationship.case_id == case_id,
                Relationship.source_record_id == source_record_id,
            ))).scalars().first()
            if existing:
                return
            try:
                relationship_enum = RelationshipType(rel_type)
            except ValueError:
                skipped += 1
                return
            db.add(Relationship(
                relationship_type=relationship_enum,
                source_entity_id=canonical_id_by_legacy_id[source_legacy],
                target_entity_id=canonical_id_by_legacy_id[target_legacy],
                source_document_id=source_document_id,
                source_record_id=source_record_id[:100],
                extraction_method="LEGACY_CSV_IMPORT",
                confidence=max(0.0, min(1.0, confidence)),
                verification_status=RelationshipVerificationStatus.UNVERIFIED,
                properties_json=json.dumps(properties, ensure_ascii=False),
                case_id=case_id,
            ))
            created += 1

        # Preserve all explicit relationship.csv rows, including original label and IDs.
        for row in legacy_relationships:
            old_type = row.get("relationship_type", "").upper()
            mapped = RELATIONSHIP_MAP.get(old_type)
            if not mapped:
                skipped += 1
                continue
            ev_id = row.get("evidence_id", "")
            src_doc = evidence_doc_by_id.get(ev_id)
            if not src_doc and ev_id.startswith("CDR"):
                src_doc = cdr_doc.id
            await add_relationship(
                row.get("source_id", ""), row.get("target_id", ""), mapped,
                row.get("relationship_id") or f"REL:{row.get('source_id')}:{row.get('target_id')}:{old_type}",
                src_doc, parse_float(row.get("confidence")),
                {"legacy_relationship_id": row.get("relationship_id"),
                 "legacy_relationship_type": old_type,
                 "legacy_source_id": row.get("source_id"), "legacy_target_id": row.get("target_id"),
                 "legacy_evidence_id": ev_id,
                 "mapping_note": "Original label preserved; imported UNVERIFIED; mapping requires investigator review."},
            )

        # CDRs explicitly record phone-to-phone calls, with time/duration/location provenance.
        for row in cdrs:
            props = {"cdr_id": row.get("cdr_id"), "date": row.get("date"), "time": row.get("time"),
                     "duration_seconds": parse_int(row.get("duration_seconds")),
                     "location_id": row.get("location_id"), "source": "cdr.csv"}
            await add_relationship(
                row.get("caller_phone_id", ""), row.get("receiver_phone_id", ""), "CALLED",
                f"DERIVED:{row.get('cdr_id')}:PHONE_CALL", cdr_doc.id, 0.95, props,
            )

        # Transactions explicitly record account-to-account transfers.
        for row in transactions:
            props = {"transaction_id": row.get("transaction_id"), "amount": row.get("amount"),
                     "currency": row.get("currency"), "date": row.get("date"),
                     "note": row.get("note"), "source": "transactions.csv"}
            await add_relationship(
                row.get("from_account_id", ""), row.get("to_account_id", ""), "TRANSFERRED_TO",
                f"DERIVED:{row.get('transaction_id')}:ACCOUNT_TRANSFER", tx_doc.id, 0.95, props,
            )

        # Explicit owner IDs in the CSV establish person-phone and person-account links.
        for row in phones:
            owner = row.get("owner_person_id", "")
            if owner:
                await add_relationship(owner, row.get("phone_id", ""), "USES",
                    f"DERIVED:{row.get('phone_id')}:PHONE_OWNER", cdr_doc.id, 0.9,
                    {"source": "phones.csv", "ownership_field": "owner_person_id"})
        for row in accounts:
            owner = row.get("owner_person_id", "")
            if owner:
                await add_relationship(owner, row.get("account_id", ""), "HAS_ACCOUNT",
                    f"DERIVED:{row.get('account_id')}:ACCOUNT_OWNER", tx_doc.id, 0.9,
                    {"source": "bank_accounts.csv", "ownership_field": "owner_person_id"})

        await db.commit()
        total_case_rels = (await db.execute(select(Relationship).where(Relationship.case_id == case_id))).scalars().all()
        print("\nImport completed successfully.")
        print(f"Case: {case.case_number} | database UUID: {case_id}")
        print(f"Canonical entities mapped: {len(canonical_id_by_legacy_id)}")
        print(f"New relationships inserted this run: {created}")
        print(f"Rows skipped because of unmapped/missing IDs: {skipped}")
        print(f"Total relationships now attached to this case: {len(total_case_rels)}")
        print("All imported relationships remain UNVERIFIED; inspect the graph and provenance before treating them as confirmed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the legacy NetraX CSV dataset safely.")
    parser.add_argument("--data-dir", required=True, help="Folder containing the CSV files")
    parser.add_argument("--dry-run", action="store_true", help="Validate CSVs and report counts without database writes")
    args = parser.parse_args()
    asyncio.run(import_data(Path(args.data_dir).resolve(), args.dry_run))

if __name__ == "__main__":
    main()
