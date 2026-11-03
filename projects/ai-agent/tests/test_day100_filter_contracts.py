from __future__ import annotations

import unittest

from examples.day100_hybrid_retrieval_filtering import (
    build_day100_fixture,
    classroom_filter_schema,
)
from rag_retrieval_filters import (
    FilterExpression,
    FilterOperator,
    FilterPlanMode,
    FilterPlanner,
    ProviderFilterCapabilities,
    UnsupportedFilter,
    authorized_and_business_match,
    matches_filter,
)


class Day100FilterContractTests(unittest.TestCase):
    def _planner(
        self,
        *,
        operators: frozenset[FilterOperator],
        split: bool,
        post: bool,
    ) -> FilterPlanner:
        return FilterPlanner(
            schema=classroom_filter_schema(),
            capabilities=ProviderFilterCapabilities("test-capabilities", operators),
            allow_split_or=split,
            allow_business_post_filter=post,
        )

    def test_unsupported_or_is_split_without_dropping_semantics(self) -> None:
        fixture = build_day100_fixture()
        expression = FilterExpression.or_(
            FilterExpression.eq("category", "finance"),
            FilterExpression.eq("owner_id", "principal-day100"),
        )
        plan = self._planner(
            operators=frozenset({FilterOperator.EQ}),
            split=True,
            post=False,
        ).plan(scope=fixture.scope, client_filter=expression)
        self.assertEqual(plan.mode, FilterPlanMode.SPLIT_OR)
        self.assertEqual(len(plan.provider_queries), 2)

    def test_unsupported_filter_fails_closed_when_no_fallback(self) -> None:
        fixture = build_day100_fixture()
        expression = FilterExpression.not_(
            FilterExpression.eq("status", "deleted")
        )
        with self.assertRaises(UnsupportedFilter):
            self._planner(
                operators=frozenset({FilterOperator.EQ}),
                split=False,
                post=False,
            ).plan(scope=fixture.scope, client_filter=expression)

    def test_application_post_filter_is_explicit(self) -> None:
        fixture = build_day100_fixture()
        expression = FilterExpression.not_(
            FilterExpression.eq("status", "deleted")
        )
        plan = self._planner(
            operators=frozenset({FilterOperator.EQ}),
            split=False,
            post=True,
        ).plan(scope=fixture.scope, client_filter=expression)
        self.assertEqual(
            plan.mode,
            FilterPlanMode.AUTHORIZATION_PREFILTER_APPLICATION_POSTFILTER,
        )
        self.assertEqual(plan.provider_queries, (None,))
        self.assertEqual(plan.application_post_filter, expression)

    def test_tenant_field_is_not_client_filterable(self) -> None:
        fixture = build_day100_fixture()
        with self.assertRaises(UnsupportedFilter):
            self._planner(
                operators=frozenset({FilterOperator.EQ}),
                split=False,
                post=False,
            ).plan(
                scope=fixture.scope,
                client_filter=FilterExpression.eq("tenant_id", "tenant-other"),
            )

    def test_filter_value_type_is_validated(self) -> None:
        fixture = build_day100_fixture()
        with self.assertRaises(UnsupportedFilter):
            self._planner(
                operators=frozenset({FilterOperator.EQ}),
                split=False,
                post=False,
            ).plan(
                scope=fixture.scope,
                client_filter=FilterExpression.eq("category", 42),
            )

    def test_nested_filter_evaluation_is_deterministic(self) -> None:
        expression = FilterExpression.and_(
            FilterExpression.eq("category", "finance"),
            FilterExpression.not_(FilterExpression.eq("status", "deleted")),
        )
        self.assertTrue(matches_filter(expression, {
            "category": "finance", "status": "active"
        }))
        self.assertFalse(matches_filter(expression, {
            "category": "finance", "status": "deleted"
        }))

    def test_business_filter_cannot_expand_authorization(self) -> None:
        fixture = build_day100_fixture()
        record = fixture.records[3]
        self.assertEqual(record.identity.occurrence_id, "occurrence:X")
        self.assertFalse(authorized_and_business_match(
            scope=fixture.scope,
            occurrence_id=record.identity.occurrence_id,
            metadata=record.metadata_dict,
            business_filter=FilterExpression.eq("category", "finance"),
        ))

    def test_filter_plan_binds_authorization_revision(self) -> None:
        fixture = build_day100_fixture()
        planner = self._planner(
            operators=frozenset({FilterOperator.EQ}),
            split=False,
            post=False,
        )
        expression = FilterExpression.eq("category", "finance")
        before = planner.plan(scope=fixture.scope, client_filter=expression)
        changed = fixture.authorization.revoke_occurrence(
            tenant_id=fixture.scope.tenant_id,
            principal_subject=fixture.scope.principal_subject,
            action=fixture.scope.action,
            purpose=fixture.scope.purpose,
            occurrence_id="occurrence:B",
        )
        after = planner.plan(scope=changed, client_filter=expression)
        self.assertNotEqual(before.fingerprint, after.fingerprint)


if __name__ == "__main__":
    unittest.main()
