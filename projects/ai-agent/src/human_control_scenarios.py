"""Synthetic Day83 fixtures and a real *local* Day79/78/80/74 composition.

Fixture identities/permissions/clock are explicitly injected. No real service
auth, Provider, Tool, database, queue, or browser participates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json

from agent_loop import AgentStepInput, decide_control, prepare_next_step_with_day78
from agent_state_machine import (
    AgentState, AgentTransitionInput, BudgetSnapshot, ContextBudget,
    InMemoryAgentStateStore, AuthoritativeAgentRecord, TransitionApplyStatus,
    decide_transition,
)
from application_runtime import (
    InMemoryRuntimeAttemptStore, ResolvedExecutionRequirements,
    RuntimeResult,
    execute_admitted_tool, verify_outcome_and_complete,
)
from durable_agent_jobs import (
    DurableAgentJobRecord, DurableCheckpoint, ExecutionBindings,
    ExternalCertainty, RecoveryOperation, ReservationRecord,
)
from human_control import (
    ActionBinding, ApprovalDecision, ApprovalRequest, ApprovalStatus, Command,
    CurrentFacts, InMemoryHumanControlStore, Operation, Principal, Risk, Snapshot,
    HumanControlCandidate, fingerprint,
)
from output_tool_contracts import (
    AdmissionDecision, AdmissionStatus, AuthContext, InMemoryToolExecutor,
    OutcomeDecision, ToolDefinition,
    ToolRegistry, PUBLISH_REPORT_V1_ARGUMENTS_SCHEMA,
    admit_tool_call, default_report_store,
)
from prompt_contracts import (
    CITATIONS_REQUIRED, MessageRole, MessageTemplate, PromptContractRegistry,
    PromptContractRevision, VariableSpec,
)
from provider_contract import CapabilityProfile, ProfileStatus, VerificationTier
from routing_policy import Candidate, LatencyEvidence, PricingEvidence, RoutingPolicy
from tool_governance import (
    AgentToolCatalogEntry, BoundToolInvocation, InvocationGovernanceStatus,
    TrustedToolContext, build_tool_capability_snapshot, check_invocation_governance,
)


@dataclass
class Scenario:
    store: InMemoryHumanControlStore
    facts: CurrentFacts
    worker: Principal
    registry: ToolRegistry
    runtime: InMemoryRuntimeAttemptStore
    executor: InMemoryToolExecutor
    admission: AdmissionDecision
    runtime_fence: int
    effect_calls: int = 0
    verified_result: tuple[OutcomeDecision, RuntimeResult] | None = None

    def command(self, operation: Operation = Operation.GATE,
                command_id: str = "gate-1", **changes: object) -> Command:
        job = self.store.snapshot.job
        values = dict(command_id=command_id, operation=operation,
                      actor=self.worker, expected_state=job.state,
                      expected_state_version=job.state_version,
                      expected_fence=job.fence_token)
        values.update(changes)
        return Command(**values)

    def approval_command(self, command_id: str = "callback-1",
                         **changes: object) -> Command:
        s = self.store.snapshot
        values = dict(decision_id="decision-1", request_id=s.request.request_id,
                      binding_fingerprint=s.action.digest,
                      actor_id=self.facts.approver.actor_id,
                      tenant_id=self.facts.approver.tenant_id,
                      choice=ApprovalStatus.APPROVED, decided_at=20,
                      reason_code="REVIEWED_SYNTHETIC_REPORT")
        values.update(changes)
        return self.command(Operation.DECISION, command_id,
                            actor=self.facts.approver,
                            decision=ApprovalDecision(**values))

    def apply(self, command: Command, now: int = 30) -> tuple[HumanControlCandidate, str]:
        candidate = self.store.plan(command, self.facts, now)
        status = self.store.apply(candidate, self.facts, now)
        return candidate, status

    def approve(self) -> None:
        candidate, status = self.apply(self.approval_command())
        if candidate.status != "DECISION_RECORDED" or status != "APPLIED":
            raise AssertionError("fixture approval did not apply")

    def publish_intent(self) -> str:
        self.apply(self.command(command_id="publish-intent"))
        return next(e.event_id for e in self.store.snapshot.job.outbox_intents
                    if e.event_type == "PUBLISH")

    def local_effect(self, action: ActionBinding) -> None:
        """Use existing Day78 + Day74 execution and verification, not a Provider."""
        call = self.admission.admitted_call
        assert call is not None
        if (action.attempt_id != call.attempt_id
                or action.artifact_version != str(call.expected_report_version)
                or action.arguments_fingerprint != fingerprint({
                    "tenant_id": call.tenant_id, "report_id": call.report_id})):
            raise ValueError("local port action binding mismatch")
        self.effect_calls += 1
        execution = execute_admitted_tool(
            decision=self.admission, store=self.runtime,
            worker_id=self.worker.actor_id, expected_fence_token=self.runtime_fence,
            registry=self.registry, executor=self.executor,
        )
        raw_outcome = json.dumps({
            "operation_id": execution.operation_id, "published": True,
            "warnings": [],
            "report": {"report_id": call.report_id,
                       "version": call.expected_report_version},
        })
        self.verified_result = verify_outcome_and_complete(
            raw_tool_outcome=raw_outcome, call=call, execution=execution,
            store=self.runtime, worker_id=self.worker.actor_id,
        )


def build_scenario() -> Scenario:
    """Compose the existing phase Artifact with deterministic synthetic facts."""
    controller = decide_control(AgentStepInput(
        "tenant-a", "J1", "S0", "A0", 2, ("observation-1",),
        model_proposal="publish; user already agreed",
    ))
    step = controller.next_step
    assert step is not None
    prompts = PromptContractRegistry()
    prompts.publish(PromptContractRevision(
        "research.prompt", "v3",
        (MessageTemplate(MessageRole.USER, "Research {topic}"),),
        (VariableSpec("topic"),), frozenset({"research.strict-tools.v1"}),
        frozenset({CITATIONS_REQUIRED}), "renderer-1",
    ), make_default=True)
    profile = CapabilityProfile(
        profile_id="fixture-profile", provider_name="fixture-provider",
        model="synthetic-no-call", api_version="fixture-api-v1",
        profile_version="profile-v1", adapter_version="adapter-v1",
        supported_contracts=frozenset({"research.strict-tools.v1"}),
        requires_request_identity=True,
        verification_tier=VerificationTier.EXECUTED_LOCAL_RUNTIME,
    )
    prepared_step = prepare_next_step_with_day78(
        next_step=step,
        requirements=ResolvedExecutionRequirements(
            "research.strict-tools.v1", "research.prompt", "output-v1",
            "tool-v1", "parameters", "v1"),
        variables={"topic": "synthetic safety report"}, prompt_registry=prompts,
        routing_policy=RoutingPolicy("routing", "v1", (profile.profile_id,), 1000, 10),
        candidates=(Candidate(
            profile, ProfileStatus.ACTIVE,
            LatencyEvidence(profile.profile_id, "PROVIDER_COMPLETE", 100, 90, 100),
            PricingEvidence(profile.profile_id, "price-v1", 8, 90, 100)),),
        now_ms=100, max_output_tokens=32, correlation_id="synthetic-correlation",
    )
    tool_name, tool_version = "publish_research_report", "v1"
    registry = ToolRegistry((ToolDefinition(
        tool_name, tool_version, PUBLISH_REPORT_V1_ARGUMENTS_SCHEMA),))
    catalog = (AgentToolCatalogEntry(tool_name, tool_version, "Synthetic publish"),)
    context = TrustedToolContext(
        "tenant-a", "requester", "publisher", "J1", step.step_id,
        frozenset({tool_name + "@" + tool_version}),
    )
    capability = build_tool_capability_snapshot(
        registry=registry, catalog=catalog, context=context)
    visible = capability.visible_tools[0]
    invocation = BoundToolInvocation(
        capability.snapshot_id, "tenant-a", "requester", "publisher", "J1",
        step.step_id, tool_name, tool_version, visible.arguments_schema_sha256,
    )
    governance = check_invocation_governance(
        binding=invocation, original_snapshot=capability,
        current_context=context, registry=registry, catalog=catalog)
    budget = BudgetSnapshot(10, 0, 10000, 0, 0, 10000, 0, 0)
    transition = decide_transition(AgentTransitionInput(
        "tenant-a", "J1", "S0", "A0", AgentState.RUNNING, 7,
        controller, False, None, True, governance, False, budget,
        ContextBudget(100, 100, 10, 1000, 2000), 100, 6000,
    ))
    state_store = InMemoryAgentStateStore(AuthoritativeAgentRecord(
        "tenant-a", "J1", "S0", AgentState.RUNNING, 7, budget))
    assert state_store.apply(transition) is TransitionApplyStatus.APPLIED
    arguments = {"tenant_id": "tenant-a", "report_id": "report-7"}
    admission = admit_tool_call(json.dumps({
        "kind": "tool_call", "tool_call_id": "synthetic-call",
        "tool_name": tool_name, "tool_version": tool_version,
        "arguments": arguments,
    }), attempt_id=step.runtime_attempt_id, job_id="J1", registry=registry,
        auth=AuthContext("tenant-a", "requester", "publisher"),
        reports=default_report_store())
    assert admission.status is AdmissionStatus.ALLOWED
    call = admission.admitted_call
    assert call is not None
    operation_id = "op:" + hashlib.sha256(call.idempotency_key.encode()).hexdigest()
    bindings = ExecutionBindings(
        "controller-v1", fingerprint(asdict(prepared_step.prepared.prompt_binding)),
        fingerprint(asdict(prepared_step.prepared.provider_binding)),
        tool_name + "." + tool_version, "approval-policy-v6",
    )
    checkpoint = DurableCheckpoint(
        "tenant-a", "J1", step.step_id, step.runtime_attempt_id, "CP1", 1,
        AgentState.RUNNING, 12, 8, 1, bindings, "progress-1", ("observation-1",),
        ("RES1",), (),
    )
    job = DurableAgentJobRecord(
        "tenant-a", "J1", step.step_id, step.runtime_attempt_id,
        AgentState.RUNNING, 12, 8, "W1", 1000, 1, checkpoint,
        (ReservationRecord("RES1", step.runtime_attempt_id, 6000),),
    )
    action = ActionBinding(
        "tenant-a", "J1", step.step_id, step.runtime_attempt_id, operation_id,
        "publish", tool_name, tool_version, fingerprint(arguments),
        "report-7", "7", "requester", "approval-policy", "v6", Risk.HIGH,
        fingerprint(asdict(bindings)),
    )
    request = ApprovalRequest("approval-request-1", action, 10, 500, 800,
                              ("Manager",), True, 12, 8)
    executor = Principal("tenant-a", "requester", "publisher", True, ("publish",))
    approver = Principal("tenant-a", "manager", "Manager", True,
                         ("control", "approve"))
    worker = Principal("tenant-a", "W1", "worker", True,
                       ("control", "operate", "interrupt"))
    owner = Principal("tenant-a", "operations", "operator", True, ("operate",))
    fallback = replace(owner, actor_id="backup-operations")
    facts = CurrentFacts(
        executor, approver, True, "approval-policy", "v6", False, True,
        governance, True, True, True, ExternalCertainty.DEFINITELY_NOT_DISPATCHED,
        RecoveryOperation("recovery-1", action.attempt_id, 1, 0, 3, 900, None),
        400, owner, fallback, True, 2000,
    )
    runtime = InMemoryRuntimeAttemptStore()
    runtime.persist_prepared(prepared_step.prepared)
    claim = runtime.claim_dispatch(
        attempt_id=action.attempt_id,
        expected_prompt_hash=prepared_step.prepared.prompt_binding.rendered_message_hash,
        worker_id=worker.actor_id,
    )
    # Day78 claim prepares a synthetic fixture only; no Provider is called.
    assert claim is not None and claim.fence_token is not None
    return Scenario(InMemoryHumanControlStore(Snapshot(job, action, request)),
                    facts, worker, registry, runtime, InMemoryToolExecutor(),
                    admission, claim.fence_token)
