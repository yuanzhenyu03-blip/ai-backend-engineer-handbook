"""Day73 — the application-owned Prompt Contract, immutable Attempt binding, and the pre-Provider LLM
Runtime gate (standard library only).

Day72 made the Provider replaceable: an already-admitted internal request is translated to a
provider-specific call behind a stable ``ProviderAdapter``. Day73 answers an EARLIER question, before any
adapter or Provider capability admission runs:

    Which exact prompt behaviour was authorized for THIS Attempt, can the Runtime reproduce it
    deterministically, and is it compatible — before any adapter or Provider call?

A Prompt Contract is an APPLICATION-OWNED, versioned execution contract — not a mutable string and not a
Provider Adapter capability declaration. A published revision is immutable; operational status lives in a
separate lifecycle overlay. Every Attempt durably binds the prompt contract id + revision, the renderer
version, the model-parameter-policy id + revision, the application contract, a canonical input fingerprint,
and the rendered-message hash (plus, only when policy permits, a protected rendered-artifact reference). The
current default revision governs ONLY new planning; it must never reinterpret an already-planned or
dispatched Attempt.

Responsibility boundaries kept distinct here:

* Application business authorization (tenant/user/entitlement/quota) — NOT modelled as prompt variables and
  never derived from them (a prompt variable is never authorization evidence).
* LLM Runtime — prompt selection, immutable binding, lifecycle enforcement, variable/schema validation,
  compatibility checks, deterministic rendering, binding verification, guarded state transitions,
  reconciliation decisions. This module.
* Model Parameter Policy — temperature/token limits etc.; versioned and bound INDEPENDENTLY, not hidden
  inside the Prompt Contract. Modelled here only as an id + revision that the binding records.
* Provider Adapter (Day72) — provider-specific translation and error normalization; it must NOT choose or
  rewrite the prompt revision.
* Output/business validation — decides whether a transport ``SUCCESS`` is a trusted business result; a
  Provider ``SUCCESS`` is only an untrusted candidate.

There is NO network, NO real Provider, NO SDK, and NO database here. The in-memory Attempt prompt store
MODELS a compare-and-set boundary for in-process determinism only; it is NOT a durable database. The
``provider_calls`` counter models crossing the in-process gate toward the Provider boundary; it is NOT proof
of a real Provider/SDK/HTTP/network/DB call.
"""

from __future__ import annotations

