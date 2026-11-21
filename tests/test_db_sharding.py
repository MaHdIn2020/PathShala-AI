import os
import unittest
from unittest.mock import patch

from pathshala.config import Config, get_config
from pathshala.db import (
    all_shard_urls,
    clear_catalog_cache,
    get_curriculum_catalog,
    merge_shard_books,
    resolve_db_url,
)


def _make_cfg(primary="postgresql://p/main", bn_ssc="postgresql://p/bn_ssc", en="postgresql://p/en"):
    return Config(
        database_url=primary,
        database_url_bn_ssc=bn_ssc,
        database_url_en=en,
        llm_model="gemini/gemini-3-flash-preview",
        llm_fast_model="gemini/gemini-3.5-flash-lite",
        llm_verify_model="gemini/gemini-3.1-flash-lite",
        embed_provider="local",
        embed_model="BAAI/bge-m3",
        embed_dim=1024,
        retrieve_k=30,
        rerank_k=5,
        min_score=0.45,
        verify=True,
        rewrite=True,
        cache=True,
        rerank=False,
        max_question_chars=600,
        max_context_chars=3600,
    )


class DbShardingTest(unittest.TestCase):
    def test_resolve_db_url_routes_all_three_shards(self):
        cfg = _make_cfg()
        for cls in range(1, 9):
            self.assertEqual(resolve_db_url("bangla_version", cls, cfg), "postgresql://p/main")
        for cls in (9, 10):
            self.assertEqual(resolve_db_url("bangla_version", cls, cfg), "postgresql://p/bn_ssc")
        for cls in range(1, 11):
            self.assertEqual(resolve_db_url("english_version", cls, cfg), "postgresql://p/en")
        self.assertEqual(all_shard_urls(cfg), ["postgresql://p/main", "postgresql://p/bn_ssc", "postgresql://p/en"])

    def test_single_db_fallback_when_shard_env_vars_unset(self):
        env_patch = {
            "DATABASE_URL": "postgresql://only/primary",
            "DATABASE_URL_BN_SSC": "",
            "DATABASE_URL_EN": "",
        }
        with patch.dict(os.environ, env_patch, clear=False):
            cfg = get_config()
            self.assertEqual(cfg.database_url_bn_ssc, "postgresql://only/primary")
            self.assertEqual(cfg.database_url_en, "postgresql://only/primary")
            self.assertEqual(all_shard_urls(cfg), ["postgresql://only/primary"])
            self.assertEqual(resolve_db_url("bangla_version", 9, cfg), "postgresql://only/primary")
            self.assertEqual(resolve_db_url("english_version", 8, cfg), "postgresql://only/primary")

    def test_merge_shard_books_prefers_authoritative_shard_and_sorts(self):
        cfg = _make_cfg()
        primary_rows = [
            {"curriculum_id": "nctb", "textbook_medium": "bangla_version", "class_level": 5, "subject": "science", "chunk_count": 300},
            {"curriculum_id": "nctb", "textbook_medium": "english_version", "class_level": 8, "subject": "science", "chunk_count": 10},
        ]
        bn_ssc_rows = [
            {"curriculum_id": "nctb", "textbook_medium": "bangla_version", "class_level": 9, "subject": "physics_secondary", "chunk_count": 900},
        ]
        en_rows = [
            {"curriculum_id": "nctb", "textbook_medium": "english_version", "class_level": 8, "subject": "science", "chunk_count": 824},
        ]
        merged = merge_shard_books(
            [
                ("postgresql://p/main", primary_rows),
                ("postgresql://p/bn_ssc", bn_ssc_rows),
                ("postgresql://p/en", en_rows),
            ],
            cfg=cfg,
        )
        self.assertEqual(len(merged), 3)
        en_sci = [b for b in merged if b["textbook_medium"] == "english_version"][0]
        self.assertEqual(en_sci["chunk_count"], 824)
        self.assertEqual(
            [(b["textbook_medium"], b["class_level"]) for b in merged],
            [("bangla_version", 5), ("bangla_version", 9), ("english_version", 8)],
        )

    def test_get_curriculum_catalog_parallel_fetch_and_cache(self):
        clear_catalog_cache()
        cfg = _make_cfg()
        calls: list[str] = []

        class FakeCursor:
            def __init__(self, url: str):
                self.url = url

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, _sql: str):
                return None

            def fetchall(self) -> list[dict]:
                if self.url.endswith("/main"):
                    return [
                        {
                            "id": 1,
                            "curriculum_id": "nctb",
                            "textbook_medium": "bangla_version",
                            "class_level": 5,
                            "subject": "science",
                            "title": "NCTB শ্রেণি 5 · science",
                            "chunk_count": 120,
                            "embedded_count": 120,
                        }
                    ]
                if self.url.endswith("/bn_ssc"):
                    return [
                        {
                            "id": 2,
                            "curriculum_id": "nctb",
                            "textbook_medium": "bangla_version",
                            "class_level": 9,
                            "subject": "physics_secondary",
                            "title": "NCTB শ্রেণি 9 · physics_secondary",
                            "chunk_count": 500,
                            "embedded_count": 500,
                        }
                    ]
                return [
                    {
                        "id": 3,
                        "curriculum_id": "nctb",
                        "textbook_medium": "english_version",
                        "class_level": 8,
                        "subject": "science",
                        "title": "NCTB Class 8 · science",
                        "chunk_count": 824,
                        "embedded_count": 824,
                    }
                ]

        class FakeConn:
            def __init__(self, url: str):
                self.url = url

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                return FakeCursor(self.url)

        def fake_get_conn(_cfg=None, *, textbook_medium=None, class_level=None, db_url=None):
            calls.append(db_url)
            return FakeConn(db_url)

        try:
            with patch("pathshala.db.get_conn", side_effect=fake_get_conn):
                first = get_curriculum_catalog(cfg)
                second = get_curriculum_catalog(cfg)
                self.assertEqual(len(first), 3)
                self.assertEqual(len(second), 3)
                self.assertEqual(len(calls), 3)

                clear_catalog_cache()
                third = get_curriculum_catalog(cfg)
                self.assertEqual(len(third), 3)
                self.assertEqual(len(calls), 6)
        finally:
            clear_catalog_cache()


if __name__ == "__main__":
    unittest.main()
