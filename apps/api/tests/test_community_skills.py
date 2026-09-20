import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CommunitySkill, Product
from app.routers.admin import (
    admin_delete_skill,
    admin_get_skill_detail,
    admin_get_skills,
    admin_post_skill,
    admin_put_skill,
    admin_toggle_skill_visibility,
)
from app.routers.public import (
    public_community_skill_copy,
    public_community_skill_detail,
    public_community_skills,
)
from app.schemas import AdminCommunitySkillCreate, AdminCommunitySkillUpdate
from app.services.community_skills import seed_default_community_skills


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        # Add a sample product for relationship testing
        prod = Product(
            slug="chatgpt-plus",
            platform="OpenAI",
            display_name="ChatGPT Plus",
            subtitle="Plus 订阅",
            description="ChatGPT Plus 描述",
            product_type="subscription",
        )
        db.add(prod)
        db.commit()
        yield db


def test_seed_and_public_community_skills(db_session: Session):
    # 1. Seed
    created = seed_default_community_skills(db_session)
    assert created >= 11

    # Idempotent seed
    assert seed_default_community_skills(db_session) == 0

    edited = db_session.scalar(
        select(CommunitySkill).where(CommunitySkill.slug == "pelican-bicycle-benchmark")
    )
    assert edited is not None
    admin_put_skill(
        skill_id=edited.id,
        payload=AdminCommunitySkillUpdate(title="管理员自定义标题", is_visible=False),
        db=db_session,
    )
    assert seed_default_community_skills(db_session) == 0
    persisted = admin_get_skills(q="管理员自定义标题", db=db_session)
    assert persisted.total == 1
    assert persisted.items[0].is_visible is False
    admin_put_skill(
        skill_id=edited.id,
        payload=AdminCommunitySkillUpdate(title="鹈鹕骑自行车 Benchmark", is_visible=True),
        db=db_session,
    )

    # 2. Public listing (All)
    res = public_community_skills(db=db_session)
    assert res.total >= 11
    assert "benchmark" in res.kinds
    assert "skill" in res.kinds
    assert len(res.all_tags) > 0

    # 3. Filter by kind
    benchmark_res = public_community_skills(kind="benchmark", db=db_session)
    assert benchmark_res.total >= 2
    for item in benchmark_res.items:
        assert item.kind == "benchmark"

    # 4. Filter by tag
    tag_res = public_community_skills(tag="UI 审美", db=db_session)
    assert tag_res.total >= 1
    assert any("UI 审美" in item.tags for item in tag_res.items)

    # 5. Detail view and view count increment
    detail = public_community_skill_detail(slug="pelican-bicycle-benchmark", db=db_session)
    assert detail.slug == "pelican-bicycle-benchmark"
    assert detail.view_count == 1
    assert detail.related_product is not None
    assert detail.related_product.slug == "chatgpt-plus"

    product = db_session.scalar(select(Product).where(Product.slug == "chatgpt-plus"))
    product.is_visible = False
    db_session.commit()
    hidden_product_detail = public_community_skill_detail(slug="pelican-bicycle-benchmark", db=db_session)
    assert hidden_product_detail.related_product is None
    assert hidden_product_detail.related_product_slug is None
    product.is_visible = True
    db_session.commit()

    # The hidden-product check above is also a public detail view.
    detail2 = public_community_skill_detail(slug="pelican-bicycle-benchmark", db=db_session)
    assert detail2.view_count == 3

    # 6. Copy count increment
    copy_res = public_community_skill_copy(slug="pelican-bicycle-benchmark", db=db_session)
    assert copy_res == {"status": "ok"}
    detail3 = public_community_skill_detail(slug="pelican-bicycle-benchmark", db=db_session)
    assert detail3.copy_count == 1


