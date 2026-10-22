"""Application-owned Day97 tenant, resource, membership and ACL contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading


class PrincipalKind(str, Enum):
    HUMAN = "HUMAN"
    SERVICE = "SERVICE"


class ResourceType(str, Enum):
    TENANT = "TENANT"
    DOCUMENT = "DOCUMENT"
    DOCUMENT_VERSION = "DOCUMENT_VERSION"
    CHUNK_SET = "CHUNK_SET"
    CHUNK = "CHUNK"


class AccessEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class ResourceRef:
    resource_type: ResourceType
    tenant_id: str
    document_id: str | None = None
    document_version_id: str | None = None
    chunk_set_id: str | None = None
    chunk_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("resource requires tenant identity")
        required_depth = {
            ResourceType.TENANT: 0,
            ResourceType.DOCUMENT: 1,
            ResourceType.DOCUMENT_VERSION: 2,
            ResourceType.CHUNK_SET: 3,
            ResourceType.CHUNK: 4,
        }[self.resource_type]
        values = (
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            self.chunk_id,
        )
        if any(values[index] is None for index in range(required_depth)):
            raise ValueError("resource hierarchy binding is incomplete")
        if any(values[index] is not None for index in range(required_depth, 4)):
            raise ValueError("resource carries fields below its hierarchy level")

    @property
    def depth(self) -> int:
        return {
            ResourceType.TENANT: 0,
            ResourceType.DOCUMENT: 1,
            ResourceType.DOCUMENT_VERSION: 2,
            ResourceType.CHUNK_SET: 3,
            ResourceType.CHUNK: 4,
        }[self.resource_type]

    def is_ancestor_of(self, other: "ResourceRef") -> bool:
        if self.depth > other.depth:
            return False
        own = (
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            self.chunk_id,
        )
        candidate = (
            other.tenant_id,
            other.document_id,
            other.document_version_id,
            other.chunk_set_id,
            other.chunk_id,
        )
        return own[: self.depth + 1] == candidate[: self.depth + 1]

    @classmethod
    def document(cls, tenant_id: str, document_id: str) -> "ResourceRef":
        return cls(ResourceType.DOCUMENT, tenant_id, document_id)

    @classmethod
    def chunk_set(
        cls,
        tenant_id: str,
        document_id: str,
        document_version_id: str,
        chunk_set_id: str,
    ) -> "ResourceRef":
        return cls(
            ResourceType.CHUNK_SET,
            tenant_id,
            document_id,
            document_version_id,
            chunk_set_id,
        )

    def chunk(self, chunk_id: str) -> "ResourceRef":
        if self.resource_type is not ResourceType.CHUNK_SET:
            raise ValueError("a chunk resource requires a ChunkSet parent")
        return ResourceRef(
            ResourceType.CHUNK,
            self.tenant_id,
            self.document_id,
            self.document_version_id,
            self.chunk_set_id,
            chunk_id,
        )


@dataclass(frozen=True)
class TenantMembership:
    tenant_id: str
    principal_subject: str
    principal_kind: PrincipalKind
    active: bool
    revision: int

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.principal_subject or self.revision <= 0:
            raise ValueError("membership identity and revision are required")


@dataclass(frozen=True)
class ACLEntry:
    entry_id: str
    principal_subject: str
    resource: ResourceRef
    action: str
    effect: AccessEffect

    def __post_init__(self) -> None:
        if not self.entry_id or not self.principal_subject or not self.action:
            raise ValueError("ACL entry bindings are required")


@dataclass(frozen=True)
class AuthorizationRevisionVector:
    policy_revision: int
    acl_revision: int
    membership_revision: int
    role_version: str
    action_catalog_version: str
    authorization_epoch: int

    def __post_init__(self) -> None:
        if min(
            self.policy_revision,
            self.acl_revision,
            self.membership_revision,
            self.authorization_epoch,
        ) <= 0:
            raise ValueError("authorization revisions and epoch must be positive")
        if not self.role_version or not self.action_catalog_version:
            raise ValueError("role and action catalog versions are required")


@dataclass(frozen=True)
class AuthorizationPolicySnapshot:
    tenant_id: str
    document_id: str
    policy_revision: int
    acl_revision: int
    role_version: str
    action_catalog_version: str
    authorization_epoch: int
    supported_actions: frozenset[str]
    entries: tuple[ACLEntry, ...]
    chunk_allow_may_expand: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.document_id:
            raise ValueError("policy resource identity is required")
        if min(
            self.policy_revision,
            self.acl_revision,
            self.authorization_epoch,
        ) <= 0:
            raise ValueError("policy revisions and epoch must be positive")
        if not self.role_version or not self.action_catalog_version:
            raise ValueError("policy definition versions are required")
        if not self.supported_actions:
            raise ValueError("policy requires an explicit action catalog")
        if any(
            entry.resource.tenant_id != self.tenant_id
            or entry.resource.document_id not in (None, self.document_id)
            for entry in self.entries
        ):
            raise ValueError("ACL entries must bind the policy tenant/document")


class AuthorizationStateUnavailable(RuntimeError):
    """Current policy or membership facts could not be read."""


class InMemoryAuthorizationStateStore:
    """Deterministic current-state model; not production policy durability."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._memberships: dict[tuple[str, str], TenantMembership] = {}
        self._policies: dict[
            tuple[str, str], AuthorizationPolicySnapshot
        ] = {}
        self._available = True

    def set_available(self, available: bool) -> None:
        with self._lock:
            self._available = available

    def put_membership(self, membership: TenantMembership) -> None:
        with self._lock:
            self._memberships[
                (membership.tenant_id, membership.principal_subject)
            ] = membership

    def put_policy(self, policy: AuthorizationPolicySnapshot) -> None:
        with self._lock:
            self._policies[(policy.tenant_id, policy.document_id)] = policy

    def read_membership(
        self,
        tenant_id: str,
        principal_subject: str,
    ) -> TenantMembership | None:
        with self._lock:
            self._require_available()
            return self._memberships.get((tenant_id, principal_subject))

    def read_policy(
        self,
        tenant_id: str,
        document_id: str,
    ) -> AuthorizationPolicySnapshot | None:
        with self._lock:
            self._require_available()
            return self._policies.get((tenant_id, document_id))

    def revoke_grant(
        self,
        *,
        tenant_id: str,
        document_id: str,
        entry_id: str,
    ) -> AuthorizationPolicySnapshot:
        """Remove one grant and advance ACL revision plus resource epoch."""

        with self._lock:
            self._require_available()
            current = self._policies[(tenant_id, document_id)]
            remaining = tuple(
                entry for entry in current.entries if entry.entry_id != entry_id
            )
            if len(remaining) == len(current.entries):
                return current
            updated = replace(
                current,
                entries=remaining,
                acl_revision=current.acl_revision + 1,
                authorization_epoch=current.authorization_epoch + 1,
            )
            self._policies[(tenant_id, document_id)] = updated
            return updated

    def advance_authorization_epoch(
        self,
        *,
        tenant_id: str,
        document_id: str,
    ) -> AuthorizationPolicySnapshot:
        with self._lock:
            self._require_available()
            current = self._policies[(tenant_id, document_id)]
            updated = replace(
                current,
                authorization_epoch=current.authorization_epoch + 1,
            )
            self._policies[(tenant_id, document_id)] = updated
            return updated

    def replace_membership(
        self,
        membership: TenantMembership,
        *,
        active: bool,
    ) -> TenantMembership:
        updated = replace(
            membership,
            active=active,
            revision=membership.revision + 1,
        )
        self.put_membership(updated)
        return updated

    def _require_available(self) -> None:
        if not self._available:
            raise AuthorizationStateUnavailable(
                "authorization state is unavailable"
            )
