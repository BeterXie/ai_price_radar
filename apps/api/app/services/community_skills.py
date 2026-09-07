from __future__ import annotations

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from ..models import CommunitySkill, Product
from ..schemas import (
    AdminCommunitySkillCreate,
    AdminCommunitySkillUpdate,
    CommunitySkillDetailOut,
    CommunitySkillPageOut,
    CommunitySkillSummaryOut,
    RelatedProductSummary,
)



def list_community_skills(
    db: Session,
    *,
    kind: str | None = None,
    tag: str | None = None,
    model: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    visible_only: bool = True,
) -> CommunitySkillPageOut:
    stmt = select(CommunitySkill)
    if visible_only:
        stmt = stmt.where(CommunitySkill.is_visible.is_(True))
    if kind:
        stmt = stmt.where(CommunitySkill.kind == kind)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                CommunitySkill.title.ilike(term),
                CommunitySkill.subtitle.ilike(term),
                CommunitySkill.summary.ilike(term),
                CommunitySkill.author_name.ilike(term),
            )
        )

    # Order: pinned first, then sort_order DESC, then id DESC
    stmt = stmt.order_by(
        CommunitySkill.is_pinned.desc(),
        CommunitySkill.sort_order.desc(),
        CommunitySkill.id.desc(),
    )

    all_items = list(db.scalars(stmt).all())

    # Tag and model filtering in Python (since tags/models are stored as JSON arrays)
    filtered = []
    for item in all_items:
        if tag and tag not in (item.tags or []):
            continue
        if model and model not in (item.target_models or []):
            continue
        filtered.append(item)

    total = len(filtered)
    offset = max(0, (page - 1) * page_size)
    paged = filtered[offset : offset + page_size]

    # Collect kinds and all tags for facet navigation
    base_query = select(CommunitySkill)
    if visible_only:
        base_query = base_query.where(CommunitySkill.is_visible.is_(True))
    visible_skills = list(db.scalars(base_query).all())
    kinds = sorted(list({s.kind for s in visible_skills if s.kind}))
    all_tags = sorted(list({t for s in visible_skills for t in (s.tags or [])}))

    return CommunitySkillPageOut(
        items=[CommunitySkillSummaryOut.model_validate(item, from_attributes=True) for item in paged],
        total=total,
        page=page,
        page_size=page_size,
        kinds=kinds,
        all_tags=all_tags,
    )


def get_community_skill_by_slug(
    db: Session,
    slug: str,
    *,
    visible_only: bool = True,
    increment_view: bool = True,
) -> CommunitySkillDetailOut | None:
    stmt = select(CommunitySkill).where(CommunitySkill.slug == slug)
    if visible_only:
        stmt = stmt.where(CommunitySkill.is_visible.is_(True))
    skill = db.scalar(stmt)
    if not skill:
        return None

    if increment_view:
        skill.view_count += 1
        db.commit()
        db.refresh(skill)

    related_product = None
    if skill.related_product_slug:
        prod = db.scalar(select(Product).where(Product.slug == skill.related_product_slug))
        if prod:
            related_product = RelatedProductSummary(
                slug=prod.slug,
                platform=prod.platform,
                display_name=prod.display_name,
                subtitle=prod.subtitle or "",
                product_type=prod.product_type or "other",
            )

    data = CommunitySkillDetailOut.model_validate(skill, from_attributes=True)
    data.related_product = related_product
    return data


def record_community_skill_copy(db: Session, slug: str) -> bool:
    stmt = select(CommunitySkill).where(CommunitySkill.slug == slug)
    skill = db.scalar(stmt)
    if not skill:
        return False
    skill.copy_count += 1
    db.commit()
    return True


def admin_create_community_skill(db: Session, data: AdminCommunitySkillCreate) -> CommunitySkill:
    skill = CommunitySkill(
        slug=data.slug.strip(),
        kind=data.kind.strip(),
        title=data.title.strip(),
        subtitle=data.subtitle.strip(),
        summary=data.summary.strip(),
        content_markdown=data.content_markdown,
        prompt_template=data.prompt_template,
        author_name=data.author_name.strip(),
        author_url=data.author_url.strip(),
        repo_url=data.repo_url.strip(),
        stars_count=data.stars_count,
        install_command=data.install_command.strip(),
        demo_url=data.demo_url.strip(),
        demo_type=data.demo_type.strip(),
        tags=data.tags or [],
        target_models=data.target_models or [],
        related_product_slug=data.related_product_slug.strip() if data.related_product_slug else None,
        is_pinned=data.is_pinned,
        is_visible=data.is_visible,
        sort_order=data.sort_order,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def admin_update_community_skill(
    db: Session, skill_id: int, data: AdminCommunitySkillUpdate
) -> CommunitySkill | None:
    skill = db.scalar(select(CommunitySkill).where(CommunitySkill.id == skill_id))
    if not skill:
        return None

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if hasattr(skill, key):
            setattr(skill, key, value)

    db.commit()
    db.refresh(skill)
    return skill


def admin_delete_community_skill(db: Session, skill_id: int) -> bool:
    skill = db.scalar(select(CommunitySkill).where(CommunitySkill.id == skill_id))
    if not skill:
        return False
    db.delete(skill)
    db.commit()
    return True


def admin_toggle_community_skill_visibility(db: Session, skill_id: int) -> CommunitySkill | None:
    skill = db.scalar(select(CommunitySkill).where(CommunitySkill.id == skill_id))
    if not skill:
        return None
    skill.is_visible = not skill.is_visible
    db.commit()
    db.refresh(skill)
    return skill


def seed_default_community_skills(db: Session) -> int:
    from .seed_skills_data import INITIAL_SKILLS_DATA

    created_count = 0
    for item in INITIAL_SKILLS_DATA:
        existing = db.scalar(select(CommunitySkill).where(CommunitySkill.slug == item["slug"]))
        if not existing:
            skill = CommunitySkill(**item)
            db.add(skill)
            created_count += 1
        else:
            # Sync target_models and content if updated in seed data
            for key, val in item.items():
                if hasattr(existing, key) and key not in ("id", "created_at", "view_count", "copy_count"):
                    setattr(existing, key, val)
    db.commit()
    return created_count

