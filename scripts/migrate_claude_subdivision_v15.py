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
from app.models import Offer, Product


def migrate_claude_subdivision(dry_run: bool = False) -> None:
    session = SessionLocal()
    try:
        # 1. Ensure claude-pro exists and has updated title
        pro_5x = session.query(Product).filter(Product.slug == "claude-pro").first()
        if pro_5x:
            if pro_5x.display_name != "Claude Pro (5x)":
                print("[MIGRATE] Updating claude-pro display_name to 'Claude Pro (5x)'")
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

        session.flush()
        if not dry_run:
            session.commit()
        else:
            # Roll back product creation/renames performed above so --dry-run
            # never leaves the database modified.
            session.rollback()
            pro_5x = session.query(Product).filter(Product.slug == "claude-pro").first()
            pro_20x = session.query(Product).filter(Product.slug == "claude-pro-20x").first()
            team = session.query(Product).filter(Product.slug == "claude-team").first()

        # 4. Reclassify offers across claude-pro, claude-pro-20x, claude-team
        claude_product_ids = [p.id for p in [pro_5x, pro_20x, team] if p]
        # Also scan `claude-account`: the legacy classifier only routed titles
        # containing "claude pro"/"claude会员" into subscriptions, so 20x/Team
        # offers currently live under the account product and must be migrated out.
        account_product = session.query(Product).filter(Product.slug == "claude-account").first()
        if account_product is not None:
            claude_product_ids.append(account_product.id)
        offers = session.query(Offer).filter(Offer.product_id.in_(claude_product_ids)).all()
        print(f"[INFO] Scanning {len(offers)} offers across Claude subscription/account products...")

        count_5x = 0
        count_20x = 0
        count_team = 0
        count_skipped_locked = 0

        team_pattern = re.compile(r"team|团队|车位|席位|企业", re.IGNORECASE)
        pattern_20x = re.compile(r"20x|20倍|max20x|max\s*20x", re.IGNORECASE)
        subscription_evidence = re.compile(
            r"max\s*20x|20x|20倍|team|团队|车位|席位|组织|订阅|subscription", re.IGNORECASE
        )

        for offer in offers:
            raw = offer.raw_product
            title = raw.original_name if raw else ""
            category = raw.original_category if raw else ""

            # Respect manual locks: the pipeline treats offers tagged
            # `manual_override` (or confidence 100) as human-corrected; do not
            # silently overwrite an administrator's classification.
            tags = offer.tags or []
            if "manual_override" in tags or (offer.classification_confidence or 0) >= 100:
                count_skipped_locked += 1
                continue

            # Account offers are only migrated when they clearly match the new
            # subscription tiers; everything else stays an account product.
            if account_product is not None and offer.product_id == account_product.id:
                if not subscription_evidence.search(title):
                    continue

            # Check title first (primary intent)
            if team_pattern.search(title):
                target = team
            elif pattern_20x.search(title):
                target = pro_20x
            elif team_pattern.search(category) and not ("pro" in title.lower() and "ios" in title.lower()):
                target = team
            elif pattern_20x.search(category) and not re.search(r"5x|5倍|pro", title, re.IGNORECASE):
                target = pro_20x
            elif account_product is not None and offer.product_id == account_product.id:
                # Matched subscription evidence but no tier keyword: keep as-is
                continue
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
            print("[SUCCESS] Claude offers reclassification complete:")
            print(f"  - Claude Pro (5x): {count_5x}")
            print(f"  - Claude Pro 20x: {count_20x}")
            print(f"  - Claude Team:    {count_team}")
            if count_skipped_locked:
                print(f"  - Skipped (manually locked): {count_skipped_locked}")
        else:
            session.rollback()
            print(f"[DRY RUN] Would set 5x: {count_5x}, 20x: {count_20x}, Team: {count_team}.")
            if count_skipped_locked:
                print(f"[DRY RUN] Skipped (manually locked): {count_skipped_locked}")

    finally:
        session.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate_claude_subdivision(dry_run=dry_run)
