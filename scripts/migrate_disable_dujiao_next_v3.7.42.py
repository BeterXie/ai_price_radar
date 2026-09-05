from app.database import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        print("=== Disabling Dujiao-Next shops ===")
        res_shops = conn.execute(text("""
            UPDATE shops
            SET is_visible = false
            WHERE platform = 'dujiao_next'
        """))
        print(f"Updated {res_shops.rowcount} shops to is_visible = false")

        print("=== Disabling and hiding offers under Dujiao-Next shops ===")
        res_offers = conn.execute(text("""
            UPDATE offers
            SET active = false,
                approved = false,
                hidden_reason = 'platform_disabled'
            WHERE shop_id IN (SELECT id FROM shops WHERE platform = 'dujiao_next')
              AND (active = true OR approved = true OR hidden_reason IS NULL OR hidden_reason != 'platform_disabled')
        """))
        print(f"Updated {res_offers.rowcount} offers to active=false, approved=false, hidden_reason='platform_disabled'")

        print("=== Disabling source_intakes for Dujiao-Next ===")
        res_intakes = conn.execute(text("""
            UPDATE source_intakes
            SET status = 'disabled'
            WHERE (source_type = 'dujiao_next' OR detected_platform = 'dujiao_next')
              AND status != 'disabled'
        """))
        print(f"Updated {res_intakes.rowcount} source_intakes to status='disabled'")

if __name__ == "__main__":
    run()
