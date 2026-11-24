"""Opt-in real PostgreSQL/pgvector checks for the Day106 L3A schema.

These tests never start Docker and are skipped unless the caller explicitly
provides the Day106 integration flag and database URL.
"""

from __future__ import annotations

import os
import unittest

from rag_capstone_postgres import psycopg2_day106_connection_factory


ENABLED = os.environ.get("DAY106_L3_INTEGRATION") == "1"
DATABASE_URL = os.environ.get("DAY106_L3_DATABASE_URL", "")


@unittest.skipUnless(ENABLED and DATABASE_URL, "Day106 L3A PostgreSQL is opt-in")
class Day106L3APostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connect = staticmethod(psycopg2_day106_connection_factory(DATABASE_URL))

    def query_one(self, sql: str, params: object = None) -> object:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            connection.rollback()
            return row
        finally:
            cursor.close()
            connection.close()

    def test_exact_isolated_database_and_pgvector_version(self) -> None:
        row = self.query_one(
            "SELECT current_database(), extversion FROM pg_extension "
            "WHERE extname = 'vector'"
        )
        self.assertEqual(row, ("day106_l3", "0.8.7"))

    def test_all_three_schemas_and_day106_tables_exist(self) -> None:
        row = self.query_one(
            """
            SELECT
              to_regclass('day104_l3.index_points') IS NOT NULL,
              to_regclass('day105_l3.security_artifacts') IS NOT NULL,
              to_regclass('day106_l3.request_bindings') IS NOT NULL,
              to_regclass('day106_l3.model_invocations') IS NOT NULL,
              to_regclass('day106_l3.provider_call_attempts') IS NOT NULL,
              to_regclass('day106_l3.provider_call_receipts') IS NOT NULL,
              to_regclass('day106_l3.dispatch_winners') IS NOT NULL,
              to_regclass('day106_l3.dispatch_recovery_delivery_records') IS NOT NULL
            """
        )
        self.assertEqual(row, (True, True, True, True, True, True, True, True))

    def test_database_content_safety_rejects_raw_provider_material(self) -> None:
        safe = self.query_one(
            "SELECT day106_l3.jsonb_is_content_safe(%s::jsonb)",
            ('{"provider_response_id_digest":"sha256:abc"}',),
        )
        unsafe = self.query_one(
            "SELECT day106_l3.jsonb_is_content_safe(%s::jsonb)",
            ('{"provider_response":"raw-must-not-persist"}',),
        )
        self.assertEqual(safe, (True,))
        self.assertEqual(unsafe, (False,))

    def test_every_durable_day106_table_has_append_only_trigger(self) -> None:
        row = self.query_one(
            """
            SELECT count(*)
            FROM pg_trigger trigger
            JOIN pg_class relation ON relation.oid = trigger.tgrelid
            JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'day106_l3'
              AND relation.relname = ANY(%s)
              AND trigger.tgname LIKE '%%_append_only'
              AND NOT trigger.tgisinternal
            """,
            ([
                "request_bindings",
                "retrieval_context_receipts",
                "model_invocations",
                "provider_call_attempts",
                "provider_call_receipts",
                "answer_release_records",
                "response_intents",
                "dispatch_winners",
                "dispatch_recovery_delivery_records",
            ],),
        )
        self.assertEqual(row, (9,))


if __name__ == "__main__":
    unittest.main()
