from __future__ import annotations

from sqlalchemy import cast, delete, func, or_, select, update
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



def _json_array_contains(db: Session, column, value: str):
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return cast(column, JSONB).contains([value])
    members = func.json_each(column).table_valued("value")
    return select(1).select_from(members).where(members.c.value == value).exists()


_SUMMARY_COLUMNS = (
    CommunitySkill.id,
    CommunitySkill.slug,
    CommunitySkill.kind,
    CommunitySkill.title,
    CommunitySkill.subtitle,
    CommunitySkill.summary,
    CommunitySkill.author_name,
    CommunitySkill.author_url,
    CommunitySkill.repo_url,
    CommunitySkill.stars_count,
    CommunitySkill.install_command,
    CommunitySkill.demo_url,
    CommunitySkill.demo_type,
    CommunitySkill.tags,
    CommunitySkill.target_models,
    CommunitySkill.related_product_slug,
    CommunitySkill.is_pinned,
    CommunitySkill.is_visible,
    CommunitySkill.sort_order,
    CommunitySkill.view_count,
    CommunitySkill.copy_count,
    CommunitySkill.created_at,
    CommunitySkill.updated_at,
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
    conditions = []
    if visible_only:
        conditions.append(CommunitySkill.is_visible.is_(True))
    if kind:
        conditions.append(CommunitySkill.kind == kind)
    if search:
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                CommunitySkill.title.ilike(term),
                CommunitySkill.subtitle.ilike(term),
                CommunitySkill.summary.ilike(term),
                CommunitySkill.author_name.ilike(term),
            )
        )
    if tag:
        conditions.append(_json_array_contains(db, CommunitySkill.tags, tag))
    if model:
        conditions.append(_json_array_contains(db, CommunitySkill.target_models, model))

    total = int(db.scalar(
        select(func.count(CommunitySkill.id)).where(*conditions)
    ) or 0)
    offset = max(0, (page - 1) * page_size)
    page_stmt = select(*_SUMMARY_COLUMNS).where(*conditions).order_by(
        CommunitySkill.is_pinned.desc(),
        CommunitySkill.sort_order.desc(),
        CommunitySkill.id.desc(),
    ).offset(offset).limit(page_size)
    paged = list(db.execute(page_stmt).mappings())

    # Collect kinds and all tags for facet navigation
    facet_conditions = []
    if visible_only:
        facet_conditions.append(CommunitySkill.is_visible.is_(True))
    kinds = sorted(
        value
        for value in db.scalars(
            select(CommunitySkill.kind).where(*facet_conditions).distinct()
        )
        if value
    )
    all_tags = sorted({
        tag_value
        for tags in db.scalars(select(CommunitySkill.tags).where(*facet_conditions))
        for tag_value in (tags or [])
        if tag_value
    })

    return CommunitySkillPageOut(
        items=[CommunitySkillSummaryOut.model_validate(dict(item)) for item in paged],
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
        db.execute(
            update(CommunitySkill)
            .where(CommunitySkill.id == skill.id)
            .values(view_count=CommunitySkill.view_count + 1)
        )
        db.commit()
        db.refresh(skill)

    related_product = None
    if skill.related_product_slug:
        product_stmt = select(Product).where(Product.slug == skill.related_product_slug)
        if visible_only:
            product_stmt = product_stmt.where(Product.is_visible.is_(True))
        prod = db.scalar(product_stmt)
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
    if visible_only and related_product is None:
        data.related_product_slug = None
    return data


def record_community_skill_copy(db: Session, slug: str) -> bool:
    result = db.execute(
        update(CommunitySkill)
        .where(
            CommunitySkill.slug == slug,
            CommunitySkill.is_visible.is_(True),
        )
        .values(copy_count=CommunitySkill.copy_count + 1)
    )
    if result.rowcount != 1:
        db.rollback()
        return False
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
    db.commit()
    return created_count
