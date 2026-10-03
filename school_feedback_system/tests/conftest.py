import pytest
from sqlalchemy import create_engine

import database


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    original_engine = database.engine
    original_engine.dispose()

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False}
    )
    database.engine = test_engine
    database.SessionLocal.configure(bind=test_engine)

    database.init_db()
    from sample_data.generate_sample_data import seed_complete_demo_data
    seed_complete_demo_data()

    yield

    test_engine.dispose()
    database.engine = original_engine
    database.SessionLocal.configure(bind=original_engine)