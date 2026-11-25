"""Reconcile official KMDian submissions against a successfully imported platform feed."""
from sqlalchemy import inspect, select, text, update, func, or_
from common import Offer, RawProduct, Shop, Product
from common import utcnow
from types import SimpleNamespace
from app.services.source_platform import kmdian_identity


def lock_intakes(db):
    if not inspect(db.connection()).has_table("source_intakes"):
        return []
    query = text("SELECT * FROM source_intakes WHERE source_url LIKE 'https://%kmdian.com/%' ORDER BY id"
                 + (" FOR UPDATE" if db.get_bind().dialect.name == "postgresql" else ""))
    return [dict(row) for row in db.execute(query).mappings() if kmdian_identity(row['source_url'])]


def allowed_records(records, intakes):
    denied = {kmdian_identity(row['source_url']).source_url for row in intakes
              if row['status'] in {'rejected','disabled','needs_re_review'}}
    for record in records:
        if not any((identity := kmdian_identity(record.get(field))) and identity.source_url in denied
                   for field in ('shop_url','product_url')):
            yield record


def remove_denied_offers(db, intakes, snapshot_id):
    denied = {kmdian_identity(row['source_url']).source_url for row in intakes
              if row['status'] in {'rejected','disabled','needs_re_review'}}
    if not denied:return
    rows = db.execute(select(Offer.id, Shop.source_url, RawProduct.source_url.label('product_url'))
        .join(Shop, Shop.id==Offer.shop_id).join(RawProduct, RawProduct.id==Offer.raw_product_id)
        .where(Offer.snapshot_id==snapshot_id, Shop.platform=='kmdian')).mappings().all()
    removed = [r for r in rows if any((identity:=kmdian_identity(r[k])) and identity.source_url in denied
                                    for k in ('source_url','product_url'))]
    if removed:
        ids = {r['id'] for r in removed}
        db.execute(update(Offer).where(Offer.id.in_(ids)).values(snapshot_id=None))
        affected = {identity.source_url for r in removed for k in ('source_url','product_url') if (identity:=kmdian_identity(r[k]))}
        related = [r for r in intakes if r['status']=='published' and kmdian_identity(r['source_url']).source_url in affected]
        finish_intakes(db,related,SimpleNamespace(offer_ids={r['id'] for r in rows}-ids,new_shop_tokens=set()),snapshot_id,utcnow())


def finish_intakes(db, intakes, imported, snapshot_id, now):
    from publish_catalog import public_offer_count, enqueue_published_intake_notifications
    rows = db.execute(select(Offer.id, Shop.token, Shop.name, Shop.source_url, RawProduct.source_url.label('product_url'))
        .join(Shop, Shop.id == Offer.shop_id).join(RawProduct, RawProduct.id == Offer.raw_product_id)
        .where(Offer.id.in_(imported.offer_ids), Shop.platform == 'kmdian')).mappings().all()
    by_url = {}
    for row in rows:
        for field in ('source_url','product_url'):
            identity = kmdian_identity(row[field])
            if identity:by_url.setdefault(identity.source_url, []).append(row)
    for intake in intakes:
        if intake['status'] not in {'submitted','pending_review','approved','published','no_products','validation_failed'}:
            continue
        identity = kmdian_identity(intake['source_url'])
        matches = by_url.get(identity.source_url, [])
        if not matches:
            if intake['status'] == 'published':
                db.execute(text("UPDATE source_intakes SET status='no_products',product_count=0,decision_note='平台完整目录中已无对应商品，等待后续同步',updated_at=:now,finished_at=:now WHERE id=:id"),
                           {'id':intake['id'],'now':now})
                enqueue_published_intake_notifications(db,intake_id=intake['id'],intake_status='no_products',product_count=0,published_at=now,transition_snapshot_id=snapshot_id)
            continue  # An absent entry cannot approve a new submission.
        tokens = {row['token'] for row in matches}
        if len(tokens) != 1:raise ValueError('KMDian intake identity is ambiguous')
        visible_ids = set(db.scalars(select(Offer.id).join(Shop, Shop.id==Offer.shop_id)
            .join(Product, Product.id==Offer.product_id).where(Offer.id.in_({r['id'] for r in matches}),
            Product.is_visible.is_(True),Shop.status!='closed',
            or_(Offer.hidden_reason.is_(None),func.trim(Offer.hidden_reason)==''))))
        count = public_offer_count(db, snapshot_id=snapshot_id, offer_ids=visible_ids)
        status = 'published' if count else 'no_products'
        # Historical rows may share a key across source types. Keep every
        # request and its moderation/notification history instead of merging.
        conflict = db.execute(text("SELECT id FROM source_intakes WHERE source_type='kmdian' AND source_key=:key AND id<>:id"),
                              {'key':intake['source_key'],'id':intake['id']}).scalar()
        source_type = intake['source_type'] if conflict else 'kmdian'
        db.execute(text("""UPDATE source_intakes SET source_type=:source_type,detected_platform='kmdian',status=:status,
            shop_name=:name,product_count=:count,approved_at=COALESCE(approved_at,:now),finished_at=:now,updated_at=:now,
            lease_expires_at=NULL,failure_reason='',decision_note=:note WHERE id=:id"""),
            {'id':intake['id'],'source_type':source_type,'status':status,'name':matches[0]['name'],'count':count,'now':now,
             'note':'卡密小店平台 API 已核实，商品已发布' if count else '平台 API 已核实，暂未有可公开分类的商品'})
        if intake['status'] != status:
            enqueue_published_intake_notifications(db,intake_id=intake['id'],intake_status=status,product_count=count,
                published_at=now,preferred_shop_token=matches[0]['token'],new_shop_tokens=imported.new_shop_tokens,transition_snapshot_id=snapshot_id)
