"""Day97 PIP, PDP and signed narrow-permit boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import json
import secrets
from typing import Callable

from mcp_auth import AuthenticatedPrincipal
from rag_acl_contracts import (
    AccessEffect,
    AuthorizationPolicySnapshot,
    AuthorizationRevisionVector,
    AuthorizationStateUnavailable,
    InMemoryAuthorizationStateStore,
    PrincipalKind,
    ResourceRef,
    ResourceType,
    TenantMembership,
)
from rag_chunking_contracts import stable_hash
from rag_ingestion_contracts import DocumentIdentity
from rag_provenance import (
    CurrentRAGBinding,
    CurrentRAGProvenanceValidator,
    ProvenanceDecision,
)


class AuthorizationOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class AuthorizationRequest:
    principal: AuthenticatedPrincipal
    tenant_id: str
    resource: ResourceRef
    action: str
    audience: str
    purpose: str
    chunk_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((
            self.tenant_id,
            self.action,
            self.audience,
            self.purpose,
        )):
            raise ValueError("authorization request bindings are required")
        if self.resource.resource_type is not ResourceType.CHUNK_SET:
            raise ValueError("Day97 protected reads target one exact ChunkSet")
        if not self.chunk_ids or len(set(self.chunk_ids)) != len(self.chunk_ids):
            raise ValueError("authorization request requires unique exact chunks")


@dataclass(frozen=True)
class AuthorizationFacts:
    membership: TenantMembership
    policy: AuthorizationPolicySnapshot
    provenance: ProvenanceDecision

    @property
    def revisions(self) -> AuthorizationRevisionVector:
        return AuthorizationRevisionVector(
            policy_revision=self.policy.policy_revision,
            acl_revision=self.policy.acl_revision,
            membership_revision=self.membership.revision,
            role_version=self.policy.role_version,
            action_catalog_version=self.policy.action_catalog_version,
            authorization_epoch=self.policy.authorization_epoch,
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    outcome: AuthorizationOutcome
    decision_id: str
    internal_reason_code: str
    safe_external_message: str
    external_status: int
    request: AuthorizationRequest
    revisions: AuthorizationRevisionVector | None = None
    binding: CurrentRAGBinding | None = None

    @property
    def allowed(self) -> bool:
        return self.outcome is AuthorizationOutcome.ALLOW

    def __post_init__(self) -> None:
        complete_allow = self.revisions is not None and self.binding is not None
        if self.allowed != complete_allow:
            raise ValueError("only ALLOW carries current authorization bindings")


@dataclass(frozen=True)
class AuthorizationCacheKey:
    principal_subject: str
    tenant_id: str
    resource: ResourceRef
    action: str
    audience: str
    purpose: str
    chunk_ids: tuple[str, ...]
    revisions: AuthorizationRevisionVector
    selection_revision: int
    document_state_version: int
    document_fence: int


class BoundedAuthorizationDecisionCache:
    """Caches decision evidence, never a reusable permit or permanent truth."""

    def __init__(
        self,
        *,
        clock: Callable[[], int],
        ttl_seconds: int = 30,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("authorization cache TTL must be positive")
        self._clock = clock
        self._ttl = ttl_seconds
        self._entries: dict[
            AuthorizationCacheKey, tuple[int, AuthorizationDecision]
        ] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: AuthorizationCacheKey) -> AuthorizationDecision | None:
        entry = self._entries.get(key)
        if entry is None or entry[0] <= self._clock():
            self.misses += 1
            if entry is not None:
                self._entries.pop(key, None)
            return None
        self.hits += 1
        return entry[1]

    def put(
        self,
        key: AuthorizationCacheKey,
        decision: AuthorizationDecision,
    ) -> None:
        self._entries[key] = (self._clock() + self._ttl, decision)

    @staticmethod
    def key(
        request: AuthorizationRequest,
        facts: AuthorizationFacts,
    ) -> AuthorizationCacheKey:
        assert facts.provenance.binding is not None
        binding = facts.provenance.binding
        return AuthorizationCacheKey(
            principal_subject=request.principal.subject,
            tenant_id=request.tenant_id,
            resource=request.resource,
            action=request.action,
            audience=request.audience,
            purpose=request.purpose,
            chunk_ids=request.chunk_ids,
            revisions=facts.revisions,
            selection_revision=binding.selection_revision,
            document_state_version=binding.document_state_version,
            document_fence=binding.document_fence,
        )


class PolicyInformationPoint:
    """Load current facts; it does not make or enforce a decision."""

    def __init__(
        self,
        *,
        state_store: InMemoryAuthorizationStateStore,
        provenance_validator: CurrentRAGProvenanceValidator,
    ) -> None:
        self._state = state_store
        self._provenance = provenance_validator

    def load(self, request: AuthorizationRequest) -> AuthorizationFacts | None:
        if (
            request.tenant_id != request.resource.tenant_id
            or request.resource.document_id is None
        ):
            return None
        provenance = self._provenance.evaluate(
            document=DocumentIdentity(
                request.tenant_id,
                request.resource.document_id,
            ),
            expected_chunk_set_id=request.resource.chunk_set_id,
        )
        if not provenance.valid or provenance.binding is None:
            return None
        if (
            request.resource.document_version_id
            != provenance.binding.version.document_version_id
            or request.resource.chunk_set_id != provenance.binding.chunk_set_id
            or not set(request.chunk_ids).issubset(provenance.binding.chunk_ids)
        ):
            return None
        membership = self._state.read_membership(
            request.tenant_id,
            request.principal.subject,
        )
        policy = self._state.read_policy(
            request.tenant_id,
            request.resource.document_id,
        )
        if membership is None or policy is None:
            return None
        return AuthorizationFacts(membership, policy, provenance)


class PolicyDecisionPoint:
    """Deterministic default-deny and deny-overrides policy evaluator."""

    def __init__(self, *, clock: Callable[[], int]) -> None:
        self._clock = clock

    def evaluate(
        self,
        request: AuthorizationRequest,
        facts: AuthorizationFacts | None,
    ) -> AuthorizationDecision:
        if request.principal.expires_at is not None and (
            request.principal.expires_at <= self._clock()
        ):
            return self._deny(request, "AUTHENTICATED_PRINCIPAL_EXPIRED")
        if facts is None:
            return self._deny(request, "RESOURCE_NOT_ACCESSIBLE")
        membership = facts.membership
        policy = facts.policy
        if (
            not membership.active
            or membership.tenant_id != request.tenant_id
            or membership.principal_subject != request.principal.subject
        ):
            return self._deny(request, "TENANT_MEMBERSHIP_NOT_ACTIVE")
        if request.action not in policy.supported_actions:
            return self._deny(request, "ACTION_NOT_IN_CURRENT_CATALOG")
        if (
            request.action == "chunk:read_for_embedding"
            and membership.principal_kind is not PrincipalKind.SERVICE
        ):
            return self._deny(request, "EMBEDDING_ACTION_REQUIRES_SERVICE_PRINCIPAL")

        targets = tuple(request.resource.chunk(chunk_id) for chunk_id in request.chunk_ids)
        applicable = tuple(
            entry
            for entry in policy.entries
            if entry.principal_subject == request.principal.subject
            and entry.action == request.action
            and any(entry.resource.is_ancestor_of(target) for target in targets)
        )
        if any(entry.effect is AccessEffect.DENY for entry in applicable):
            return self._deny(request, "APPLICABLE_EXPLICIT_DENY")

        allows = tuple(
            entry for entry in applicable if entry.effect is AccessEffect.ALLOW
        )
        for target in targets:
            covering = tuple(
                entry for entry in allows if entry.resource.is_ancestor_of(target)
            )
            if not covering:
                return self._deny(request, "DEFAULT_DENY_NO_APPLICABLE_GRANT")
            only_chunk_grants = all(
                entry.resource.resource_type is ResourceType.CHUNK
                for entry in covering
            )
            if only_chunk_grants and not policy.chunk_allow_may_expand:
                return self._deny(
                    request,
                    "CHILD_ALLOW_CANNOT_EXPAND_PARENT_PERMISSION",
                )

        binding = facts.provenance.binding
        assert binding is not None
        revisions = facts.revisions
        decision_id = self._decision_id(request, revisions, binding)
        return AuthorizationDecision(
            AuthorizationOutcome.ALLOW,
            decision_id,
            "EXACT_CURRENT_AUTHORIZATION_ALLOW",
            "Authorized",
            200,
            request,
            revisions=revisions,
            binding=binding,
        )

    def unavailable(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision(
            AuthorizationOutcome.INDETERMINATE,
            stable_hash((request.principal.subject, request.action, "unavailable")),
            "AUTHORIZATION_STATE_UNAVAILABLE",
            "Service unavailable",
            503,
            request,
        )

    def _deny(
        self,
        request: AuthorizationRequest,
        reason: str,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            AuthorizationOutcome.DENY,
            stable_hash((
                request.principal.subject,
                request.tenant_id,
                request.action,
                reason,
            )),
            reason,
            "Resource not found or inaccessible",
            404,
            request,
        )

    @staticmethod
    def _decision_id(
        request: AuthorizationRequest,
        revisions: AuthorizationRevisionVector,
        binding: CurrentRAGBinding,
    ) -> str:
        return stable_hash((
            request.principal.subject,
            request.tenant_id,
            request.action,
            request.audience,
            request.purpose,
            request.chunk_ids,
            binding.chunk_set_id,
            binding.selection_revision,
            binding.document_state_version,
            binding.document_fence,
            revisions.policy_revision,
            revisions.acl_revision,
            revisions.membership_revision,
            revisions.role_version,
            revisions.action_catalog_version,
            revisions.authorization_epoch,
        ))


@dataclass(frozen=True)
class PermitClaims:
    permit_id: str
    decision_id: str
    issuer: str
    subject: str
    tenant_id: str
    audience: str
    action: str
    purpose: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    chunk_ids: tuple[str, ...]
    issued_at: int
    expires_at: int
    revisions: AuthorizationRevisionVector
    selection_revision: int
    document_state_version: int
    document_fence: int

    def payload(self) -> dict[str, object]:
        return {
            "permit_id": self.permit_id,
            "decision_id": self.decision_id,
            "issuer": self.issuer,
            "subject": self.subject,
            "tenant_id": self.tenant_id,
            "audience": self.audience,
            "action": self.action,
            "purpose": self.purpose,
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "chunk_set_id": self.chunk_set_id,
            "chunk_ids": self.chunk_ids,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revisions": {
                "policy_revision": self.revisions.policy_revision,
                "acl_revision": self.revisions.acl_revision,
                "membership_revision": self.revisions.membership_revision,
                "role_version": self.revisions.role_version,
                "action_catalog_version": self.revisions.action_catalog_version,
                "authorization_epoch": self.revisions.authorization_epoch,
            },
            "selection_revision": self.selection_revision,
            "document_state_version": self.document_state_version,
            "document_fence": self.document_fence,
        }


@dataclass(frozen=True)
class SignedPermit:
    claims: PermitClaims
    signature: str


class PermitIssuer:
    """Trusted HMAC classroom issuer with injected key and clock.

    HMAC demonstrates signed binding and tamper rejection.  It is not evidence
    of production key custody, asymmetric verification, or key rotation.
    """

    def __init__(
        self,
        *,
        issuer: str,
        signing_key: bytes,
        clock: Callable[[], int],
        ttl_seconds: int = 60,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        if not issuer or len(signing_key) < 16 or ttl_seconds <= 0:
            raise ValueError("permit issuer configuration is invalid")
        self._issuer = issuer
        self._key = signing_key
        self._clock = clock
        self._ttl = ttl_seconds
        self._nonce = nonce_factory or (lambda: secrets.token_hex(16))

    def issue(self, decision: AuthorizationDecision) -> SignedPermit:
        if not decision.allowed:
            raise ValueError("PermitIssuer may only consume ALLOW decisions")
        assert decision.revisions is not None and decision.binding is not None
        request = decision.request
        now = self._clock()
        permit_id = stable_hash((decision.decision_id, now, self._nonce()))
        claims = PermitClaims(
            permit_id=permit_id,
            decision_id=decision.decision_id,
            issuer=self._issuer,
            subject=request.principal.subject,
            tenant_id=request.tenant_id,
            audience=request.audience,
            action=request.action,
            purpose=request.purpose,
            document_id=decision.binding.version.document_id,
            document_version_id=decision.binding.version.document_version_id,
            chunk_set_id=decision.binding.chunk_set_id,
            chunk_ids=request.chunk_ids,
            issued_at=now,
            expires_at=now + self._ttl,
            revisions=decision.revisions,
            selection_revision=decision.binding.selection_revision,
            document_state_version=decision.binding.document_state_version,
            document_fence=decision.binding.document_fence,
        )
        return SignedPermit(claims, self._sign(claims))

    def verify_signature(self, permit: SignedPermit) -> bool:
        return (
            permit.claims.issuer == self._issuer
            and hmac.compare_digest(
                permit.signature,
                self._sign(permit.claims),
            )
        )

    def _sign(self, claims: PermitClaims) -> str:
        encoded = json.dumps(
            claims.payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._key, encoded, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class AuthorizationResult:
    decision: AuthorizationDecision
    permit: SignedPermit | None = None

    def __post_init__(self) -> None:
        if self.decision.allowed != (self.permit is not None):
            raise ValueError("only an allowed result carries a permit")


class RAGAuthorizationService:
    """Compose PIP, PDP and issuer without moving enforcement into the PDP."""

    def __init__(
        self,
        *,
        pip: PolicyInformationPoint,
        pdp: PolicyDecisionPoint,
        issuer: PermitIssuer,
        cache: BoundedAuthorizationDecisionCache | None = None,
    ) -> None:
        self._pip = pip
        self._pdp = pdp
        self._issuer = issuer
        self._cache = cache

    def authorize(self, request: AuthorizationRequest) -> AuthorizationResult:
        try:
            facts = self._pip.load(request)
        except AuthorizationStateUnavailable:
            return AuthorizationResult(self._pdp.unavailable(request))
        cache_key = None
        decision = None
        if facts is not None and self._cache is not None:
            cache_key = self._cache.key(request, facts)
            decision = self._cache.get(cache_key)
        if decision is None:
            decision = self._pdp.evaluate(request, facts)
            if cache_key is not None and self._cache is not None:
                self._cache.put(cache_key, decision)
        permit = self._issuer.issue(decision) if decision.allowed else None
        return AuthorizationResult(decision, permit)
