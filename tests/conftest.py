import os
from pathlib import Path

import psycopg
from psycopg import sql
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

# Tests use a separate database, never the player's database.
root = Path(__file__).resolve().parents[1]
url = make_url(os.environ.get('DATABASE_URL') or dotenv_values(root / '.env')['DATABASE_URL'])
test_name = url.database + '_test'
if not test_name.endswith('_test'):
    raise RuntimeError('Unsafe test database name')
with psycopg.connect(host=url.host, port=url.port, user=url.username, password=url.password, dbname='postgres', autocommit=True) as db:
    if not db.execute('SELECT 1 FROM pg_database WHERE datname=%s', (test_name,)).fetchone():
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(test_name)))
os.environ['DATABASE_URL'] = url.set(database=test_name).render_as_string(hide_password=False)

from backend.app.database import Base, engine
from backend.app.main import app
from backend.app.seed import seed
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def clean_database():
    assert engine.url.database.endswith('_test')
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    yield

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def player(client):
    response = client.post('/api/auth/register', json={'username':'tester', 'password':'testpassword123', 'name':'Искатель'})
    assert response.status_code == 201
    return client
