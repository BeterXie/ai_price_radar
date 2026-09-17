"""Migration script v15: Subdivide Claude products and reclassify offers.

1. Ensures `claude-pro-20x` and `claude-team` exist in `products`.
2. Updates `claude-pro` display name to "Claude Pro (5x)".
3. Reclassifies existing offers under `claude-pro`:
   - Offers with 'team', '团队', '车位', '席位', '组织' -> `claude-team`
   - Offers with '20x', '20倍', 'max20x', 'max 20x' -> `claude-pro-20x`
   - Remaining standard pro offers stay under `claude-pro` (5x).
Safe and idempotent to run multiple times.
"""

from __future__ import annotations

import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in [
    os.path.join(BASE_DIR, "apps", "api"),
    os.path.join(BASE_DIR, "pipeline"),
    "/app",
]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from app.database import SessionLocal
from app.models import Offer, Product, RawProduct


def migrate_claude_subdivision(dry_run: bool = False) -> None:
    session = SessionLocal()
    try:
        # 1. Ensure claude-pro exists and has updated title
        pro_5x = session.query(Product).filter(Product.slug == "claude-pro").first()
        if pro_5x:
            if pro_5x.display_name != "Claude Pro (5x)":
                print(f"[MIGRATE] Updating claude-pro display_name to 'Claude Pro (5x)'")
                pro_5x.display_name = "Claude Pro (5x)"
                pro_5x.subtitle = "Pro 5x 个人会员订阅"
        else:
            pro_5x = Product(
                slug="claude-pro",
                platform="Claude",
                display_name="Claude Pro (5x)",
                subtitle="Pro 5x 个人会员订阅",
                product_type="subscription",
                description="聚合 Claude Pro (5x) 个人会员订阅公开报价。",
                is_visible=True,
            )
            session.add(pro_5x)
            session.flush()
            print(f"[MIGRATE] Created claude-pro product (id={pro_5x.id})")

        # 2. Ensure claude-pro-20x exists
        pro_20x = session.query(Product).filter(Product.slug == "claude-pro-20x").first()
        if not pro_20x:
            pro_20x = Product(
                slug="claude-pro-20x",
                platform="Claude",
                display_name="Claude Pro 20x",
                subtitle="Pro 20x 满血高配号",
                product_type="subscription",
                description="聚合明确标注为 Claude Pro 20x / Max 20x 的高倍用量公开报价。",
                is_visible=True,
            )
            session.add(pro_20x)
            session.flush()
            print(f"[MIGRATE] Created claude-pro-20x product (id={pro_20x.id})")
        else:
            pro_20x.is_visible = True

        # 3. Ensure claude-team exists
        team = session.query(Product).filter(Product.slug == "claude-team").first()
        if not team:
            team = Product(
                slug="claude-team",
                platform="Claude",
                display_name="Claude Team",
                subtitle="Team 团队版席位与组织号",
                product_type="subscription",
                description="聚合 Claude Team 团队版席位、拼车与独享组织公开报价。",
                is_visible=True,
            )
            session.add(team)
            session.flush()
            print(f"[MIGRATE] Created claude-team product (id={team.id})")
        else:
            team.is_visible = True

        session.commit()

        # 4. Reclassify offers across claude-pro, claude-pro-20x, claude-team
        claude_product_ids = [p.id for p in [pro_5x, pro_20x, team] if p]
        offers = session.query(Offer).filter(Offer.product_id.in_(claude_product_ids)).all()
        print(f"[INFO] Scanning {len(offers)} offers across Claude subscription products...")

        count_5x = 0
        count_20x = 0
        count_team = 0

        team_pattern = re.compile(r"team|团队|车位|席位|企业", re.IGNORECASE)
        pattern_20x = re.compile(r"20x|20倍|max20x|max\s*20x", re.IGNORECASE)

        for offer in offers:
            raw = offer.raw_product
            title = raw.original_name if raw else ""
            category = raw.original_category if raw else ""

            # Check title first (primary intent)
            if team_pattern.search(title):
                target = team
            elif pattern_20x.search(title):
                target = pro_20x
            elif team_pattern.search(category) and not ("pro" in title.lower() and "ios" in title.lower()):
                target = team
            elif pattern_20x.search(category) and not re.search(r"5x|5倍|pro", title, re.IGNORECASE):
                target = pro_20x
            else:
                target = pro_5x

            if target.id == pro_5x.id:
                count_5x += 1
            elif target.id == pro_20x.id:
                count_20x += 1
            elif target.id == team.id:
                count_team += 1

            if target.id != offer.product_id:
                print(f"  Reclassifying offer #{offer.id} ({float(offer.price or 0)} CNY) '{title}': -> {target.slug} (id={target.id})")
                if not dry_run:
                    offer.product_id = target.id

        if not dry_run:
            session.commit()
            print(f"[SUCCESS] Claude offers reclassification complete:")
            print(f"  - Claude Pro (5x): {count_5x}")
            print(f"  - Claude Pro 20x: {count_20x}")
            print(f"  - Claude Team:    {count_team}")
        else:
            print(f"[DRY RUN] Would set 5x: {count_5x}, 20x: {count_20x}, Team: {count_team}.")

    finally:
        session.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate_claude_subdivision(dry_run=dry_run)
