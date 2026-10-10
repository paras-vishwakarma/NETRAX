"""
Cases API — CRUD operations for investigation cases.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.case import Case, CaseStatus
from app.models.document import Document
from app.schemas.case import CaseCreate, CaseUpdate, CaseResponse, CaseListResponse

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(data: CaseCreate, db: AsyncSession = Depends(get_db)):
    """Create a new investigation case."""
    # Check for duplicate case number
    existing = await db.execute(
        select(Case).where(Case.case_number == data.case_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case with number '{data.case_number}' already exists",
        )

    try:
        case_status = CaseStatus(data.status)
    except ValueError:
        case_status = CaseStatus.OPEN

    case = Case(
        case_number=data.case_number,
        title=data.title,
        description=data.description,
        status=case_status,
    )
    db.add(case)
    await db.flush()

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        status=case.status.value,
        document_count=0,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(db: AsyncSession = Depends(get_db)):
    """List all investigation cases."""
    result = await db.execute(
        select(Case).order_by(Case.created_at.desc())
    )
    cases = result.scalars().all()

    case_responses = []
    for case in cases:
        # Count documents per case
        doc_count_result = await db.execute(
            select(func.count(Document.id)).where(Document.case_id == case.id)
        )
        doc_count = doc_count_result.scalar() or 0

        case_responses.append(CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status.value,
            document_count=doc_count,
            created_at=case.created_at,
            updated_at=case.updated_at,
        ))

    return CaseListResponse(cases=case_responses, total=len(case_responses))


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    """Get case details by ID."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.case_id == case.id)
    )
    doc_count = doc_count_result.scalar() or 0

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        status=case.status.value,
        document_count=doc_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(case_id: str, data: CaseUpdate, db: AsyncSession = Depends(get_db)):
    """Update case details."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if data.title is not None:
        case.title = data.title
    if data.description is not None:
        case.description = data.description
    if data.status is not None:
        try:
            case.status = CaseStatus(data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    await db.flush()

    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.case_id == case.id)
    )
    doc_count = doc_count_result.scalar() or 0

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        status=case.status.value,
        document_count=doc_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(case_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an investigation case and all associated documents & entities."""
    import os
    import shutil
    from sqlalchemy import delete
    from app.models.relationship import Relationship
    from app.models.canonical_entity import CanonicalEntity, EntityAlias
    from app.models.entity import Entity
    from app.models.entity_match_candidate import EntityMatchCandidate

    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get document IDs under this case
    doc_results = await db.execute(select(Document).where(Document.case_id == case_id))
    documents = doc_results.scalars().all()
    doc_ids = [doc.id for doc in documents]

    # Clean up uploaded physical files for documents under this case
    for doc in documents:
        if doc.storage_path and os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
                parent_dir = os.path.dirname(doc.storage_path)
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    shutil.rmtree(parent_dir, ignore_errors=True)
            except Exception:
                pass

    if doc_ids:
        # Fetch entity IDs belonging to these documents
        ent_results = await db.execute(select(Entity.id).where(Entity.document_id.in_(doc_ids)))
        entity_ids = [row[0] for row in ent_results.all()]

        if entity_ids:
            # Delete EntityMatchCandidates referencing these entities
            await db.execute(
                delete(EntityMatchCandidate).where(
                    (EntityMatchCandidate.entity_a_id.in_(entity_ids)) |
                    (EntityMatchCandidate.entity_b_id.in_(entity_ids))
                )
            )

            # Delete EntityAliases referencing these entities or documents
            await db.execute(
                delete(EntityAlias).where(
                    (EntityAlias.entity_id.in_(entity_ids)) |
                    (EntityAlias.source_document_id.in_(doc_ids))
                )
            )

        # Delete Relationships referencing these documents or case
        await db.execute(
            delete(Relationship).where(
                (Relationship.case_id == case_id) |
                (Relationship.source_document_id.in_(doc_ids))
            )
        )
    else:
        # Delete case relationships if no docs
        await db.execute(delete(Relationship).where(Relationship.case_id == case_id))

    # Delete case (cascades to documents, pages, entities, mentions via ORM cascade)
    await db.delete(case)
    await db.commit()

    # Clean up orphaned canonical entities with no aliases left
    try:
        subq = select(EntityAlias.canonical_entity_id).distinct()
        await db.execute(delete(CanonicalEntity).where(CanonicalEntity.id.not_in(subq)))
        await db.commit()
    except Exception as exc:
        pass

    return None
