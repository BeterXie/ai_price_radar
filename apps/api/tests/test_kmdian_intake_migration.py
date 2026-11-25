import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from app.services.source_platform import kmdian_identity, prepare_source_submission


@pytest.mark.parametrize('url', ['https://kmdian.com/shop/JOJO?ref=source', 'https://www.kmdian.com:443/shop/JOJO/'])
def test_kmdian_shop_identity_is_canonical_without_network(url):
    result = prepare_source_submission(url)
    assert result.platform == 'kmdian'
    assert result.source_url == 'https://www.kmdian.com/shop/JOJO'
    assert result.shop_token == 'kmdian-JOJO'


@pytest.mark.parametrize('url', ['https://www.kmdian.com.evil.test/shop/X','https://www.kmdian.com:444/shop/X',
    'https://other.test/?next=https://www.kmdian.com/shop/X','https://www.kmdian.com/shop/../admin',
    'https://www.kmdian.com/api/v1/open/products','https://www.kmdian.com:0/shop/S1','https://www.kmdian.com/shop/A/p/KM1'])
def test_kmdian_lookalikes_and_nonstore_urls_are_not_trusted(url):
    assert kmdian_identity(url) is None


def test_port_zero_is_rejected_at_submission_entry():
    with pytest.raises(ValueError):prepare_source_submission('https://www.kmdian.com:0/shop/S1')


@pytest.mark.skipif(not os.getenv('SITE_TEST_DATABASE_URL'),reason='Disposable PostgreSQL not configured')
def test_kmdian_v29_migration_is_repeatable_and_keeps_existing_intakes():
    base = create_engine(os.environ['SITE_TEST_DATABASE_URL'])
    schema='kmdian_'+uuid4().hex
    with base.begin() as c:c.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine=create_engine(os.environ['SITE_TEST_DATABASE_URL'],connect_args={'options':f'-csearch_path={schema}'})
    spec=importlib.util.spec_from_file_location('kmdian_migration',Path(__file__).resolve().parents[3]/'scripts/migrate_kmdian_intakes_v29.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    try:
        with engine.begin() as c:
            c.execute(text("CREATE TABLE source_intakes (id int PRIMARY KEY,source_type text CONSTRAINT ck_source_intakes_type CHECK(source_type IN ('other','ldxp')))"))
            c.execute(text("INSERT INTO source_intakes VALUES (1,'ldxp')"))
        module.migrate(engine);module.migrate(engine)
        with engine.begin() as c:
            c.execute(text("INSERT INTO source_intakes VALUES (2,'kmdian')"))
            assert c.execute(text('SELECT source_type FROM source_intakes WHERE id=1')).scalar()=='ldxp'
    finally:
        engine.dispose()
        with base.begin() as c:c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base.dispose()
