from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.db.repositories.chunk import ChunkRepository, ParadeDBUnavailableError, _build_paradedb_bm25_sql


def test_paradedb_bm25_sql_uses_pg_search_score_and_snippet():
    statement = str(_build_paradedb_bm25_sql(has_knowledge_ids=True))

    assert "search_text ||| :query" in statement
    assert "pdb.score(id)" in statement
    assert "pdb.snippet(search_text)" in statement
    assert "chunk_type = 'child'" in statement
    assert "knowledge_id IN" in statement
    assert "to_tsvector" not in statement


def test_postgres_keyword_search_raises_chinese_error_when_paradedb_is_missing():
    class BrokenPostgresSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, *_args, **_kwargs):
            raise SQLAlchemyError("operator does not exist: text ||| unknown")

    repo = ChunkRepository(BrokenPostgresSession())

    with pytest.raises(ParadeDBUnavailableError) as exc:
        repo.keyword_search(
            knowledge_base_id="kb-1",
            query="混合检索",
            terms=["混合", "检索"],
            limit=5,
        )

    assert "ParadeDB BM25 未就绪" in str(exc.value)


def test_v09_paradedb_migration_creates_pg_search_bm25_index():
    migration = Path("alembic/versions/0017_v09_paradedb_bm25.py").read_text(encoding="utf-8")
    upgrade_body = migration.split("def downgrade", 1)[0]

    assert "CREATE EXTENSION IF NOT EXISTS pg_search" in upgrade_body
    assert "USING bm25" in upgrade_body
    assert "WITH (key_field='id')" in upgrade_body
    assert "ix_chunks_paradedb_bm25" in upgrade_body
    assert "to_tsvector" not in upgrade_body
