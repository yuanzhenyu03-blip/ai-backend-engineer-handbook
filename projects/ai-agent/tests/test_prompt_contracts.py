"""Day73 — EXECUTED_LOCAL_RUNTIME tests for the application-owned Prompt Contract + pre-Provider LLM Runtime
gate (deterministic, in-process; standard library only; no network, no SDK, no real Provider, no database).

Covered (from the Day73 required scenarios):

  1. immutable revision binding (published revision cannot be edited in place);
  2. current default vs historical Attempt binding (default governs NEW planning only);
  3. binding mismatch -> zero Provider calls, Attempt stays PLANNED;
  4. disabled bound revision -> BLOCKED_PROMPT_DISABLED, zero Provider calls;
  5. missing variables + unknown-policy value fail closed;
  6. backward-compatible optional variable with a safe default;
  7. breaking rename without alias/migration;
  8. conflicting alias rejection;
  9. semantic-guarantee weakening (citations required -> optional) is a break;
 10. renderer/parameter-policy binding + rendered hash;
 11. migration without rewriting historical Attempts;
 12. timeout-unknown reconciliation + late-response safety (interpret with the bound revision).

The ``provider_calls`` counter models crossing the in-process gate toward the Provider boundary only. It is
NOT proof of a real Provider Adapter, SDK, HTTP, network, database, or external call. INTEGRATION_RUNTIME and
PRODUCTION are NOT RUN.

Run from ``projects/ai-agent/``:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prompt_contracts import (  # noqa: E402
    AliasConflictError,
    AttemptPromptState,
    CITATIONS_REQUIRED,
    InMemoryAttemptPromptStore,
    MessageRole,
    MessageTemplate,
    PromptBindingError,
    PromptContractRegistry,
    PromptContractRevision,
    PromptDisabledError,
    PromptGateOutcome,
    PromptLifecycle,
    PromptStatus,
    PromptVariableError,
    ReconciliationDecision,
    UnknownPromptError,
    VariableSpec,
    VariableType,
    apply_migration,
    backward_incompatibilities,
    classify_timeout_unknown,
    compute_rendered_hash,
    interpret_late_response,
    is_backward_compatible,
    plan_attempt_binding,
    prepare_dispatch,
    render_messages,
)

CONTRACT = "research_claims.v1"
POLICY_ID = "params.balanced"
POLICY_REV = "p1"


def _rev(revision="v1", *, variables=None, guarantees=(CITATIONS_REQUIRED,), renderer="r1",
         messages=None, status=PromptStatus.ACTIVE, contracts=(CONTRACT,), pcid="research_report"):
    if variables is None:
        variables = (VariableSpec("topic", VariableType.STR, required=True),)
    if messages is None:
        messages = (
            MessageTemplate(MessageRole.SYSTEM, "You are a research assistant. Cite every claim."),
            MessageTemplate(MessageRole.USER, "Write about {topic}."),
        )
    return PromptContractRevision(
        prompt_contract_id=pcid, revision=revision, messages=tuple(messages),
        variables=tuple(variables), compatible_application_contracts=frozenset(contracts),
        semantic_guarantees=frozenset(guarantees), renderer_version=renderer, status=status)


def _registry_with(revision, make_default=True):
    reg = PromptContractRegistry()
    reg.publish(revision, make_default=make_default)
    return reg


def _plan(reg, revision, *, attempt_id="A1", job_id="job-1", variables=None):
    variables = variables if variables is not None else {"topic": "vaccines"}
    binding, messages = plan_attempt_binding(
        attempt_id=attempt_id, job_id=job_id, revision=revision, parameter_policy_id=POLICY_ID,
        parameter_policy_revision=POLICY_REV, application_contract=CONTRACT, variables=variables)
    store = InMemoryAttemptPromptStore()
    store.plan(binding)
    return binding, messages, store


# ===========================================================================
# 1 + 2. Immutable revision binding; current default vs historical Attempt binding.
# ===========================================================================
class ImmutableBindingAndDefault(unittest.TestCase):
    def test_publishing_same_revision_id_with_different_definition_is_rejected(self):
        reg = _registry_with(_rev("v1"))
        drifted = _rev("v1", messages=(MessageTemplate(MessageRole.SYSTEM, "Citations optional now."),))
        with self.assertRaises(PromptBindingError):
            reg.publish(drifted)                          # editing a published revision in place is rejected

    def test_default_selects_only_for_new_attempt_history_keeps_bound_revision(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding_v1, _, store = _plan(reg, v1, attempt_id="A1")
        # Publish v2 and make it the new default; A1 is already planned bound to v1.
        v2 = _rev("v2")
        reg.publish(v2, make_default=True)
        # A NEW attempt selects the current default (v2)...
        self.assertEqual(reg.select_default_for_new_attempt("research_report", CONTRACT).revision, "v2")
        # ...but A1's authoritative binding is still v1 and the gate interprets it with v1.
        self.assertEqual(store.get_record("A1").binding.revision, "v1")
        res = prepare_dispatch(request_binding=binding_v1, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.READY)
        self.assertEqual(res.provider_calls, 1)

    def test_rollback_default_to_older_safe_revision(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        v2 = _rev("v2", guarantees=())                    # weakened
        reg.publish(v2, make_default=True)
        self.assertEqual(reg.select_default_for_new_attempt("research_report", CONTRACT).revision, "v2")
        reg.set_default_revision("research_report", "v1")   # rollback
        self.assertEqual(reg.select_default_for_new_attempt("research_report", CONTRACT).revision, "v1")


# ===========================================================================
# 3 + 4. Binding mismatch (zero calls, PLANNED); disabled bound revision (zero calls).
# ===========================================================================
class GateFailClosed(unittest.TestCase):
    def test_binding_mismatch_zero_calls_attempt_stays_planned(self):
        v2 = _rev("v2")
        reg = _registry_with(v2)
        binding_v2, _, store = _plan(reg, v2, attempt_id="A1")
        # A caller forges a v1 dispatch payload for the SAME attempt_id (authoritative is v2).
        v1 = _rev("v1")
        reg.publish(v1)
        forged, _ = plan_attempt_binding(
            attempt_id="A1", job_id="job-1", revision=v1, parameter_policy_id=POLICY_ID,
            parameter_policy_revision=POLICY_REV, application_contract=CONTRACT, variables={"topic": "vaccines"})
        res = prepare_dispatch(request_binding=forged, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.BINDING_MISMATCH)
        self.assertEqual(res.provider_calls, 0)
        self.assertIs(store.get_record("A1").state, AttemptPromptState.PLANNED)   # authoritative unchanged
        self.assertEqual(store.get_record("A1").binding.revision, "v2")

    def test_disabled_bound_revision_blocked_zero_calls(self):
        v2 = _rev("v2")
        reg = _registry_with(v2)
        binding_v2, _, store = _plan(reg, v2, attempt_id="A1")
        reg.lifecycle.disable("research_report", "v2")     # the authoritative bound revision is disabled
        res = prepare_dispatch(request_binding=binding_v2, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.BLOCKED_PROMPT_DISABLED)
        self.assertEqual(res.provider_calls, 0)
        self.assertIs(res.attempt_state, AttemptPromptState.BLOCKED_PROMPT_DISABLED)
        self.assertIs(store.get_record("A1").state, AttemptPromptState.BLOCKED_PROMPT_DISABLED)

    def test_quarantined_bound_revision_blocked_zero_calls(self):
        v2 = _rev("v2")
        reg = _registry_with(v2)
        binding_v2, _, store = _plan(reg, v2, attempt_id="A1")
        reg.lifecycle.quarantine("research_report", "v2")
        res = prepare_dispatch(request_binding=binding_v2, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.BLOCKED_PROMPT_DISABLED)
        self.assertEqual(res.provider_calls, 0)

    def test_unknown_bound_revision_fails_closed(self):
        # Lifecycle status forced UNKNOWN for the bound revision -> fail closed, zero calls.
        v2 = _rev("v2")
        reg = _registry_with(v2)
        binding_v2, _, store = _plan(reg, v2, attempt_id="A1")
        reg.lifecycle.set_status("research_report", "v2", PromptStatus.UNKNOWN)
        res = prepare_dispatch(request_binding=binding_v2, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.UNKNOWN_PROMPT)
        self.assertEqual(res.provider_calls, 0)
        self.assertIs(store.get_record("A1").state, AttemptPromptState.PLANNED)

    def test_active_compatible_revision_is_ready_once(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1")
        res = prepare_dispatch(request_binding=binding, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.READY)
        self.assertEqual(res.provider_calls, 1)
        self.assertIs(store.get_record("A1").state, AttemptPromptState.DISPATCHED)
        # A second dispatch of the same Attempt is rejected (guarded state; not PLANNED).
        with self.assertRaises(Exception):
            prepare_dispatch(request_binding=binding, variables={"topic": "vaccines"},
                             store=store, registry=reg)

    def test_incompatible_application_contract_blocks_zero_calls(self):
        # Bound revision supports only a different contract than the binding's application_contract.
        v1 = _rev("v1", contracts=("other.v1",))
        reg = PromptContractRegistry()
        reg.publish(v1, make_default=True)
        binding, _ = plan_attempt_binding(
            attempt_id="A1", job_id="job-1", revision=v1, parameter_policy_id=POLICY_ID,
            parameter_policy_revision=POLICY_REV, application_contract="other.v1", variables={"topic": "x"})
        store = InMemoryAttemptPromptStore(); store.plan(binding)
        # Now pretend the runtime asserts CONTRACT compatibility: rebuild a binding claiming CONTRACT.
        mismatched = plan_attempt_binding(
            attempt_id="A2", job_id="job-1", revision=_rev("v9", contracts=("other.v1",)),
            parameter_policy_id=POLICY_ID, parameter_policy_revision=POLICY_REV,
            application_contract=CONTRACT, variables={"topic": "x"})[0]
        reg.publish(_rev("v9", contracts=("other.v1",)))
        store.plan(mismatched)
        res = prepare_dispatch(request_binding=mismatched, variables={"topic": "x"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.INCOMPATIBLE_CONTRACT)
        self.assertEqual(res.provider_calls, 0)


# ===========================================================================
# 5. Missing variables + unknown-policy fail-closed.
# ===========================================================================
class VariableValidation(unittest.TestCase):
    def test_missing_required_variable_rejected(self):
        v1 = _rev("v1")
        with self.assertRaises(PromptVariableError):
            render_messages(v1, {})                        # 'topic' missing

    def test_unknown_variable_rejected(self):
        v1 = _rev("v1")
        with self.assertRaises(PromptVariableError):
            render_messages(v1, {"topic": "x", "surprise": "y"})

    def test_unknown_enum_policy_value_fails_closed(self):
        v = _rev("v1", variables=(
            VariableSpec("topic", VariableType.STR, required=True),
            VariableSpec("tenant_policy", VariableType.ENUM, required=True,
                         allowed=frozenset({"strict", "standard"})),
        ))
        with self.assertRaises(PromptVariableError):
            render_messages(v, {"topic": "x", "tenant_policy": "permissive"})   # unknown -> fail closed

    def test_wrong_type_rejected(self):
        v = _rev("v1", variables=(VariableSpec("topic", VariableType.INT, required=True),))
        with self.assertRaises(PromptVariableError):
            render_messages(v, {"topic": "not-an-int"})

    def test_bool_not_accepted_as_int(self):
        v = _rev("v1", variables=(VariableSpec("n", VariableType.INT, required=True),
                                  VariableSpec("topic", VariableType.STR, required=True)))
        with self.assertRaises(PromptVariableError):
            render_messages(v, {"n": True, "topic": "x"})


# ===========================================================================
# 6 + 7 + 9. Compatibility: optional default OK; rename breaking; semantic weakening breaking.
# ===========================================================================
class Compatibility(unittest.TestCase):
    def test_optional_variable_with_default_is_backward_compatible(self):
        v1 = _rev("v1")
        v2 = _rev("v2", variables=(
            VariableSpec("topic", VariableType.STR, required=True),
            VariableSpec("tone", VariableType.STR, required=False, default="neutral"),
        ))
        self.assertTrue(is_backward_compatible(v1, v2))
        # And an old-style input (no 'tone') renders deterministically with the neutral default.
        msgs = render_messages(v2, {"topic": "x"})
        self.assertTrue(any("x" in m.content for m in msgs))

    def test_rename_without_alias_is_breaking(self):
        v1 = _rev("v1", variables=(VariableSpec("topic", VariableType.STR),
                                   VariableSpec("evidence", VariableType.STR)))
        v2 = _rev("v2", variables=(VariableSpec("topic", VariableType.STR),
                                   VariableSpec("sources", VariableType.STR)))
        reasons = backward_incompatibilities(v1, v2)
        self.assertFalse(is_backward_compatible(v1, v2))
        self.assertTrue(any("evidence" in r for r in reasons))

    def test_new_required_variable_without_default_is_breaking(self):
        v1 = _rev("v1")
        v2 = _rev("v2", variables=(VariableSpec("topic", VariableType.STR),
                                   VariableSpec("audience", VariableType.STR, required=True)))
        self.assertFalse(is_backward_compatible(v1, v2))

    def test_semantic_guarantee_weakening_is_breaking(self):
        strict = _rev("v1", guarantees=(CITATIONS_REQUIRED,))
        weak = _rev("v2", guarantees=())                   # citations now optional, same variables/schema
        reasons = backward_incompatibilities(strict, weak)
        self.assertFalse(is_backward_compatible(strict, weak))
        self.assertTrue(any(CITATIONS_REQUIRED in r for r in reasons))

    def test_enum_narrowing_is_breaking(self):
        v1 = _rev("v1", variables=(VariableSpec("topic", VariableType.STR),
                                   VariableSpec("lang", VariableType.ENUM,
                                                allowed=frozenset({"en", "zh", "fr"}))))
        v2 = _rev("v2", variables=(VariableSpec("topic", VariableType.STR),
                                   VariableSpec("lang", VariableType.ENUM,
                                                allowed=frozenset({"en", "zh"}))))
        self.assertFalse(is_backward_compatible(v1, v2))

    def test_removing_old_optional_variable_is_breaking(self):
        v1 = _rev("v1", variables=(
            VariableSpec("topic", VariableType.STR),
            VariableSpec("tone", VariableType.STR, required=False, default="neutral"),
        ))
        v2 = _rev("v2", variables=(VariableSpec("topic", VariableType.STR),))
        self.assertFalse(is_backward_compatible(v1, v2))

    def test_removing_supported_application_contract_is_breaking(self):
        v1 = _rev("v1", contracts=(CONTRACT, "research_claims.v2"))
        v2 = _rev("v2", contracts=("research_claims.v2",))
        reasons = backward_incompatibilities(v1, v2)
        self.assertFalse(is_backward_compatible(v1, v2))
        self.assertTrue(any(CONTRACT in reason for reason in reasons))


# ===========================================================================
# 8 + 11. Alias conflict rejection; migration without rewriting historical Attempts.
# ===========================================================================
class Migration(unittest.TestCase):
    def test_alias_applies_when_only_old_name_present(self):
        out = apply_migration({"topic": "x", "evidence": "e"}, {"evidence": "sources"})
        self.assertEqual(out, {"topic": "x", "sources": "e"})

    def test_conflicting_alias_and_replacement_is_rejected(self):
        with self.assertRaises(AliasConflictError):
            apply_migration({"evidence": "old", "sources": "new"}, {"evidence": "sources"})

    def test_agreeing_alias_and_replacement_collapses(self):
        out = apply_migration({"evidence": "same", "sources": "same"}, {"evidence": "sources"})
        self.assertEqual(out, {"sources": "same"})

    def test_migration_does_not_rewrite_a_planned_attempts_binding(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding_v1, _, store = _plan(reg, v1, attempt_id="A1")
        original = store.get_record("A1").binding
        # Publish a migrated v2 and default to it — the already-planned A1 binding is untouched.
        v2 = _rev("v2", variables=(VariableSpec("topic", VariableType.STR),
                                   VariableSpec("tone", VariableType.STR, required=False, default="neutral")))
        reg.publish(v2, make_default=True)
        self.assertEqual(store.get_record("A1").binding, original)     # history not rewritten
        self.assertEqual(store.get_record("A1").binding.revision, "v1")


# ===========================================================================
# 10. Renderer/parameter-policy binding + rendered hash.
# ===========================================================================
class BindingEvidence(unittest.TestCase):
    def test_binding_records_renderer_and_parameter_policy(self):
        v1 = _rev("v1", renderer="r7")
        binding, messages = plan_attempt_binding(
            attempt_id="A1", job_id="job-1", revision=v1, parameter_policy_id="params.creative",
            parameter_policy_revision="p3", application_contract=CONTRACT, variables={"topic": "x"})
        self.assertEqual(binding.renderer_version, "r7")
        self.assertEqual(binding.parameter_policy_id, "params.creative")
        self.assertEqual(binding.parameter_policy_revision, "p3")
        self.assertEqual(binding.rendered_message_hash, compute_rendered_hash(messages))
        self.assertTrue(binding.input_fingerprint.startswith("sha256:"))

    def test_rendered_hash_is_deterministic_and_input_sensitive(self):
        v1 = _rev("v1")
        h1 = compute_rendered_hash(render_messages(v1, {"topic": "a"}))
        h1b = compute_rendered_hash(render_messages(v1, {"topic": "a"}))
        h2 = compute_rendered_hash(render_messages(v1, {"topic": "b"}))
        self.assertEqual(h1, h1b)
        self.assertNotEqual(h1, h2)

    def test_renderer_version_mismatch_between_binding_and_revision_is_render_hash_or_binding_error(self):
        # Bind with renderer r1, but the registry's revision is republished conceptually as r2 under a NEW id.
        v1 = _rev("v1", renderer="r1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1")
        # Tamper: a different renderer revision v1b under same (id, revision) is immutable-rejected, proving
        # the binding's renderer_version cannot be silently swapped.
        with self.assertRaises(PromptBindingError):
            reg.publish(_rev("v1", renderer="r2"))
        # Gate still READY against the true bound r1 revision.
        res = prepare_dispatch(request_binding=binding, variables={"topic": "vaccines"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.READY)

    def test_input_fingerprint_mismatch_when_variables_differ_from_binding(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1", variables={"topic": "vaccines"})
        # Dispatch-time variables differ from what was bound -> re-render hash won't match -> zero calls.
        res = prepare_dispatch(request_binding=binding, variables={"topic": "DIFFERENT"},
                               store=store, registry=reg)
        self.assertIs(res.outcome, PromptGateOutcome.INPUT_FINGERPRINT_MISMATCH)
        self.assertEqual(res.provider_calls, 0)

    def test_render_hash_mismatch_is_rejected_after_input_matches(self):
        revision = _rev("v1")
        registry = _registry_with(revision)
        binding, _ = plan_attempt_binding(
            attempt_id="A1", job_id="job-1", revision=revision,
            parameter_policy_id=POLICY_ID, parameter_policy_revision=POLICY_REV,
            application_contract=CONTRACT, variables={"topic": "vaccines"},
        )
        tampered = replace(binding, rendered_message_hash="sha256:" + ("0" * 64))
        store = InMemoryAttemptPromptStore()
        store.plan(tampered)
        result = prepare_dispatch(
            request_binding=tampered, variables={"topic": "vaccines"},
            store=store, registry=registry,
        )
        self.assertIs(result.outcome, PromptGateOutcome.RENDER_HASH_MISMATCH)
        self.assertEqual(result.provider_calls, 0)
        self.assertIs(store.get_record("A1").state, AttemptPromptState.PLANNED)

    def test_input_fingerprint_catches_changed_variable_not_used_by_template(self):
        revision = _rev("v1", variables=(
            VariableSpec("topic", VariableType.STR),
            VariableSpec("audit_label", VariableType.STR),
        ))
        registry = _registry_with(revision)
        binding, _, store = _plan(
            registry, revision, attempt_id="A1",
            variables={"topic": "vaccines", "audit_label": "planned"},
        )
        result = prepare_dispatch(
            request_binding=binding,
            variables={"topic": "vaccines", "audit_label": "tampered"},
            store=store,
            registry=registry,
        )
        self.assertIs(result.outcome, PromptGateOutcome.INPUT_FINGERPRINT_MISMATCH)
        self.assertEqual(result.provider_calls, 0)
        self.assertIs(store.get_record("A1").state, AttemptPromptState.PLANNED)


# ===========================================================================
# 12. Timeout-unknown reconciliation + late-response safety.
# ===========================================================================
class Reconciliation(unittest.TestCase):
    def test_timeout_unknown_enters_reconciliation(self):
        self.assertIs(classify_timeout_unknown(), ReconciliationDecision.PENDING_RECONCILIATION)

    def test_late_response_interpreted_with_bound_revision(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1")
        reg.publish(_rev("v2"), make_default=True)         # default moved on
        decision, revision = interpret_late_response(
            authoritative=binding, response_binding=binding,
            attempt_state=AttemptPromptState.DISPATCHED, awaiting_reconciliation=True, registry=reg)
        self.assertIs(decision, ReconciliationDecision.INTERPRET_WITH_BOUND_REVISION)
        self.assertEqual(revision.revision, "v1")          # bound revision, NOT the current default v2

    def test_late_response_when_not_awaiting_is_refused(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1")
        decision, revision = interpret_late_response(
            authoritative=binding, response_binding=binding,
            attempt_state=AttemptPromptState.DISPATCHED, awaiting_reconciliation=False, registry=reg)
        self.assertIs(decision, ReconciliationDecision.REFUSED_NOT_AWAITING)
        self.assertIsNone(revision)

    def test_late_response_on_terminal_attempt_is_refused(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1")
        decision, _ = interpret_late_response(
            authoritative=binding, response_binding=binding,
            attempt_state=AttemptPromptState.BLOCKED_PROMPT_DISABLED, awaiting_reconciliation=True,
            registry=reg)
        self.assertIs(decision, ReconciliationDecision.REFUSED_TERMINAL)

    def test_late_response_binding_mismatch_is_refused(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        binding, _, store = _plan(reg, v1, attempt_id="A1")
        other, _ = plan_attempt_binding(
            attempt_id="A1", job_id="job-1", revision=_rev("v2"), parameter_policy_id=POLICY_ID,
            parameter_policy_revision=POLICY_REV, application_contract=CONTRACT, variables={"topic": "vaccines"})
        reg.publish(_rev("v2"))
        decision, _ = interpret_late_response(
            authoritative=binding, response_binding=other,
            attempt_state=AttemptPromptState.DISPATCHED, awaiting_reconciliation=True, registry=reg)
        self.assertIs(decision, ReconciliationDecision.REFUSED_BINDING_MISMATCH)


# ===========================================================================
# Fail-closed selection surfaces (new-attempt planning).
# ===========================================================================
class SelectionFailClosed(unittest.TestCase):
    def test_select_default_unknown_prompt_fails_closed(self):
        reg = PromptContractRegistry()
        with self.assertRaises(UnknownPromptError):
            reg.select_default_for_new_attempt("nope", CONTRACT)

    def test_select_default_disabled_fails_closed(self):
        v1 = _rev("v1")
        reg = _registry_with(v1)
        reg.lifecycle.disable("research_report", "v1")
        with self.assertRaises(PromptDisabledError):
            reg.select_default_for_new_attempt("research_report", CONTRACT)

    def test_select_default_incompatible_contract_fails_closed(self):
        v1 = _rev("v1", contracts=("other.v1",))
        reg = _registry_with(v1)
        with self.assertRaises(PromptBindingError):
            reg.select_default_for_new_attempt("research_report", CONTRACT)


if __name__ == "__main__":
    unittest.main()
