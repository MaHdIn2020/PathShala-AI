import os
import unittest
from unittest.mock import patch

from pathshala.config import Config, get_config
from pathshala.db import all_shard_urls, merge_shard_books, resolve_db_url


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


if __name__ == "__main__":
    unittest.main()