import hashlib
import json
import string
import threading
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Message roles + prompt lifecycle status (fail-closed, like Day72's ProfileStatus).
# ---------------------------------------------------------------------------
class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class PromptStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    QUARANTINED = "QUARANTINED"
    UNKNOWN = "UNKNOWN"          # not registered with the lifecycle authority -> callers MUST fail closed


class VariableType(str, Enum):
    STR = "str"
    INT = "int"
    BOOL = "bool"
    ENUM = "enum"


# ---------------------------------------------------------------------------
# 2. Application-invariant errors (NOT Provider failures, NOT model output problems).
# ---------------------------------------------------------------------------
class PromptVariableError(Exception):
    """Input variables violate the revision's input schema (missing required, unknown, wrong type/value, or a
    fail-closed unknown policy value). An application-invariant violation before any Provider call."""


class PromptBindingError(Exception):
    """The dispatch inputs do not match the Attempt's AUTHORITATIVE persisted prompt binding, or a caller
    supplied a binding that differs from the stored one. Never a Provider failure; zero Provider calls."""


class AliasConflictError(Exception):
    """A migration alias and its replacement are BOTH present with conflicting values. The migration/
    validation path must reject rather than silently pick a winner."""


class UnknownPromptError(Exception):
    """A prompt contract revision the lifecycle authority never registered. Callers fail closed (never
    assume ACTIVE)."""


class PromptDisabledError(Exception):
    """A prompt contract revision whose CURRENT lifecycle status is DISABLED or QUARANTINED."""


class PromptStateError(Exception):
    """A guarded Attempt prompt-state transition was rejected (duplicate plan, non-PLANNED dispatch, or a
    lost compare-and-set). Zero new Provider calls."""


# ---------------------------------------------------------------------------
# 3. Variable specification + immutable published Prompt Contract revision.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VariableSpec:
    """One declared input variable of a Prompt Contract revision. ``required`` variables must be supplied;
    an optional variable with a deterministic ``default`` is how a NEWER revision can stay backward
    compatible. ``allowed`` enumerates the closed value set for an ENUM variable (unknown value -> fail
    closed)."""

    name: str
    type: VariableType = VariableType.STR
    required: bool = True
    default: Optional[object] = None
    allowed: Optional[FrozenSet[str]] = None      # only for ENUM

    def __post_init__(self) -> None:
        if self.required and self.default is not None:
            raise ValueError(f"required variable {self.name!r} must not carry a default")
        if self.type is VariableType.ENUM and not self.allowed:
            raise ValueError(f"enum variable {self.name!r} needs a non-empty allowed set")


@dataclass(frozen=True)
class MessageTemplate:
    """One ordered message in the prompt. ``text`` uses ``{variable}`` placeholders resolved by the
    deterministic renderer. Roles are part of the prompt behaviour and are bound + hashed."""

    role: MessageRole
    text: str


# Semantic guarantee tokens the application relies on (e.g. a required citations guarantee). Weakening or
# dropping one is a SEMANTIC breaking change even if variables and schema are unchanged.
CITATIONS_REQUIRED = "citations_required"


@dataclass(frozen=True)
class PromptContractRevision:
    """A current, versioned prompt behaviour FACT — an immutable PUBLISHED revision. ``status`` is the status
    it was published with; the CURRENT operational status lives in a separate ``PromptLifecycle`` overlay so a
    live disable/quarantine never mutates this published fact and never changes how an already-bound Attempt
    is interpreted. Enough to render and interpret a model request reproducibly."""

    prompt_contract_id: str
    revision: str
    messages: Tuple[MessageTemplate, ...]
    variables: Tuple[VariableSpec, ...]
    compatible_application_contracts: FrozenSet[str]
    semantic_guarantees: FrozenSet[str]
    renderer_version: str
    status: PromptStatus = PromptStatus.ACTIVE

    def required_variable_names(self) -> FrozenSet[str]:
        return frozenset(v.name for v in self.variables if v.required)

    def optional_variable_names(self) -> FrozenSet[str]:
        return frozenset(v.name for v in self.variables if not v.required)

    def variable(self, name: str) -> Optional[VariableSpec]:
        for v in self.variables:
            if v.name == name:
                return v
        return None

    def supports_contract(self, application_contract: str) -> bool:
        return application_contract in self.compatible_application_contracts

    def guarantees(self, token: str) -> bool:
        return token in self.semantic_guarantees

    def disabled(self) -> "PromptContractRevision":
        return replace(self, status=PromptStatus.DISABLED)

    def quarantined(self) -> "PromptContractRevision":
        return replace(self, status=PromptStatus.QUARANTINED)


def _revision_key(prompt_contract_id: str, revision: str) -> Tuple[str, str]:
    return (prompt_contract_id, revision)


# ---------------------------------------------------------------------------
# 4. Lifecycle overlay (current operational status per revision), separate from published revisions.
# ---------------------------------------------------------------------------
class PromptLifecycle:
    """Current operational status per (prompt_contract_id, revision), SEPARATE from the immutable published
    revisions. A lifecycle update affects NEW selection and dispatch admission; it never edits a published
    revision's definition, and an already-bound Attempt is still interpreted by its original binding."""

    def __init__(self) -> None:
        self._status: Dict[Tuple[str, str], PromptStatus] = {}
        self._lock = threading.RLock()

    def register(self, revision: PromptContractRevision) -> None:
        with self._lock:
            self._status.setdefault(_revision_key(revision.prompt_contract_id, revision.revision),
                                    revision.status)

    def set_status(self, prompt_contract_id: str, revision: str, status: PromptStatus) -> None:
        with self._lock:
            self._status[_revision_key(prompt_contract_id, revision)] = status

    def disable(self, prompt_contract_id: str, revision: str) -> None:
        self.set_status(prompt_contract_id, revision, PromptStatus.DISABLED)

    def quarantine(self, prompt_contract_id: str, revision: str) -> None:
        self.set_status(prompt_contract_id, revision, PromptStatus.QUARANTINED)

    def status(self, prompt_contract_id: str, revision: str) -> PromptStatus:
        # A revision the authority never registered is UNKNOWN, NOT ACTIVE (fail-closed default): a caller
        # cannot bypass a disable by consulting an empty/foreign lifecycle catalog.
        with self._lock:
            return self._status.get(_revision_key(prompt_contract_id, revision), PromptStatus.UNKNOWN)

    def is_active(self, prompt_contract_id: str, revision: str) -> bool:
        return self.status(prompt_contract_id, revision) is PromptStatus.ACTIVE


# ---------------------------------------------------------------------------
# 5. The Prompt Contract registry (published revisions + current-default selection for NEW Attempts).
# ---------------------------------------------------------------------------
class PromptContractRegistry:
    """Holds immutable published revisions and the CURRENT DEFAULT revision per prompt_contract_id used when
    planning a NEW Attempt. Selection fails closed on an unknown/disabled/quarantined or incompatible default.
    The current default NEVER reinterprets an already-planned Attempt."""

    def __init__(self, lifecycle: Optional[PromptLifecycle] = None) -> None:
        self._revisions: Dict[Tuple[str, str], PromptContractRevision] = {}
        self._default: Dict[str, str] = {}
        self._lifecycle = lifecycle if lifecycle is not None else PromptLifecycle()

    @property
    def lifecycle(self) -> PromptLifecycle:
        return self._lifecycle

    def publish(self, revision: PromptContractRevision, make_default: bool = False) -> None:
        """Publish an immutable revision. Re-publishing the SAME (id, revision) with a DIFFERENT definition is
        rejected — a published revision is an immutable audit fact; a change is a NEW revision."""
        key = _revision_key(revision.prompt_contract_id, revision.revision)
        existing = self._revisions.get(key)
        if existing is not None and existing != revision:
            raise PromptBindingError(
                f"published revision {key} is immutable; publish a NEW revision instead of editing it")
        self._revisions[key] = revision
        self._lifecycle.register(revision)
        if make_default or revision.prompt_contract_id not in self._default:
            self._default[revision.prompt_contract_id] = revision.revision

    def set_default_revision(self, prompt_contract_id: str, revision: str) -> None:
        """Roll the CURRENT DEFAULT for new planning to an already-published revision (used by rollback)."""
        if _revision_key(prompt_contract_id, revision) not in self._revisions:
            raise UnknownPromptError(f"cannot default to unpublished revision {(prompt_contract_id, revision)}")
        self._default[prompt_contract_id] = revision

    def get_revision(self, prompt_contract_id: str, revision: str) -> PromptContractRevision:
        key = _revision_key(prompt_contract_id, revision)
        if key not in self._revisions:
            raise UnknownPromptError(f"unknown prompt revision {key}")
        return self._revisions[key]

    def select_default_for_new_attempt(self, prompt_contract_id: str,
                                       application_contract: str) -> PromptContractRevision:
        """Select the current-default revision for a NEW Attempt: it must be registered, currently ACTIVE by
        the authoritative lifecycle, and compatible with the application contract. Fails closed otherwise.
        This governs NEW planning ONLY."""
        if prompt_contract_id not in self._default:
            raise UnknownPromptError(f"no default revision for {prompt_contract_id!r}")
        revision = self._default[prompt_contract_id]
        status = self._lifecycle.status(prompt_contract_id, revision)
        if status is PromptStatus.UNKNOWN:
            raise UnknownPromptError(f"default revision {(prompt_contract_id, revision)} is unknown")
        if status is not PromptStatus.ACTIVE:
            raise PromptDisabledError(f"default revision {(prompt_contract_id, revision)} is {status.value}")
        rev = self.get_revision(prompt_contract_id, revision)
        if not rev.supports_contract(application_contract):
            raise PromptBindingError(
                f"default revision {(prompt_contract_id, revision)} does not support {application_contract}")
        return rev


# ---------------------------------------------------------------------------
# 6. Deterministic variable validation + migration/alias handling.
# ---------------------------------------------------------------------------
def apply_migration(raw_variables: Mapping[str, object],
                    alias_map: Optional[Mapping[str, str]] = None) -> Dict[str, object]:
    """Normalize provider-neutral input by applying an explicit, NON-mutating alias map (old_name ->
    new_name). If BOTH an old alias and its replacement are present:

    * equal values -> collapse to the new name (idempotent);
    * conflicting values -> raise ``AliasConflictError`` (never silently pick a winner).

    Migration is explicit and auditable; it produces a NEW normalized input, it does not rewrite history."""

    alias_map = dict(alias_map or {})
    out: Dict[str, object] = {}
    for key, value in raw_variables.items():
        target = alias_map.get(key, key)
        if target in out and out[target] != value:
            raise AliasConflictError(
                f"alias conflict: {key!r} -> {target!r} disagrees with an existing value for {target!r}")
        out[target] = value
    return out


def validate_and_fill_variables(revision: PromptContractRevision,
                                variables: Mapping[str, object]) -> Dict[str, object]:
    """Validate ``variables`` against the revision's input schema and return a fully-resolved variable map
    (optional defaults applied). Fails closed:

    * a required variable that is missing -> ``PromptVariableError``;
    * an unknown variable not declared by the revision -> ``PromptVariableError`` (fail closed; do NOT
      silently pass an unrecognized field through — e.g. an unknown ``tenant_policy`` value must be rejected,
      never defaulted to a permissive value);
    * a wrong type or an ENUM value outside the closed ``allowed`` set -> ``PromptVariableError``.
    """

    declared = {v.name: v for v in revision.variables}
    for name in variables:
        if name not in declared:
            raise PromptVariableError(f"unknown variable {name!r} for {revision.prompt_contract_id}/"
                                      f"{revision.revision}")
    resolved: Dict[str, object] = {}
    for spec in revision.variables:
        if spec.name in variables:
            value = variables[spec.name]
        elif spec.required:
            raise PromptVariableError(f"missing required variable {spec.name!r}")
        else:
            value = spec.default            # deterministic safe default for an optional variable
        _check_type(spec, value)
        resolved[spec.name] = value
    return resolved


def _check_type(spec: VariableSpec, value: object) -> None:
    if value is None and not spec.required:
        return
    if spec.type is VariableType.STR:
        if not isinstance(value, str):
            raise PromptVariableError(f"variable {spec.name!r} must be a string")
    elif spec.type is VariableType.INT:
        if not isinstance(value, int) or isinstance(value, bool):
            raise PromptVariableError(f"variable {spec.name!r} must be an int")
    elif spec.type is VariableType.BOOL:
        if not isinstance(value, bool):
            raise PromptVariableError(f"variable {spec.name!r} must be a bool")
    elif spec.type is VariableType.ENUM:
        if not isinstance(value, str) or spec.allowed is None or value not in spec.allowed:
            raise PromptVariableError(
                f"variable {spec.name!r}={value!r} is not in the allowed set {sorted(spec.allowed or [])} "
                f"(unknown policy values fail closed)")


# ---------------------------------------------------------------------------
# 7. Deterministic renderer + canonical fingerprint / rendered-message hash.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RenderedMessage:
    role: MessageRole
    content: str


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:            # never silently blank a missing placeholder
        raise PromptVariableError(f"template references undeclared/absent variable {key!r}")


def render_messages(revision: PromptContractRevision,
                    variables: Mapping[str, object]) -> List[RenderedMessage]:
    """Deterministically render the ordered messages after validating + filling variables. A template that
    references a variable the revision does not declare/provide fails closed. Rendering is a pure function of
    (revision, validated variables) — the same inputs always produce the same messages and hash."""

    resolved = validate_and_fill_variables(revision, variables)
    fmt = _SafeFormatDict({k: ("" if v is None else str(v)) for k, v in resolved.items()})
    formatter = string.Formatter()
    out: List[RenderedMessage] = []
    for msg in revision.messages:
        out.append(RenderedMessage(role=msg.role, content=formatter.vformat(msg.text, (), fmt)))
    return out


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_input_fingerprint(revision: PromptContractRevision,
                              variables: Mapping[str, object]) -> str:
    """A stable SHA-256 over the VALIDATED, resolved input variables (canonical, sorted). Optional defaults
    are included, so two calls that differ only by relying on the same default fingerprint identically."""
    resolved = validate_and_fill_variables(revision, variables)
    payload = _canonical_json({"pc": revision.prompt_contract_id, "rev": revision.revision, "vars": resolved})
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_rendered_hash(messages: List[RenderedMessage]) -> str:
    """A stable SHA-256 over the ordered rendered (role, content) messages — integrity evidence for the exact
    text sent. A hash is integrity evidence, NOT encryption and NOT authorization."""
    payload = _canonical_json([[m.role.value, m.content] for m in messages])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 8. Immutable per-Attempt prompt binding + in-memory authoritative store.
# ---------------------------------------------------------------------------
BINDING_FIELDS = (
    "prompt_contract_id", "revision", "renderer_version", "parameter_policy_id",
    "parameter_policy_revision", "application_contract", "input_fingerprint", "rendered_message_hash",
)


@dataclass(frozen=True)
class AttemptPromptBinding:
    """Snapshot of the prompt behaviour bound to ONE Attempt when it was planned. IMMUTABLE; never rewritten
    to a different revision — a re-plan is an explicit NEW Attempt. Equality (frozen dataclass) covers every
    binding field, so it can be compared as a whole for authoritative-binding checks. ``rendered_artifact_ref``
    is only a POINTER to a protected full-prompt artifact when policy permits storing it; it is not
    authorization by itself and not the prompt content."""

    attempt_id: str
    job_id: str
    prompt_contract_id: str
    revision: str
    renderer_version: str
    parameter_policy_id: str
    parameter_policy_revision: str
    application_contract: str
    input_fingerprint: str
    rendered_message_hash: str
    rendered_artifact_ref: Optional[str] = None


def plan_attempt_binding(*, attempt_id: str, job_id: str, revision: PromptContractRevision,
                         parameter_policy_id: str, parameter_policy_revision: str,
                         application_contract: str, variables: Mapping[str, object],
                         rendered_artifact_ref: Optional[str] = None) -> Tuple[AttemptPromptBinding,
                                                                               List[RenderedMessage]]:
    """Plan a NEW Attempt's immutable prompt binding: validate + render deterministically, then bind the
    revision + renderer version + independently-versioned parameter policy + application contract + canonical
    input fingerprint + rendered-message hash. Returns the binding and the rendered messages."""

    messages = render_messages(revision, variables)
    binding = AttemptPromptBinding(
        attempt_id=attempt_id, job_id=job_id,
        prompt_contract_id=revision.prompt_contract_id, revision=revision.revision,
        renderer_version=revision.renderer_version,
        parameter_policy_id=parameter_policy_id, parameter_policy_revision=parameter_policy_revision,
        application_contract=application_contract,
        input_fingerprint=compute_input_fingerprint(revision, variables),
        rendered_message_hash=compute_rendered_hash(messages),
        rendered_artifact_ref=rendered_artifact_ref,
    )
    return binding, messages


class AttemptPromptState(str, Enum):
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    BLOCKED_PROMPT_DISABLED = "BLOCKED_PROMPT_DISABLED"


@dataclass(frozen=True)
class AttemptPromptRecord:
    binding: AttemptPromptBinding
    state: AttemptPromptState


class InMemoryAttemptPromptStore:
    """A tiny, injectable in-memory store holding each Attempt's AUTHORITATIVE ``AttemptPromptBinding`` and
    guarding the 'one Attempt -> at most one dispatch' invariant with a compare-and-set bound to (identity +
    full binding + expected state) under an ``RLock``. NOT a durable database — a production deployment needs
    a DB conditional UPDATE / transaction."""

    def __init__(self) -> None:
        self._records: Dict[str, AttemptPromptRecord] = {}
        self._lock = threading.RLock()

    def plan(self, binding: AttemptPromptBinding) -> None:
        with self._lock:
            if binding.attempt_id in self._records:
                raise PromptStateError(f"attempt already planned: {binding.attempt_id}")
            self._records[binding.attempt_id] = AttemptPromptRecord(binding, AttemptPromptState.PLANNED)

    def get_record(self, attempt_id: str) -> Optional[AttemptPromptRecord]:
        with self._lock:
            return self._records.get(attempt_id)

    def compare_and_set(self, binding: AttemptPromptBinding, expected: AttemptPromptState,
                        new: AttemptPromptState) -> bool:
        with self._lock:
            rec = self._records.get(binding.attempt_id)
            if rec is None or rec.state is not expected or rec.binding != binding:
                return False
            self._records[binding.attempt_id] = AttemptPromptRecord(binding, new)
            return True


def validate_attempt_prompt_binding(binding: AttemptPromptBinding,
                                    revision: PromptContractRevision) -> None:
    """Raise ``PromptBindingError`` unless the resolved revision matches the binding's prompt contract id,
    revision and renderer version. The bound revision interprets an already-issued call — never the current
    default."""
    if revision.prompt_contract_id != binding.prompt_contract_id or revision.revision != binding.revision:
        raise PromptBindingError(
            f"resolved revision {(revision.prompt_contract_id, revision.revision)} != bound "
            f"{(binding.prompt_contract_id, binding.revision)}")
    if revision.renderer_version != binding.renderer_version:
        raise PromptBindingError(
            f"renderer_version mismatch: revision={revision.renderer_version} bound={binding.renderer_version}")


# ---------------------------------------------------------------------------
# 9. The pre-Provider LLM Runtime gate.
# ---------------------------------------------------------------------------
class PromptGateOutcome(str, Enum):
    READY = "READY"                                   # rendered + verified; may proceed to Provider admission
    BINDING_MISMATCH = "BINDING_MISMATCH"             # caller payload != authoritative bound revision
    UNKNOWN_PROMPT = "UNKNOWN_PROMPT"                  # bound revision not registered -> fail closed
    BLOCKED_PROMPT_DISABLED = "BLOCKED_PROMPT_DISABLED"  # bound revision disabled/quarantined
    INCOMPATIBLE_CONTRACT = "INCOMPATIBLE_CONTRACT"   # bound revision incompatible with application contract
    VARIABLE_INVALID = "VARIABLE_INVALID"             # inputs violate the revision schema (fail closed)
    INPUT_FINGERPRINT_MISMATCH = "INPUT_FINGERPRINT_MISMATCH"  # validated inputs differ from the binding
    RENDER_HASH_MISMATCH = "RENDER_HASH_MISMATCH"     # re-render does not match the bound rendered hash


@dataclass(frozen=True)
class PromptGateResult:
    outcome: PromptGateOutcome
    provider_calls: int                               # THIS gate only: 0 unless READY, then 1 (models the
                                                      # in-process crossing toward the Provider boundary)
    attempt_state: AttemptPromptState
    detail: str = ""
    rendered_message_hash: Optional[str] = None


def prepare_dispatch(*, request_binding: AttemptPromptBinding, variables: Mapping[str, object],
                     store: InMemoryAttemptPromptStore, registry: PromptContractRegistry) -> PromptGateResult:
    """The LLM Runtime gate that runs BEFORE any Provider capability admission or adapter call. Gates, in
    order — each failure making ZERO Provider calls:

    1. Read the AUTHORITATIVE binding from the store; reject if unknown, if the caller's ``request_binding``
       differs from the stored authoritative binding (``BINDING_MISMATCH`` — the Attempt stays ``PLANNED``),
       or if the state is not ``PLANNED``.
    2. Resolve the bound revision from the registry by its EXACT (prompt_contract_id, revision); an
       unregistered revision fails closed (``UNKNOWN_PROMPT``).
    3. Read the CURRENT lifecycle status of the bound revision. An UNKNOWN status fails closed; a
       DISABLED/QUARANTINED bound revision is a guarded ``PLANNED -> BLOCKED_PROMPT_DISABLED`` transition
       (binding preserved, zero calls).
    4. Verify the bound revision is compatible with the binding's application contract.
    5. Re-validate variables, verify their canonical fingerprint, deterministically RE-RENDER, then verify
       the rendered-message hash equals the bound hash (binding verification). Only then authorize crossing
       toward the Provider boundary (``provider_calls=1``) via a guarded ``PLANNED -> DISPATCHED``
       compare-and-set.

    Business authorization is the APPLICATION's responsibility and is assumed already granted before this gate
    — a prompt variable is never authorization evidence.
    """

    record = store.get_record(request_binding.attempt_id)
    if record is None:
        raise PromptStateError(f"unknown attempt (not planned): {request_binding.attempt_id}")
    authoritative = record.binding
    # (1) reject a forged/mismatched caller binding; use the STORE's authoritative binding thereafter.
    if request_binding != authoritative:
        return PromptGateResult(PromptGateOutcome.BINDING_MISMATCH, provider_calls=0,
                                attempt_state=record.state,
                                detail="caller binding does not match the persisted Attempt binding")
    if record.state is not AttemptPromptState.PLANNED:
        raise PromptStateError(
            f"attempt {authoritative.attempt_id} is {record.state.value}, only PLANNED may dispatch")

    # (2) resolve the bound revision (exact version) — fail closed if unknown.
    try:
        revision = registry.get_revision(authoritative.prompt_contract_id, authoritative.revision)
    except UnknownPromptError as e:
        return PromptGateResult(PromptGateOutcome.UNKNOWN_PROMPT, provider_calls=0,
                                attempt_state=record.state, detail=str(e))

    # (3) admission against the CURRENT lifecycle status of the BOUND revision.
    status = registry.lifecycle.status(authoritative.prompt_contract_id, authoritative.revision)
    if status is PromptStatus.UNKNOWN:
        return PromptGateResult(PromptGateOutcome.UNKNOWN_PROMPT, provider_calls=0,
                                attempt_state=record.state, detail="bound revision unknown to lifecycle")
    if status is not PromptStatus.ACTIVE:
        if not store.compare_and_set(authoritative, AttemptPromptState.PLANNED,
                                     AttemptPromptState.BLOCKED_PROMPT_DISABLED):
            raise PromptStateError(f"could not block attempt {authoritative.attempt_id}")
        return PromptGateResult(PromptGateOutcome.BLOCKED_PROMPT_DISABLED, provider_calls=0,
                                attempt_state=AttemptPromptState.BLOCKED_PROMPT_DISABLED,
                                detail=f"bound revision is {status.value}")

    # binding vs resolved revision structural check (renderer version etc.).
    validate_attempt_prompt_binding(authoritative, revision)

    # (4) application-contract compatibility of the bound revision.
    if not revision.supports_contract(authoritative.application_contract):
        return PromptGateResult(PromptGateOutcome.INCOMPATIBLE_CONTRACT, provider_calls=0,
                                attempt_state=record.state,
                                detail=f"revision does not support {authoritative.application_contract}")

    # (5) re-validate + re-render deterministically, verify both bound input and rendered evidence. The input
    # fingerprint is necessary even when a declared variable is not interpolated into a message: changing
    # that variable must not be hidden by an unchanged rendered-message hash.
    try:
        input_fingerprint = compute_input_fingerprint(revision, variables)
        messages = render_messages(revision, variables)
    except PromptVariableError as e:
        return PromptGateResult(PromptGateOutcome.VARIABLE_INVALID, provider_calls=0,
                                attempt_state=record.state, detail=str(e))
    if input_fingerprint != authoritative.input_fingerprint:
        return PromptGateResult(PromptGateOutcome.INPUT_FINGERPRINT_MISMATCH, provider_calls=0,
                                attempt_state=record.state,
                                detail="validated inputs do not match the bound input fingerprint")
    rendered_hash = compute_rendered_hash(messages)
    if rendered_hash != authoritative.rendered_message_hash:
        return PromptGateResult(PromptGateOutcome.RENDER_HASH_MISMATCH, provider_calls=0,
                                attempt_state=record.state,
                                detail="re-render does not match the bound rendered hash")

    if not store.compare_and_set(authoritative, AttemptPromptState.PLANNED, AttemptPromptState.DISPATCHED):
        raise PromptStateError(
            f"attempt {authoritative.attempt_id} could not transition PLANNED -> DISPATCHED")
    return PromptGateResult(PromptGateOutcome.READY, provider_calls=1,
                            attempt_state=AttemptPromptState.DISPATCHED, detail="rendered + verified",
                            rendered_message_hash=rendered_hash)


# ---------------------------------------------------------------------------
# 10. Compatibility reasoning (structural + semantic, directional).
# ---------------------------------------------------------------------------
def backward_incompatibilities(old: PromptContractRevision,
                               new: PromptContractRevision) -> List[str]:
    """Return the reasons ``new`` is NOT backward compatible with ``old`` (empty list == backward
    compatible). Backward compatibility = ``new`` accepts valid OLD inputs AND preserves the guarantees old
    callers relied on. Both structural and semantic:

    * a required variable of ``old`` that ``new`` drops or no longer accepts (e.g. a rename without an alias)
      is structurally breaking;
    * a NEW required variable without a default is breaking (old callers never sent it);
    * a semantic guarantee present in ``old`` but absent in ``new`` (e.g. citations_required -> optional) is a
      semantic breaking change even if variables/schema are unchanged.

    Adding an OPTIONAL variable with a deterministic default is NOT breaking. Compatibility is not based on
    human semantic resemblance of names — a rename is structural.
    """

    reasons: List[str] = []
    old_names = {v.name: v for v in old.variables}
    new_names = {v.name: v for v in new.variables}

    for name in old_names:
        if name not in new_names:
            reasons.append(
                f"previously accepted variable {name!r} removed (no alias/migration) — structural break")

    for name, spec in new_names.items():
        if name not in old_names and spec.required and spec.default is None:
            reasons.append(f"new required variable {name!r} without default — old callers cannot satisfy it")

    for name, old_spec in old_names.items():
        new_spec = new_names.get(name)
        if new_spec is None:
            continue
        if old_spec.type is not new_spec.type:
            reasons.append(f"variable {name!r} type changed {old_spec.type.value}->{new_spec.type.value}")
        if (old_spec.type is VariableType.ENUM and new_spec.type is VariableType.ENUM
                and old_spec.allowed and new_spec.allowed
                and not old_spec.allowed.issubset(new_spec.allowed)):
            reasons.append(f"enum {name!r} narrowed — some old values no longer accepted")

    for token in old.semantic_guarantees:
        if token not in new.semantic_guarantees:
            reasons.append(f"semantic guarantee {token!r} dropped/weakened — semantic break")

    removed_contracts = old.compatible_application_contracts - new.compatible_application_contracts
    for contract in sorted(removed_contracts):
        reasons.append(f"previously supported application contract {contract!r} removed")

    return reasons


def is_backward_compatible(old: PromptContractRevision, new: PromptContractRevision) -> bool:
    return not backward_incompatibilities(old, new)


# ---------------------------------------------------------------------------
# 11. Late response / reconciliation (interpret with the BOUND revision; never overwrite unsafe state).
# ---------------------------------------------------------------------------
class ReconciliationDecision(str, Enum):
    INTERPRET_WITH_BOUND_REVISION = "INTERPRET_WITH_BOUND_REVISION"  # valid late response, use bound revision
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"                # timeout unknown -> reconcile, no retry
    REFUSED_TERMINAL = "REFUSED_TERMINAL"                            # Attempt already terminal
    REFUSED_NOT_AWAITING = "REFUSED_NOT_AWAITING"                    # not awaiting a late response
    REFUSED_BINDING_MISMATCH = "REFUSED_BINDING_MISMATCH"           # response's binding != authoritative


def classify_timeout_unknown() -> ReconciliationDecision:
    """A dispatched-then-timed-out Attempt has UNKNOWN execution/cost. It must enter reconciliation; never
    assume success or failure and never blindly retry."""
    return ReconciliationDecision.PENDING_RECONCILIATION


def interpret_late_response(*, authoritative: AttemptPromptBinding, response_binding: AttemptPromptBinding,
                            attempt_state: AttemptPromptState, awaiting_reconciliation: bool,
                            registry: PromptContractRegistry) -> Tuple[ReconciliationDecision,
                                                                       Optional[PromptContractRevision]]:
    """Decide how to interpret a late Provider response. A valid late response is interpreted using the
    revision BOUND to that Attempt (not the current default); a stale/terminal/superseded or binding-mismatched
    response must not overwrite authoritative state."""

    if attempt_state is AttemptPromptState.BLOCKED_PROMPT_DISABLED:
        return ReconciliationDecision.REFUSED_TERMINAL, None
    if not awaiting_reconciliation:
        return ReconciliationDecision.REFUSED_NOT_AWAITING, None
    if response_binding != authoritative:
        return ReconciliationDecision.REFUSED_BINDING_MISMATCH, None
    bound_revision = registry.get_revision(authoritative.prompt_contract_id, authoritative.revision)
    return ReconciliationDecision.INTERPRET_WITH_BOUND_REVISION, bound_revision
