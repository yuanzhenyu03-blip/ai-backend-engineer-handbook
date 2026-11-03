"""Day100 application-owned business-filter grammar and execution plans."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping

from rag_chunking_contracts import stable_hash
from rag_retrieval_contracts import RetrievalAuthorizationScope


class FilterOperator(str, Enum):
    EQ = "EQ"
    IN = "IN"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass(frozen=True)
class FilterExpression:
    operator: FilterOperator
    field: str | None = None
    value: object | None = None
    children: tuple["FilterExpression", ...] = ()

    def __post_init__(self) -> None:
        leaf = self.operator in {FilterOperator.EQ, FilterOperator.IN}
        if leaf:
            if not self.field or self.value is None or self.children:
                raise ValueError("leaf filters require field and value only")
            if self.operator is FilterOperator.IN and (
                not isinstance(self.value, tuple) or not self.value
            ):
                raise ValueError("IN requires a non-empty immutable tuple")
            return
        if self.field is not None or self.value is not None:
            raise ValueError("logical filters cannot carry field/value")
        if self.operator is FilterOperator.NOT:
            if len(self.children) != 1:
                raise ValueError("NOT requires exactly one child")
        elif len(self.children) < 2:
            raise ValueError("AND/OR require at least two children")

    @classmethod
    def eq(cls, field: str, value: object) -> "FilterExpression":
        return cls(FilterOperator.EQ, field=field, value=value)

    @classmethod
    def in_(cls, field: str, values: tuple[object, ...]) -> "FilterExpression":
        return cls(FilterOperator.IN, field=field, value=values)

    @classmethod
    def and_(cls, *children: "FilterExpression") -> "FilterExpression":
        return cls(FilterOperator.AND, children=tuple(children))

    @classmethod
    def or_(cls, *children: "FilterExpression") -> "FilterExpression":
        return cls(FilterOperator.OR, children=tuple(children))

    @classmethod
    def not_(cls, child: "FilterExpression") -> "FilterExpression":
        return cls(FilterOperator.NOT, children=(child,))

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class FilterField:
    name: str
    value_type: type
    client_filterable: bool = True


@dataclass(frozen=True)
class FilterSchema:
    schema_version: str
    fields: tuple[FilterField, ...]
    max_depth: int
    max_nodes: int

    def __post_init__(self) -> None:
        if not self.schema_version or not self.fields:
            raise ValueError("filter schema identity and fields are required")
        if self.max_depth <= 0 or self.max_nodes <= 0:
            raise ValueError("filter complexity bounds must be positive")
        names = tuple(field.name for field in self.fields)
        if len(set(names)) != len(names):
            raise ValueError("filter schema fields must be unique")

    @property
    def fingerprint(self) -> str:
        serializable = {
            "schema_version": self.schema_version,
            "fields": tuple((item.name, item.value_type.__name__, item.client_filterable)
                            for item in self.fields),
            "max_depth": self.max_depth,
            "max_nodes": self.max_nodes,
        }
        return stable_hash(serializable)


@dataclass(frozen=True)
class ProviderFilterCapabilities:
    capability_version: str
    supported_operators: frozenset[FilterOperator]

    def __post_init__(self) -> None:
        if not self.capability_version or not self.supported_operators:
            raise ValueError("provider filter capabilities are required")


class FilterPlanMode(str, Enum):
    DIRECT = "DIRECT"
    SPLIT_OR = "SPLIT_OR"
    AUTHORIZATION_PREFILTER_APPLICATION_POSTFILTER = (
        "AUTHORIZATION_PREFILTER_APPLICATION_POSTFILTER"
    )


@dataclass(frozen=True)
class FilterPlan:
    mode: FilterPlanMode
    authorization_scope_fingerprint: str
    schema_fingerprint: str
    provider_capability_version: str
    client_filter_fingerprint: str | None
    provider_queries: tuple[FilterExpression | None, ...]
    application_post_filter: FilterExpression | None
    system_excluded_occurrence_ids: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return stable_hash({
            "mode": self.mode.value,
            "authorization_scope_fingerprint": self.authorization_scope_fingerprint,
            "schema_fingerprint": self.schema_fingerprint,
            "provider_capability_version": self.provider_capability_version,
            "client_filter_fingerprint": self.client_filter_fingerprint,
            "provider_queries": tuple(
                item.fingerprint if item is not None else None
                for item in self.provider_queries
            ),
            "application_post_filter": (
                self.application_post_filter.fingerprint
                if self.application_post_filter is not None else None
            ),
            "system_excluded_occurrence_ids": self.system_excluded_occurrence_ids,
        })


class UnsupportedFilter(ValueError):
    """The application cannot preserve the requested filter semantics."""


class FilterPlanner:
    def __init__(
        self,
        *,
        schema: FilterSchema,
        capabilities: ProviderFilterCapabilities,
        allow_split_or: bool,
        allow_business_post_filter: bool,
    ) -> None:
        self._schema = schema
        self._capabilities = capabilities
        self._allow_split_or = allow_split_or
        self._allow_post = allow_business_post_filter

    def plan(
        self,
        *,
        scope: RetrievalAuthorizationScope,
        client_filter: FilterExpression | None,
        system_excluded_occurrence_ids: tuple[str, ...] = (),
    ) -> FilterPlan:
        if client_filter is None:
            return FilterPlan(
                FilterPlanMode.DIRECT,
                scope.fingerprint,
                self._schema.fingerprint,
                self._capabilities.capability_version,
                None,
                (None,),
                None,
                system_excluded_occurrence_ids,
            )
        self._validate(client_filter)
        operators = self._operators(client_filter)
        if operators.issubset(self._capabilities.supported_operators):
            return FilterPlan(
                FilterPlanMode.DIRECT,
                scope.fingerprint,
                self._schema.fingerprint,
                self._capabilities.capability_version,
                client_filter.fingerprint,
                (client_filter,),
                None,
                system_excluded_occurrence_ids,
            )
        if (
            self._allow_split_or
            and client_filter.operator is FilterOperator.OR
            and all(
                self._operators(child).issubset(
                    self._capabilities.supported_operators
                )
                for child in client_filter.children
            )
        ):
            return FilterPlan(
                FilterPlanMode.SPLIT_OR,
                scope.fingerprint,
                self._schema.fingerprint,
                self._capabilities.capability_version,
                client_filter.fingerprint,
                client_filter.children,
                None,
                system_excluded_occurrence_ids,
            )
        if self._allow_post:
            return FilterPlan(
                FilterPlanMode.AUTHORIZATION_PREFILTER_APPLICATION_POSTFILTER,
                scope.fingerprint,
                self._schema.fingerprint,
                self._capabilities.capability_version,
                client_filter.fingerprint,
                (None,),
                client_filter,
                system_excluded_occurrence_ids,
            )
        unsupported = sorted(operator.value for operator in (
            operators - self._capabilities.supported_operators
        ))
        raise UnsupportedFilter(
            "UNSUPPORTED_FILTER_OPERATORS:" + ",".join(unsupported)
        )

    def _validate(self, expression: FilterExpression) -> None:
        fields = {item.name: item for item in self._schema.fields}
        count = 0

        def walk(node: FilterExpression, depth: int) -> None:
            nonlocal count
            count += 1
            if depth > self._schema.max_depth or count > self._schema.max_nodes:
                raise UnsupportedFilter("FILTER_COMPLEXITY_LIMIT_EXCEEDED")
            if node.field is not None:
                definition = fields.get(node.field)
                if definition is None or not definition.client_filterable:
                    raise UnsupportedFilter("FILTER_FIELD_NOT_ALLOWED:" + node.field)
                values = node.value if isinstance(node.value, tuple) else (node.value,)
                if any(not isinstance(value, definition.value_type) for value in values):
                    raise UnsupportedFilter("FILTER_VALUE_TYPE_MISMATCH:" + node.field)
            for child in node.children:
                walk(child, depth + 1)

        walk(expression, 1)

    @staticmethod
    def _operators(expression: FilterExpression) -> frozenset[FilterOperator]:
        values = {expression.operator}
        for child in expression.children:
            values.update(FilterPlanner._operators(child))
        return frozenset(values)


def matches_filter(
    expression: FilterExpression | None,
    metadata: Mapping[str, object],
) -> bool:
    if expression is None:
        return True
    if expression.operator is FilterOperator.EQ:
        return metadata.get(expression.field or "") == expression.value
    if expression.operator is FilterOperator.IN:
        return metadata.get(expression.field or "") in expression.value  # type: ignore[operator]
    if expression.operator is FilterOperator.AND:
        return all(matches_filter(child, metadata) for child in expression.children)
    if expression.operator is FilterOperator.OR:
        return any(matches_filter(child, metadata) for child in expression.children)
    return not matches_filter(expression.children[0], metadata)


def authorized_and_business_match(
    *,
    scope: RetrievalAuthorizationScope,
    occurrence_id: str,
    metadata: Mapping[str, object],
    business_filter: FilterExpression | None,
    system_excluded_occurrence_ids: tuple[str, ...] = (),
) -> bool:
    """Authorization is always enforced independently from business filters."""

    return (
        occurrence_id in scope.allowed_occurrence_ids
        and occurrence_id not in system_excluded_occurrence_ids
        and metadata.get("tenant_id") == scope.tenant_id
        and matches_filter(business_filter, metadata)
    )
