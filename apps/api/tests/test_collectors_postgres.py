import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from scripts.migrate_collectors_v28 import migrate
from app.models import CollectorJob
from app.routers.collectors import Claim,claim


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL') and not os.getenv('SITE_TEST_DATABASE_URL'),reason='PostgreSQL integration URL required')
def test_migration_and_concurrent_claim_are_exclusive():
    url=os.getenv('TEST_POSTGRES_URL') or os.environ['SITE_TEST_DATABASE_URL']
    admin=create_engine(url)
    schema='collector_test_'+uuid4().hex
    with admin.begin() as conn:conn.execute(text('CREATE SCHEMA '+schema))
    engine=create_engine(url,connect_args={'options':'-csearch_path='+schema})
    try:
        migrate(engine)
        identity=str(uuid4())
        with Session(engine) as db:
            db.add(CollectorJob(id=identity,kind='inventory',release='test',active_lane='catalog',sources=[]))
            db.commit()
        migrate(engine)
        barrier=Barrier(2)
        def take(i):
            with Session(engine) as db:
                barrier.wait()
                return claim(Claim(worker_id='worker-'+str(i),release='test'),db)
        with ThreadPoolExecutor(max_workers=2) as pool:
            values=list(pool.map(take,[1,2]))
        assert sum(value is not None for value in values)==1
        with Session(engine) as db:
            assert db.get(CollectorJob,identity).attempts==1
    finally:
        engine.dispose()
        with admin.begin() as conn:conn.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()