def test_admin_community_skill_crud(db_session: Session):
    # 1. Create
    payload = AdminCommunitySkillCreate(
        slug="my-custom-test-skill",
        kind="article",
        title="测试自定义博文分享",
        subtitle="副标题测试",
        summary="这是一篇测试分享文章",
        content_markdown="# 详细正文",
        author_name="测试者",
        author_url="https://example.com",
        tags=["心得", "测试"],
        target_models=["GPT-6"],
        related_product_slug="chatgpt-plus",
        is_pinned=True,
    )
    created = admin_post_skill(payload=payload, db=db_session)
    assert created.slug == "my-custom-test-skill"
    assert created.is_pinned is True

    # Duplicate slug rejected
    with pytest.raises(HTTPException) as exc:
        admin_post_skill(payload=payload, db=db_session)
    assert exc.value.status_code == 409

    # 2. Update
    update_payload = AdminCommunitySkillUpdate(title="修改后的标题", sort_order=42)
    updated = admin_put_skill(skill_id=created.id, payload=update_payload, db=db_session)
    assert updated.title == "修改后的标题"
    assert updated.sort_order == 42

    # 3. Toggle visibility
    toggled = admin_toggle_skill_visibility(skill_id=created.id, db=db_session)
    assert toggled.is_visible is False

    # When hidden, public detail returns 404
    with pytest.raises(HTTPException) as exc:
        public_community_skill_detail(slug="my-custom-test-skill", db=db_session)
    assert exc.value.status_code == 404

    before_copy_count = db_session.scalar(
        select(CommunitySkill.copy_count).where(CommunitySkill.id == created.id)
    )
    with pytest.raises(HTTPException) as exc:
        public_community_skill_copy(slug="my-custom-test-skill", db=db_session)
    assert exc.value.status_code == 404
    assert db_session.scalar(
        select(CommunitySkill.copy_count).where(CommunitySkill.id == created.id)
    ) == before_copy_count

    admin_detail = admin_get_skill_detail(skill_id=created.id, db=db_session)
    assert admin_detail.content_markdown == "# 详细正文"
    assert admin_detail.is_visible is False

    # But admin listing includes it
    admin_list = admin_get_skills(q="修改后的标题", db=db_session)
    assert admin_list.total == 1
    assert admin_list.items[0].is_visible is False

    # Toggle back to visible
    admin_toggle_skill_visibility(skill_id=created.id, db=db_session)
    assert public_community_skill_detail(slug="my-custom-test-skill", db=db_session) is not None

    # 4. Delete
    del_res = admin_delete_skill(skill_id=created.id, db=db_session)
    assert del_res["ok"] is True
    assert admin_get_skills(q="修改后的标题", db=db_session).total == 0


@pytest.mark.parametrize("slug", ["contains/slash", "has space", "query?value", "double--dash"])
def test_community_skill_slug_must_be_url_safe(slug: str):
    with pytest.raises(ValidationError):
        AdminCommunitySkillCreate(slug=slug, title="invalid")
    with pytest.raises(ValidationError):
        AdminCommunitySkillUpdate(slug=slug)


def test_community_skill_slug_is_normalized_to_lowercase():
    assert AdminCommunitySkillCreate(slug="Upper-Case", title="normalized").slug == "upper-case"
    assert AdminCommunitySkillUpdate(slug="Upper-Case").slug == "upper-case"


def test_community_skill_update_rejects_null_for_non_nullable_fields():
    with pytest.raises(ValidationError):
        AdminCommunitySkillUpdate(title=None)
    assert AdminCommunitySkillUpdate(related_product_slug=None).related_product_slug is None


@pytest.mark.parametrize("field", ["author_url", "repo_url"])
@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://example.com", "https://user:pass@example.com"])
def test_community_skill_external_urls_require_safe_https(field: str, url: str):
    with pytest.raises(ValidationError):
        AdminCommunitySkillCreate(slug="safe-url", title="safe", **{field: url})
    with pytest.raises(ValidationError):
        AdminCommunitySkillUpdate(**{field: url})


@pytest.mark.parametrize(
    "url",
    ["https://example.com/demo.html", "//example.com/demo.html", "/demos/../secret.html", "/demos/demo.html?token=secret"],
)
def test_community_skill_demo_url_is_local_html(url: str):
    with pytest.raises(ValidationError):
        AdminCommunitySkillCreate(slug="safe-demo", title="safe", demo_url=url)
    assert AdminCommunitySkillCreate(
        slug="safe-demo", title="safe", demo_url="/demos/benchmarks/example.html"
    ).demo_url == "/demos/benchmarks/example.html"
