"""Day106 composition validators and append-only response delivery ledger."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import hmac
import threading
from typing import Iterator

from rag_authorized_retriever import (
    InMemoryRetrievalAuthorization,
    RetrievalAuthorizationUnavailable,
)
from rag_capstone_contracts import (
    AnswerReleaseRecord,
    CapstoneEvaluationDecision,
    CapstoneRequestBinding,
    CapstoneResult,
    Day101ExecutionReceipt,
    DispatchObservation,
    EndToEndExecutionManifest,
    RecoveryAndIncidentRecord,
    ReleaseCurrentnessSnapshot,
    ResponseIntent,
    ResponseIntentState,
    RetrievalAndContextReceipt,
    SourceToOccurrenceLineage,
)
from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_contracts import (
    ActivePointer,
    BuildSnapshot,
    GenerationArtifact,
    GenerationManifest,
    ReadView,
    ReadViewStatus,
)
from rag_reranker_contracts import Day101Response
from rag_retrieval_contracts import (
    RetrievalAuthorizationScope,
    RetrievalRequest,
    SelectedRetrievalBundle,
)
from rag_security_contracts import (
    AnswerCandidate,
    ContextAssemblyManifest,
    DisclosureEnvelope,
    ModelInvocationEnvelope,
    OutputReleaseDecision,
    ReleaseEvidence,
    RequestSecurityBinding,
    RetrievalBundle,
    manifest_entry_digest,
)


class CapstoneIdentityConflict(ValueError):
    """One identity was reused for different immutable content."""


class CapstoneGateRejected(RuntimeError):
    """A required application-owned capstone gate rejected the transition."""


class Day101ExecutionReceiptAuthority:
    """Application-owned issuer/verifier for immutable Day101 handoffs."""

    def __init__(self, authority_id: str, secret: bytes) -> None:
        if not authority_id or not secret:
            raise ValueError("receipt authority ID and secret are required")
        self.authority_id = authority_id
        self._secret = secret

    def issue(self, **fields: object) -> Day101ExecutionReceipt:
        receipt = Day101ExecutionReceipt(
            **fields,
            authority_id=self.authority_id,
            authority_mac="UNSIGNED",
        )
        return replace(receipt, authority_mac=self._mac(receipt.signing_digest))

    def verify(self, receipt: Day101ExecutionReceipt) -> bool:
        return (
            receipt.authority_id == self.authority_id
            and hmac.compare_digest(
                receipt.authority_mac,
                self._mac(receipt.signing_digest),
            )
        )

    def _mac(self, signing_digest: str) -> str:
        return hmac.new(
            self._secret,
            signing_digest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class InMemoryReleaseCurrentnessAuthority:
    """Deterministic current-state owner; not a production policy store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._current: dict[tuple[str, str], ReleaseCurrentnessSnapshot] = {}
        self._by_id: dict[str, ReleaseCurrentnessSnapshot] = {}

    def put(self, snapshot: ReleaseCurrentnessSnapshot) -> None:
        with self._lock:
            prior = self._by_id.get(snapshot.snapshot_id)
            if prior is not None and prior != snapshot:
                raise CapstoneIdentityConflict(
                    "RELEASE_CURRENTNESS_ID_REUSED_WITH_DIFFERENT_CONTENT"
                )
            key = (snapshot.tenant_id, snapshot.destination)
            current = self._current.get(key)
            if prior is not None:
                if current != prior:
                    raise CapstoneIdentityConflict(
                        "STALE_RELEASE_CURRENTNESS_REPLAY"
                    )
                return
            if current is not None and snapshot.revision != current.revision + 1:
                raise CapstoneIdentityConflict(
                    "RELEASE_CURRENTNESS_REVISION_CONFLICT"
                )
            if current is None and snapshot.revision != 1:
                raise CapstoneIdentityConflict(
                    "RELEASE_CURRENTNESS_INITIAL_REVISION_CONFLICT"
                )
            self._by_id[snapshot.snapshot_id] = snapshot
            self._current[key] = snapshot

    def read(
        self,
        *,
        tenant_id: str,
        destination: str,
    ) -> ReleaseCurrentnessSnapshot | None:
        with self._lock:
            return self._current.get((tenant_id, destination))

    @contextmanager
    def guarded_read(
        self,
        *,
        tenant_id: str,
        destination: str,
    ) -> Iterator[ReleaseCurrentnessSnapshot | None]:
        """Hold the deterministic currentness revision stable for one commit."""

        with self._lock:
            yield self._current.get((tenant_id, destination))

    def history(self) -> tuple[ReleaseCurrentnessSnapshot, ...]:
        with self._lock:
            return tuple(self._by_id[key] for key in sorted(self._by_id))


class CapstoneComposer:
    """Compose existing public artifacts without becoming their authority."""

    @staticmethod
    def bind_request(
        *,
        request_attempt_id: str,
        pointer: ActivePointer,
        read_view: ReadView,
        build_snapshot: BuildSnapshot,
        manifest: GenerationManifest,
        artifact: GenerationArtifact,
        security_binding: RequestSecurityBinding,
        selected_retrieval_bundle: SelectedRetrievalBundle,
        retrieval_authorization_scope: RetrievalAuthorizationScope,
        lineages: tuple[SourceToOccurrenceLineage, ...],
        created_at: str,
    ) -> CapstoneRequestBinding:
        if read_view.status is not ReadViewStatus.OPEN:
            raise CapstoneGateRejected("READ_VIEW_NOT_OPEN")
        if (
            pointer.generation_id != read_view.generation_id
            or pointer.revision != read_view.pointer_revision
        ):
            raise CapstoneIdentityConflict("READ_VIEW_POINTER_IDENTITY_CONFLICT")
        if artifact.generation_id != read_view.generation_id:
            raise CapstoneIdentityConflict("ARTIFACT_READ_VIEW_IDENTITY_CONFLICT")
        if artifact.build_snapshot_fingerprint != build_snapshot.fingerprint:
            raise CapstoneIdentityConflict("BUILD_SNAPSHOT_IDENTITY_CONFLICT")
        if artifact.manifest_digest != manifest.digest:
            raise CapstoneIdentityConflict("GENERATION_MANIFEST_DIGEST_CONFLICT")
        if not manifest.integrity_matches:
            raise CapstoneGateRejected("GENERATION_MANIFEST_INTEGRITY_NOT_PASSED")
        lineages_by_id = {item.occurrence_id: item for item in lineages}
        if len(lineages_by_id) != len(lineages):
            raise CapstoneIdentityConflict("DUPLICATE_OCCURRENCE_LINEAGE")
        if set(manifest.actual.occurrence_ids) != set(lineages_by_id):
            raise CapstoneIdentityConflict("MANIFEST_LINEAGE_SET_CONFLICT")
        ordered_lineages = tuple(
            lineages_by_id[item] for item in sorted(lineages_by_id)
        )
        if manifest.actual.content_digest != stable_hash(
            tuple((item.occurrence_id, item.content_digest) for item in ordered_lineages)
        ):
            raise CapstoneIdentityConflict("MANIFEST_LINEAGE_CONTENT_CONFLICT")
        if manifest.actual.metadata_digest != stable_hash(
            tuple((item.occurrence_id, item.metadata_digest) for item in ordered_lineages)
        ):
            raise CapstoneIdentityConflict("MANIFEST_LINEAGE_METADATA_CONFLICT")
        if manifest.actual.provenance_digest != stable_hash(
            tuple(
                (item.occurrence_id, stable_hash(item.provenance_revision))
                for item in ordered_lineages
            )
        ):
            raise CapstoneIdentityConflict("MANIFEST_LINEAGE_PROVENANCE_CONFLICT")

        if security_binding.request_id != request_attempt_id:
            raise CapstoneIdentityConflict("SECURITY_BINDING_ATTEMPT_CONFLICT")
        if security_binding.generation_id != artifact.generation_id:
            raise CapstoneIdentityConflict("SECURITY_BINDING_GENERATION_CONFLICT")
        if security_binding.generation_artifact_digest != artifact.fingerprint:
            raise CapstoneIdentityConflict("SECURITY_BINDING_ARTIFACT_CONFLICT")
        if (
            security_binding.build_snapshot_fingerprint
            != build_snapshot.fingerprint
        ):
            raise CapstoneIdentityConflict("SECURITY_BINDING_SNAPSHOT_CONFLICT")
        if security_binding.validation_record_digest != artifact.validation_record_digest:
            raise CapstoneIdentityConflict("SECURITY_BINDING_VALIDATION_CONFLICT")
        if (
            security_binding.day103_evaluation_report_checksum
            != artifact.evaluation_report_digest
        ):
            raise CapstoneIdentityConflict("SECURITY_BINDING_EVALUATION_CONFLICT")
        if security_binding.pointer_revision != pointer.revision:
            raise CapstoneIdentityConflict("SECURITY_BINDING_POINTER_CONFLICT")
        if security_binding.active_pointer_digest != stable_hash(asdict(pointer)):
            raise CapstoneIdentityConflict("ACTIVE_POINTER_DIGEST_CONFLICT")
        if (
            security_binding.read_view_id != read_view.view_id
            or security_binding.read_view_fence != read_view.fencing_token
            or security_binding.read_view_owner_id != read_view.owner_id
        ):
            raise CapstoneIdentityConflict("SECURITY_BINDING_READ_VIEW_CONFLICT")
        if security_binding.read_view_validation_digest != stable_hash(
            asdict(read_view)
        ):
            raise CapstoneIdentityConflict("READ_VIEW_VALIDATION_DIGEST_CONFLICT")
        if security_binding.authorization_revision != (
            build_snapshot.authorization_snapshot.identity
        ):
            raise CapstoneIdentityConflict("AUTHORIZATION_SNAPSHOT_CONFLICT")
        if set(dict(security_binding.manifest_entries)) != set(
            manifest.actual.occurrence_ids
        ):
            raise CapstoneIdentityConflict("SECURITY_MANIFEST_ENTRY_SET_CONFLICT")
        expected_security_entries = tuple(
            (
                item.occurrence_id,
                manifest_entry_digest(
                    item.occurrence_id,
                    item.source_artifact_id,
                    item.source_version,
                    item.tenant_id,
                    item.resource_id,
                    item.content_digest,
                    item.metadata_digest,
                    item.metadata_version,
                    item.provenance_revision,
                ),
            )
            for item in ordered_lineages
        )
        if security_binding.manifest_entries != expected_security_entries:
            raise CapstoneIdentityConflict("SECURITY_MANIFEST_LINEAGE_CONFLICT")

        authorization_revision_digest = stable_hash(
            asdict(retrieval_authorization_scope.revisions)
        )
        if build_snapshot.authorization_snapshot.digest != stable_hash(
            (
                build_snapshot.authorization_snapshot.identity,
                authorization_revision_digest,
            )
        ):
            raise CapstoneIdentityConflict("AUTHORIZATION_REVISION_DIGEST_CONFLICT")
        if (
            retrieval_authorization_scope.tenant_id != security_binding.tenant_id
            or retrieval_authorization_scope.principal_subject
            != security_binding.principal_id
            or retrieval_authorization_scope.purpose != security_binding.purpose
        ):
            raise CapstoneIdentityConflict("RETRIEVAL_AUTHORIZATION_SCOPE_CONFLICT")
        if not set(retrieval_authorization_scope.allowed_occurrence_ids).issubset(
            manifest.actual.occurrence_ids
        ):
            raise CapstoneIdentityConflict("AUTHORIZATION_MANIFEST_SCOPE_CONFLICT")
        if (
            selected_retrieval_bundle.generation_id != read_view.generation_id
            or selected_retrieval_bundle.revision != read_view.pointer_revision
            or selected_retrieval_bundle.tenant_id != security_binding.tenant_id
        ):
            raise CapstoneIdentityConflict("SELECTED_RETRIEVAL_BUNDLE_CONFLICT")
        if selected_retrieval_bundle.generation_contract_fingerprint != (
            artifact.fingerprint
        ):
            raise CapstoneIdentityConflict("RETRIEVAL_GENERATION_ARTIFACT_CONFLICT")
        if {item.chunk_set_id for item in lineages} != {
            selected_retrieval_bundle.chunk_set_id
        }:
            raise CapstoneIdentityConflict("RETRIEVAL_CHUNK_SET_CONFLICT")
        if {item.embedding_set_id for item in lineages} != {
            selected_retrieval_bundle.embedding_set_id
        }:
            raise CapstoneIdentityConflict("RETRIEVAL_EMBEDDING_SET_CONFLICT")
        if {item.embedding_contract_fingerprint for item in lineages} != {
            selected_retrieval_bundle.embedding_contract_fingerprint
        }:
            raise CapstoneIdentityConflict(
                "RETRIEVAL_EMBEDDING_CONTRACT_CONFLICT"
            )
        if (
            build_snapshot.embedding_contract.identity
            != selected_retrieval_bundle.embedding_contract_fingerprint
            or build_snapshot.embedding_contract.digest
            != stable_hash(
                selected_retrieval_bundle.embedding_contract_fingerprint
            )
        ):
            raise CapstoneIdentityConflict(
                "BUILD_SNAPSHOT_EMBEDDING_CONTRACT_CONFLICT"
            )

        return CapstoneRequestBinding(
            request_attempt_id=request_attempt_id,
            request_id=security_binding.request_id,
            principal_id=security_binding.principal_id,
            tenant_id=security_binding.tenant_id,
            action=retrieval_authorization_scope.action,
            purpose=security_binding.purpose,
            audience=security_binding.audience,
            pointer_name=pointer.pointer_name,
            generation_id=artifact.generation_id,
            generation_artifact_digest=artifact.fingerprint,
            generation_manifest_digest=manifest.digest,
            build_snapshot_fingerprint=build_snapshot.fingerprint,
            pointer_revision=pointer.revision,
            read_view_id=read_view.view_id,
            read_view_fence=read_view.fencing_token,
            read_view_digest=stable_hash(asdict(read_view)),
            source_snapshot_id=build_snapshot.source_snapshot.identity,
            authorization_snapshot_id=(
                build_snapshot.authorization_snapshot.identity
            ),
            deletion_snapshot_id=build_snapshot.deletion_snapshot.identity,
            policy_fingerprint=security_binding.policy.fingerprint,
            security_binding_fingerprint=security_binding.fingerprint,
            retrieval_authorization_revision_digest=(
                authorization_revision_digest
            ),
            retrieval_authorization_scope_fingerprint=(
                retrieval_authorization_scope.fingerprint
            ),
            selected_retrieval_bundle_id=selected_retrieval_bundle.bundle_id,
            selected_retrieval_bundle_revision=selected_retrieval_bundle.revision,
            selected_retrieval_bundle_fingerprint=(
                selected_retrieval_bundle.fingerprint
            ),
            created_at=created_at,
        )

    @staticmethod
    def record_retrieval_and_context(
        *,
        receipt_id: str,
        binding: CapstoneRequestBinding,
        retrieval_request: RetrievalRequest,
        day101_response: Day101Response,
        day101_execution_receipt: Day101ExecutionReceipt,
        day101_receipt_authority: Day101ExecutionReceiptAuthority,
        retrieval_bundle: RetrievalBundle,
        context_manifest: ContextAssemblyManifest,
        current_authorization_scope: RetrievalAuthorizationScope,
        created_at: str,
    ) -> RetrievalAndContextReceipt:
        handoff_digest = day101_response.handoff_digest
        if handoff_digest is None:
            raise CapstoneGateRejected("DAY101_HANDOFF_NOT_RELEASABLE")
        if not day101_receipt_authority.verify(day101_execution_receipt):
            raise CapstoneGateRejected(
                "DAY101_EXECUTION_RECEIPT_AUTHORITY_CONFLICT"
            )
        if day101_response.authorization_scope_fingerprint != (
            binding.retrieval_authorization_scope_fingerprint
        ):
            raise CapstoneIdentityConflict(
                "DAY101_AUTHORIZATION_SCOPE_CONFLICT"
            )
        response_occurrence_ids = tuple(
            item.identity.occurrence_id for item in day101_response.hits
        )
        response_content_digests = tuple(
            item.identity.content_hash for item in day101_response.hits
        )
        if (
            day101_execution_receipt.request_id != retrieval_request.request_id
            or day101_execution_receipt.operation_id
            != retrieval_request.operation_id
            or day101_execution_receipt.query_hash != retrieval_request.query_hash
            or day101_execution_receipt.selected_bundle_id
            != binding.selected_retrieval_bundle_id
            or day101_execution_receipt.selected_bundle_fingerprint
            != binding.selected_retrieval_bundle_fingerprint
            or day101_execution_receipt.selected_generation_id
            != binding.generation_id
            or day101_execution_receipt.selected_pointer_revision
            != binding.selected_retrieval_bundle_revision
            or day101_execution_receipt.generation_artifact_digest
            != binding.generation_artifact_digest
            or day101_execution_receipt.authorization_scope_fingerprint
            != binding.retrieval_authorization_scope_fingerprint
            or day101_execution_receipt.original_query_digest
            != day101_response.original_query_digest
            or day101_execution_receipt.day101_handoff_digest != handoff_digest
            or day101_execution_receipt.candidate_pool_digest
            != day101_response.candidate_pool_digest
            or day101_execution_receipt.exact_occurrence_ids
            != response_occurrence_ids
            or day101_execution_receipt.exact_content_digests
            != response_content_digests
        ):
            raise CapstoneIdentityConflict("DAY101_EXECUTION_RECEIPT_CONFLICT")
        if (
            retrieval_request.request_id != binding.request_attempt_id
            or retrieval_request.tenant_id != binding.tenant_id
            or retrieval_request.principal_subject != binding.principal_id
            or retrieval_request.action != binding.action
            or retrieval_request.purpose != binding.purpose
        ):
            raise CapstoneIdentityConflict("RETRIEVAL_REQUEST_BINDING_CONFLICT")
        if retrieval_request.client_generation_id not in {
            None,
            binding.generation_id,
        }:
            raise CapstoneIdentityConflict("CLIENT_GENERATION_CONFLICT")
        if (
            current_authorization_scope.tenant_id != binding.tenant_id
            or current_authorization_scope.principal_subject
            != binding.principal_id
            or current_authorization_scope.action != binding.action
            or current_authorization_scope.purpose != binding.purpose
        ):
            raise CapstoneIdentityConflict(
                "PROMPT_AUTHORIZATION_SCOPE_CONFLICT"
            )
        if retrieval_bundle.request_binding_fingerprint != (
            binding.security_binding_fingerprint
        ):
            raise CapstoneIdentityConflict("RETRIEVAL_BINDING_CONFLICT")
        if context_manifest.request_binding_fingerprint != (
            binding.security_binding_fingerprint
        ):
            raise CapstoneIdentityConflict("CONTEXT_BINDING_CONFLICT")
        if context_manifest.retrieval_bundle_digest != retrieval_bundle.digest:
            raise CapstoneIdentityConflict("CONTEXT_RETRIEVAL_BUNDLE_CONFLICT")
        if context_manifest.bundle_security_decision_digest != (
            retrieval_bundle.bundle_security_decision_digest
        ):
            raise CapstoneIdentityConflict("CONTEXT_SECURITY_DECISION_CONFLICT")

        day101_occurrence_ids = response_occurrence_ids
        if not set(retrieval_bundle.occurrence_ids).issubset(
            day101_occurrence_ids
        ):
            raise CapstoneIdentityConflict("RETRIEVAL_BUNDLE_NOT_FROM_DAY101")
        day101_content_by_id = {
            item.identity.occurrence_id: item.identity.content_hash
            for item in day101_response.hits
        }
        bundle_content_by_id = dict(
            zip(
                retrieval_bundle.occurrence_ids,
                retrieval_bundle.content_digests,
                strict=True,
            )
        )
        if any(
            day101_content_by_id.get(occurrence_id) != content_digest
            for occurrence_id, content_digest in bundle_content_by_id.items()
        ):
            raise CapstoneIdentityConflict("DAY101_CONTENT_DIGEST_CONFLICT")
        context_content_by_id = dict(
            zip(
                context_manifest.included_occurrence_ids,
                context_manifest.included_content_digests,
                strict=True,
            )
        )
        if any(
            bundle_content_by_id.get(occurrence_id) != content_digest
            for occurrence_id, content_digest in context_content_by_id.items()
        ):
            raise CapstoneIdentityConflict("CONTEXT_CONTENT_DIGEST_CONFLICT")
        authorized = set(current_authorization_scope.allowed_occurrence_ids)
        unauthorized_prompt_count = len(
            set(context_manifest.included_occurrence_ids) - authorized
        )
        if unauthorized_prompt_count:
            raise CapstoneGateRejected(
                "UNAUTHORIZED_OCCURRENCE_ENTERED_CONTEXT"
            )
        return RetrievalAndContextReceipt(
            receipt_id=receipt_id,
            request_binding_digest=binding.digest,
            retrieval_operation_id=retrieval_request.operation_id,
            retrieval_request_id=retrieval_request.request_id,
            day101_execution_receipt_digest=(
                day101_execution_receipt.digest
            ),
            day101_handoff_digest=handoff_digest,
            prompt_authorization_scope_fingerprint=(
                current_authorization_scope.fingerprint
            ),
            prompt_authorization_revision_digest=stable_hash(
                asdict(current_authorization_scope.revisions)
            ),
            retrieval_bundle_id=retrieval_bundle.bundle_id,
            retrieval_bundle_digest=retrieval_bundle.digest,
            retrieval_security_decision_digest=(
                retrieval_bundle.retrieval_decision_digest
            ),
            bundle_security_decision_digest=(
                retrieval_bundle.bundle_security_decision_digest
            ),
            exact_occurrence_ids=retrieval_bundle.occurrence_ids,
            exact_content_digests=retrieval_bundle.content_digests,
            context_manifest_id=context_manifest.manifest_id,
            context_manifest_digest=context_manifest.digest,
            context_occurrence_ids=context_manifest.included_occurrence_ids,
            assembled_context_digest=context_manifest.assembled_context_digest,
            unauthorized_prompt_count=unauthorized_prompt_count,
            created_at=created_at,
        )

    @staticmethod
    def record_answer_release(
        *,
        record_id: str,
        response_intent_id: str,
        binding: CapstoneRequestBinding,
        receipt: RetrievalAndContextReceipt,
        disclosure: DisclosureEnvelope,
        invocation: ModelInvocationEnvelope,
        candidate: AnswerCandidate,
        release_evidence: ReleaseEvidence,
        decision: OutputReleaseDecision,
        current_authorization_scope: RetrievalAuthorizationScope,
        release_currentness_snapshot: ReleaseCurrentnessSnapshot,
        dispatch_idempotency_key: str,
        created_at: str,
    ) -> AnswerReleaseRecord:
        if receipt.request_binding_digest != binding.digest:
            raise CapstoneIdentityConflict("RECEIPT_REQUEST_BINDING_CONFLICT")
        if invocation.request_binding_fingerprint != (
            binding.security_binding_fingerprint
        ):
            raise CapstoneIdentityConflict("INVOCATION_REQUEST_BINDING_CONFLICT")
        if invocation.context_manifest_digest != receipt.context_manifest_digest:
            raise CapstoneIdentityConflict("INVOCATION_CONTEXT_CONFLICT")
        if candidate.invocation_envelope_digest != invocation.digest:
            raise CapstoneIdentityConflict("CANDIDATE_INVOCATION_CONFLICT")
        if release_evidence.candidate_digest != candidate.digest:
            raise CapstoneIdentityConflict("RELEASE_EVIDENCE_CANDIDATE_CONFLICT")
        if (
            disclosure.request_binding_fingerprint
            != binding.security_binding_fingerprint
            or disclosure.purpose != binding.purpose
            or disclosure.audience != binding.audience
        ):
            raise CapstoneIdentityConflict("DISCLOSURE_REQUEST_BINDING_CONFLICT")
        if (
            decision.request_binding_fingerprint
            != binding.security_binding_fingerprint
            or decision.candidate_digest != candidate.digest
            or decision.release_evidence_digest != release_evidence.digest
            or decision.disclosure_envelope_digest != disclosure.digest
            or invocation.disclosure_envelope_digest != disclosure.digest
        ):
            raise CapstoneIdentityConflict("OUTPUT_DECISION_IDENTITY_CONFLICT")

        current_authorization_revision_digest = stable_hash(
            asdict(current_authorization_scope.revisions)
        )
        if (
            current_authorization_scope.tenant_id != binding.tenant_id
            or current_authorization_scope.principal_subject
            != binding.principal_id
            or current_authorization_scope.action != binding.action
            or current_authorization_scope.purpose != binding.purpose
            or release_evidence.current_authorization_revision
            != current_authorization_revision_digest
        ):
            raise CapstoneIdentityConflict(
                "RELEASE_AUTHORIZATION_SCOPE_CONFLICT"
            )
        if (
            release_currentness_snapshot.tenant_id != binding.tenant_id
            or release_currentness_snapshot.destination != disclosure.destination
            or release_evidence.current_provenance_revision
            != release_currentness_snapshot.provenance_revision
            or release_evidence.current_tombstone_revision
            != release_currentness_snapshot.tombstone_revision
            or release_evidence.current_content_security_snapshot_digest
            != release_currentness_snapshot.content_security_snapshot_digest
            or release_evidence.current_security_policy_fingerprint
            != release_currentness_snapshot.security_policy_fingerprint
            or release_evidence.dlp_result.value
            != release_currentness_snapshot.dlp_result
            or release_evidence.metadata_stripping_result.value
            != release_currentness_snapshot.metadata_stripping_result
            or release_evidence.destination_result.value
            != release_currentness_snapshot.destination_result
        ):
            raise CapstoneIdentityConflict(
                "RELEASE_CURRENTNESS_SNAPSHOT_CONFLICT"
            )
        expected_authorized_occurrences = tuple(
            sorted(
                set(current_authorization_scope.allowed_occurrence_ids)
                .intersection(
                    release_currentness_snapshot.source_eligible_occurrence_ids
                )
                .difference(
                    release_currentness_snapshot.quarantined_occurrence_ids
                )
            )
        )
        if release_evidence.currently_authorized_occurrence_ids != (
            expected_authorized_occurrences
        ):
            raise CapstoneIdentityConflict(
                "RELEASE_AUTHORIZED_OCCURRENCE_SET_CONFLICT"
            )
        required_currentness_evidence = {
            current_authorization_revision_digest,
            release_currentness_snapshot.digest,
            *release_currentness_snapshot.evidence_digests,
        }
        if not required_currentness_evidence.issubset(
            release_evidence.evidence_digests
        ):
            raise CapstoneIdentityConflict(
                "RELEASE_CURRENTNESS_EVIDENCE_BINDING_CONFLICT"
            )

        releases = decision.result.value == "PASS" and (
            decision.disposition.value == "RELEASE"
        )
        if releases and disclosure.authorization_revision != (
            release_evidence.current_authorization_revision
        ):
            raise CapstoneIdentityConflict(
                "DISCLOSURE_AUTHORIZATION_REVISION_CONFLICT"
            )
        return AnswerReleaseRecord(
            record_id=record_id,
            request_binding_digest=binding.digest,
            retrieval_context_receipt_digest=receipt.digest,
            model_invocation_id=invocation.envelope_id,
            model_invocation_digest=invocation.digest,
            answer_candidate_id=candidate.candidate_id,
            answer_candidate_digest=candidate.digest,
            release_evidence_id=release_evidence.evidence_id,
            release_evidence_digest=release_evidence.digest,
            output_release_decision_id=decision.decision_id,
            output_release_decision_digest=decision.digest,
            disclosure_envelope_digest=disclosure.digest,
            tenant_id=binding.tenant_id,
            principal_id=binding.principal_id,
            action=binding.action,
            purpose=binding.purpose,
            current_authorization_scope_fingerprint=(
                current_authorization_scope.fingerprint
            ),
            current_authorization_revision_digest=(
                current_authorization_revision_digest
            ),
            release_currentness_snapshot_id=(
                release_currentness_snapshot.snapshot_id
            ),
            release_currentness_snapshot_digest=(
                release_currentness_snapshot.digest
            ),
            release_currentness_revision=(
                release_currentness_snapshot.revision
            ),
            released_occurrence_ids=(
                decision.released_citation_occurrence_ids
            ),
            authorized_destination=(disclosure.destination if releases else None),
            dispatch_idempotency_key=(
                dispatch_idempotency_key if releases else None
            ),
            result=decision.result.value,
            disposition=decision.disposition.value,
            safe_reason_codes=decision.reason_codes,
            response_intent_id=response_intent_id if releases else None,
            response_dispatch_state=(
                ResponseIntentState.PENDING
                if releases
                else ResponseIntentState.NOT_ATTEMPTED
            ),
            created_at=created_at,
        )

    @staticmethod
    def evaluate(
        *,
        decision_id: str,
        execution_id: str,
        normal_quality: CapstoneResult,
        security_defense: CapstoneResult,
        failure_recovery: CapstoneResult,
        evidence_replay: CapstoneResult,
        external_real_boundary: CapstoneResult,
        hard_gates: tuple[tuple[str, CapstoneResult], ...],
        evaluated_artifact_digests: tuple[str, ...],
        evidence_level: str,
        production_readiness: str,
        safe_reason_codes: tuple[str, ...],
        observed_at: str,
    ) -> CapstoneEvaluationDecision:
        required = (
            normal_quality,
            security_defense,
            failure_recovery,
            *(result for _, result in hard_gates),
        )
        overall = CapstoneEvaluationDecision._aggregate(required)
        return CapstoneEvaluationDecision(
            decision_id=decision_id,
            execution_id=execution_id,
            normal_quality=normal_quality,
            security_defense=security_defense,
            failure_recovery=failure_recovery,
            evidence_replay=evidence_replay,
            external_real_boundary=external_real_boundary,
            hard_gates=hard_gates,
            evaluated_artifact_digests=evaluated_artifact_digests,
            overall_hard_gate=overall,
            evidence_level=evidence_level,
            production_readiness=production_readiness,
            safe_reason_codes=safe_reason_codes,
            observed_at=observed_at,
        )


class InMemoryResponseLedger:
    """Deterministic durable-boundary model; not distributed durability proof."""

    def __init__(
        self,
        *,
        authorization_authority: InMemoryRetrievalAuthorization | None = None,
        release_currentness_authority: (
            InMemoryReleaseCurrentnessAuthority | None
        ) = None,
    ) -> None:
        self._lock = threading.RLock()
        self._authorization_authority = authorization_authority
        self._release_currentness_authority = release_currentness_authority
        self._release_records: dict[str, AnswerReleaseRecord] = {}
        self._intents: dict[str, ResponseIntent] = {}
        self._intent_by_idempotency_key: dict[str, str] = {}
        self._release_record_by_intent: dict[str, str] = {}
        self._record_by_decision_id: dict[str, str] = {}
        self._record_by_decision_digest: dict[str, str] = {}
        self._history: dict[str, list[RecoveryAndIncidentRecord]] = {}
        self._recovery_record_owner: dict[str, str] = {}

    @contextmanager
    def _guard_release_currentness(
        self,
        release_record: AnswerReleaseRecord,
        *,
        phase: str,
    ) -> Iterator[None]:
        if (
            self._authorization_authority is None
            or self._release_currentness_authority is None
        ):
            raise CapstoneGateRejected("CURRENTNESS_AUTHORITIES_NOT_BOUND")
        try:
            authorization_guard = self._authorization_authority.guarded_read(
                tenant_id=release_record.tenant_id,
                principal_subject=release_record.principal_id,
                action=release_record.action,
                purpose=release_record.purpose,
            )
        except RetrievalAuthorizationUnavailable as exc:
            raise CapstoneGateRejected(
                "CURRENT_AUTHORIZATION_UNAVAILABLE"
            ) from exc
        try:
            with authorization_guard as scope:
                with self._release_currentness_authority.guarded_read(
                    tenant_id=release_record.tenant_id,
                    destination=release_record.authorized_destination or "",
                ) as currentness:
                    if scope is None or currentness is None:
                        raise CapstoneGateRejected(
                            "CURRENT_RELEASE_FACTS_NOT_FOUND"
                        )
                    matches = (
                        scope.fingerprint
                        == release_record.current_authorization_scope_fingerprint
                        and stable_hash(asdict(scope.revisions))
                        == release_record.current_authorization_revision_digest
                        and currentness.snapshot_id
                        == release_record.release_currentness_snapshot_id
                        and currentness.revision
                        == release_record.release_currentness_revision
                        and currentness.digest
                        == release_record.release_currentness_snapshot_digest
                    )
                    if not matches:
                        raise CapstoneGateRejected(
                            f"RELEASE_CURRENTNESS_CHANGED_BEFORE_{phase}"
                        )
                    currently_eligible = (
                        set(scope.allowed_occurrence_ids)
                        .intersection(currentness.source_eligible_occurrence_ids)
                        .difference(currentness.quarantined_occurrence_ids)
                    )
                    if (
                        currentness.dlp_result != "PASS"
                        or currentness.metadata_stripping_result != "PASS"
                        or currentness.destination_result != "PASS"
                        or not set(
                            release_record.released_occurrence_ids
                        ).issubset(currently_eligible)
                    ):
                        raise CapstoneGateRejected(
                            f"RELEASE_GATE_NOT_PASSED_BEFORE_{phase}"
                        )
                    yield
        except RetrievalAuthorizationUnavailable as exc:
            raise CapstoneGateRejected(
                "CURRENT_AUTHORIZATION_UNAVAILABLE"
            ) from exc

    def _assert_decision_ownership_available(
        self,
        release_record: AnswerReleaseRecord,
    ) -> None:
        for index, identity, reason in (
            (
                self._record_by_decision_id,
                release_record.output_release_decision_id,
                "OUTPUT_RELEASE_DECISION_ID_ALREADY_OWNED",
            ),
            (
                self._record_by_decision_digest,
                release_record.output_release_decision_digest,
                "OUTPUT_RELEASE_DECISION_ALREADY_OWNED",
            ),
        ):
            owner = index.get(identity)
            if owner is not None and owner != release_record.record_id:
                raise CapstoneIdentityConflict(reason)

    def _claim_decision_ownership(
        self,
        release_record: AnswerReleaseRecord,
    ) -> None:
        self._assert_decision_ownership_available(release_record)
        self._record_by_decision_id[
            release_record.output_release_decision_id
        ] = release_record.record_id
        self._record_by_decision_digest[
            release_record.output_release_decision_digest
        ] = release_record.record_id

    def commit_decision_and_intent(
        self,
        *,
        release_record: AnswerReleaseRecord,
        destination: str,
        dispatch_idempotency_key: str,
    ) -> ResponseIntent | None:
        """Atomically persist a release decision and, only for RELEASE, intent."""

        with self._lock:
            releases = (
                release_record.result == "PASS"
                and release_record.disposition == "RELEASE"
            )
            if releases:
                if (
                    destination != release_record.authorized_destination
                    or dispatch_idempotency_key
                    != release_record.dispatch_idempotency_key
                ):
                    raise CapstoneIdentityConflict(
                        "DISPATCH_AUTHORITY_BINDING_CONFLICT"
                    )
            elif destination or dispatch_idempotency_key:
                raise CapstoneGateRejected(
                    "BLOCKED_DECISION_CANNOT_CREATE_DISPATCH_INTENT"
                )
            prior = self._release_records.get(release_record.record_id)
            if prior is not None:
                if prior != release_record:
                    raise CapstoneIdentityConflict(
                        "RELEASE_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT"
                    )
                if prior.response_intent_id is None:
                    return None
                return self._intents[prior.response_intent_id]

            if not releases:
                self._claim_decision_ownership(release_record)
                self._release_records[release_record.record_id] = release_record
                return None

            with self._guard_release_currentness(
                release_record,
                phase="INTENT_COMMIT",
            ):
                self._assert_decision_ownership_available(release_record)

                intent_id = release_record.response_intent_id
                if intent_id is None:
                    raise CapstoneIdentityConflict("RELEASE_RECORD_MISSING_INTENT_ID")
                authorized_destination = release_record.authorized_destination
                authorized_key = release_record.dispatch_idempotency_key
                if authorized_destination is None or authorized_key is None:
                    raise CapstoneIdentityConflict(
                        "RELEASE_RECORD_DISPATCH_BINDING_MISSING"
                    )
                if intent_id in self._intents:
                    raise CapstoneIdentityConflict(
                        "RESPONSE_INTENT_ID_ALREADY_EXISTS"
                    )
                existing_intent = self._intent_by_idempotency_key.get(
                    authorized_key
                )
                if existing_intent is not None:
                    raise CapstoneIdentityConflict(
                        "DISPATCH_IDEMPOTENCY_KEY_ALREADY_BOUND"
                    )
                self._claim_decision_ownership(release_record)
                intent = ResponseIntent(
                    intent_id=intent_id,
                    request_binding_digest=release_record.request_binding_digest,
                    output_release_decision_digest=(
                        release_record.output_release_decision_digest
                    ),
                    candidate_digest=release_record.answer_candidate_digest,
                    destination=authorized_destination,
                    dispatch_idempotency_key=authorized_key,
                    state=ResponseIntentState.PENDING,
                    revision=1,
                    created_at=release_record.created_at,
                )
                self._release_records[release_record.record_id] = release_record
                self._intents[intent_id] = intent
                self._intent_by_idempotency_key[authorized_key] = intent_id
                self._release_record_by_intent[
                    intent_id
                ] = release_record.record_id
                self._history[intent_id] = []
                return intent

    def append_observation(
        self,
        record: RecoveryAndIncidentRecord,
    ) -> ResponseIntent:
        """Append one exact observation and advance the durable intent state."""

        with self._lock:
            intent = self._intents.get(record.response_intent_id)
            if intent is None:
                raise CapstoneIdentityConflict("RESPONSE_INTENT_NOT_FOUND")
            if record.dispatch_idempotency_key != intent.dispatch_idempotency_key:
                raise CapstoneIdentityConflict("DISPATCH_IDEMPOTENCY_KEY_CONFLICT")
            owner = self._recovery_record_owner.get(record.record_id)
            if owner is not None and owner != record.response_intent_id:
                raise CapstoneIdentityConflict(
                    "RECOVERY_RECORD_ID_ALREADY_OWNED"
                )
            history = self._history[record.response_intent_id]
            for prior in history:
                if prior.record_id == record.record_id:
                    if prior != record:
                        raise CapstoneIdentityConflict(
                            "RECOVERY_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT"
                        )
                    return intent
            expected_previous = history[-1].record_id if history else None
            if record.previous_record_id != expected_previous:
                raise CapstoneIdentityConflict("APPEND_ONLY_HISTORY_FORK")

            if record.observation is DispatchObservation.SEND_STARTED:
                owner_id = self._release_record_by_intent.get(intent.intent_id)
                if owner_id is None:
                    raise CapstoneIdentityConflict(
                        "RESPONSE_INTENT_RELEASE_OWNER_NOT_FOUND"
                    )
                with self._guard_release_currentness(
                    self._release_records[owner_id],
                    phase="SEND",
                ):
                    self._validate_history_step(
                        intent,
                        record,
                        previous_record=(history[-1] if history else None),
                    )
                    updated = self._transition(intent, record)
                    history.append(record)
                    self._recovery_record_owner[
                        record.record_id
                    ] = intent.intent_id
                    self._intents[intent.intent_id] = updated
                    return updated

            self._validate_history_step(
                intent,
                record,
                previous_record=(history[-1] if history else None),
            )
            updated = self._transition(intent, record)
            history.append(record)
            self._recovery_record_owner[record.record_id] = intent.intent_id
            self._intents[intent.intent_id] = updated
            return updated

    @staticmethod
    def _validate_history_step(
        intent: ResponseIntent,
        record: RecoveryAndIncidentRecord,
        *,
        previous_record: RecoveryAndIncidentRecord | None,
    ) -> None:
        """Require a durable same-attempt send before a transport outcome."""

        if (
            record.observation is DispatchObservation.SEND_STARTED
            and intent.state is ResponseIntentState.PENDING
            and previous_record is not None
            and previous_record.observation is DispatchObservation.SEND_STARTED
        ):
            raise CapstoneGateRejected("SEND_ALREADY_STARTED")
        if (
            record.observation
            in {DispatchObservation.UNKNOWN, DispatchObservation.ACCEPTED}
            and intent.state is ResponseIntentState.PENDING
            and (
                previous_record is None
                or previous_record.observation
                is not DispatchObservation.SEND_STARTED
                or previous_record.transport_attempt_id
                != record.transport_attempt_id
            )
        ):
            raise CapstoneGateRejected(
                "DISPATCH_OUTCOME_REQUIRES_MATCHING_SEND_STARTED"
            )

    @staticmethod
    def _transition(
        intent: ResponseIntent,
        record: RecoveryAndIncidentRecord,
    ) -> ResponseIntent:
        observation = record.observation
        if observation is DispatchObservation.SEND_STARTED:
            if intent.state is not ResponseIntentState.PENDING:
                raise CapstoneGateRejected("SEND_REQUIRES_PENDING_INTENT")
            return replace(intent, revision=intent.revision + 1)
        if observation is DispatchObservation.UNKNOWN:
            if intent.state not in {
                ResponseIntentState.PENDING,
                ResponseIntentState.DELIVERY_UNKNOWN,
            }:
                raise CapstoneGateRejected("UNKNOWN_NOT_VALID_AFTER_ACCEPTANCE")
            return replace(
                intent,
                state=ResponseIntentState.DELIVERY_UNKNOWN,
                revision=intent.revision + 1,
            )
        if observation is DispatchObservation.NOT_FOUND:
            if intent.state is not ResponseIntentState.DELIVERY_UNKNOWN:
                raise CapstoneGateRejected("NOT_FOUND_REQUIRES_RECONCILIATION")
            return replace(
                intent,
                state=ResponseIntentState.PENDING,
                revision=intent.revision + 1,
            )
        if observation is DispatchObservation.ACCEPTED:
            if intent.state not in {
                ResponseIntentState.PENDING,
                ResponseIntentState.DELIVERY_UNKNOWN,
            }:
                if (
                    intent.state is ResponseIntentState.DISPATCHED
                    and intent.provider_message_id == record.provider_message_id
                ):
                    return replace(intent, revision=intent.revision + 1)
                raise CapstoneIdentityConflict("DESTINATION_ACCEPTANCE_CONFLICT")
            return replace(
                intent,
                state=ResponseIntentState.DISPATCHED,
                revision=intent.revision + 1,
                dispatch_at=record.observed_at,
                provider_message_id=record.provider_message_id,
            )
        if observation is DispatchObservation.DELIVERED:
            if intent.state is not ResponseIntentState.DISPATCHED:
                raise CapstoneGateRejected("DELIVERY_REQUIRES_DISPATCH_ACCEPTANCE")
            if intent.provider_message_id != record.provider_message_id:
                raise CapstoneIdentityConflict("DELIVERY_RECEIPT_MESSAGE_CONFLICT")
            return replace(
                intent,
                state=ResponseIntentState.DELIVERED,
                revision=intent.revision + 1,
                delivered_at=record.observed_at,
            )
        if observation is DispatchObservation.DUPLICATE_RECEIPT:
            if (
                intent.state is not ResponseIntentState.DELIVERED
                or intent.provider_message_id != record.provider_message_id
            ):
                raise CapstoneIdentityConflict("DUPLICATE_RECEIPT_NOT_EXACT")
            return replace(intent, revision=intent.revision + 1)
        raise ValueError(f"unsupported dispatch observation: {observation}")

    def read_intent(self, intent_id: str) -> ResponseIntent | None:
        with self._lock:
            return self._intents.get(intent_id)

    def history(self, intent_id: str) -> tuple[RecoveryAndIncidentRecord, ...]:
        with self._lock:
            return tuple(self._history.get(intent_id, ()))

    def recoverable_intents(self) -> tuple[ResponseIntent, ...]:
        """Return durable work after restart; memory-only decisions are absent."""

        with self._lock:
            return tuple(
                sorted(
                    (
                        item
                        for item in self._intents.values()
                        if item.state in {
                            ResponseIntentState.PENDING,
                            ResponseIntentState.DELIVERY_UNKNOWN,
                        }
                    ),
                    key=lambda item: item.intent_id,
                )
            )

    def release_records(self) -> tuple[AnswerReleaseRecord, ...]:
        with self._lock:
            return tuple(
                self._release_records[key]
                for key in sorted(self._release_records)
            )

    def export_state(
        self,
    ) -> tuple[
        tuple[AnswerReleaseRecord, ...],
        tuple[ResponseIntent, ...],
        tuple[tuple[str, tuple[RecoveryAndIncidentRecord, ...]], ...],
    ]:
        """Export the content-safe durable model for deterministic restart tests."""

        with self._lock:
            return (
                self.release_records(),
                tuple(self._intents[key] for key in sorted(self._intents)),
                tuple(
                    (key, tuple(self._history[key]))
                    for key in sorted(self._history)
                ),
            )

    @classmethod
    def restore(
        cls,
        state: tuple[
            tuple[AnswerReleaseRecord, ...],
            tuple[ResponseIntent, ...],
            tuple[tuple[str, tuple[RecoveryAndIncidentRecord, ...]], ...],
        ],
        *,
        authorization_authority: InMemoryRetrievalAuthorization | None = None,
        release_currentness_authority: (
            InMemoryReleaseCurrentnessAuthority | None
        ) = None,
    ) -> "InMemoryResponseLedger":
        """Rehydrate exact durable state; reject forks or broken bindings."""

        records, intents, histories = state
        ledger = cls(
            authorization_authority=authorization_authority,
            release_currentness_authority=release_currentness_authority,
        )
        record_by_intent: dict[str, AnswerReleaseRecord] = {}
        for item in records:
            if item.response_intent_id is None:
                continue
            if item.response_intent_id in record_by_intent:
                raise CapstoneIdentityConflict(
                    "RESTORE_DUPLICATE_RESPONSE_INTENT_OWNERSHIP"
                )
            record_by_intent[item.response_intent_id] = item
        if len(record_by_intent) != len(intents):
            raise CapstoneIdentityConflict("RESTORE_DECISION_INTENT_CARDINALITY_CONFLICT")
        for record in records:
            if record.record_id in ledger._release_records:
                raise CapstoneIdentityConflict("RESTORE_DUPLICATE_RELEASE_RECORD")
            ledger._claim_decision_ownership(record)
            ledger._release_records[record.record_id] = record
        for intent in intents:
            record = record_by_intent.get(intent.intent_id)
            if record is None or (
                record.output_release_decision_digest
                != intent.output_release_decision_digest
                or record.answer_candidate_digest != intent.candidate_digest
                or record.request_binding_digest != intent.request_binding_digest
                or record.authorized_destination != intent.destination
                or record.dispatch_idempotency_key
                != intent.dispatch_idempotency_key
            ):
                raise CapstoneIdentityConflict("RESTORE_DECISION_INTENT_BINDING_CONFLICT")
            if intent.intent_id in ledger._intents:
                raise CapstoneIdentityConflict("RESTORE_DUPLICATE_INTENT")
            if intent.dispatch_idempotency_key in ledger._intent_by_idempotency_key:
                raise CapstoneIdentityConflict("RESTORE_IDEMPOTENCY_KEY_CONFLICT")
            ledger._intents[intent.intent_id] = intent
            ledger._intent_by_idempotency_key[
                intent.dispatch_idempotency_key
            ] = intent.intent_id
            ledger._release_record_by_intent[intent.intent_id] = record.record_id
        history_by_intent = dict(histories)
        if len(history_by_intent) != len(histories):
            raise CapstoneIdentityConflict("RESTORE_DUPLICATE_HISTORY")
        if set(history_by_intent) != set(ledger._intents):
            raise CapstoneIdentityConflict("RESTORE_HISTORY_INTENT_SET_CONFLICT")
        recovery_record_owner: dict[str, str] = {}
        for intent_id, items in history_by_intent.items():
            previous: str | None = None
            seen: set[str] = set()
            final_intent = ledger._intents[intent_id]
            replayed_intent = replace(
                final_intent,
                state=ResponseIntentState.PENDING,
                revision=1,
                dispatch_at=None,
                delivered_at=None,
                provider_message_id=None,
            )
            previous_record: RecoveryAndIncidentRecord | None = None
            for item in items:
                owner = recovery_record_owner.get(item.record_id)
                if owner is not None and owner != intent_id:
                    raise CapstoneIdentityConflict(
                        "RESTORE_RECOVERY_RECORD_ID_ALREADY_OWNED"
                    )
                if (
                    item.response_intent_id != intent_id
                    or item.previous_record_id != previous
                    or item.record_id in seen
                    or item.dispatch_idempotency_key
                    != final_intent.dispatch_idempotency_key
                ):
                    raise CapstoneIdentityConflict("RESTORE_APPEND_ONLY_HISTORY_CONFLICT")
                seen.add(item.record_id)
                recovery_record_owner[item.record_id] = intent_id
                previous = item.record_id
                cls._validate_history_step(
                    replayed_intent,
                    item,
                    previous_record=previous_record,
                )
                replayed_intent = cls._transition(replayed_intent, item)
                previous_record = item
            if replayed_intent != final_intent:
                raise CapstoneIdentityConflict("RESTORE_DURABLE_STATE_REPLAY_CONFLICT")
            ledger._history[intent_id] = list(items)
        ledger._recovery_record_owner = recovery_record_owner
        return ledger


def seal_execution(
    *,
    execution_id: str,
    repository_revision: str,
    config_fingerprint: str,
    runtime_boundary: str,
    evidence_level: str,
    exact_command: str,
    started_at: str,
    completed_at: str,
    lineages: tuple[SourceToOccurrenceLineage, ...],
    request_bindings: tuple[CapstoneRequestBinding, ...],
    retrieval_receipts: tuple[RetrievalAndContextReceipt, ...],
    answer_release_records: tuple[AnswerReleaseRecord, ...],
    response_intents: tuple[ResponseIntent, ...],
    recovery_records: tuple[RecoveryAndIncidentRecord, ...],
    release_currentness_snapshots: tuple[ReleaseCurrentnessSnapshot, ...],
    prerequisite_evidence_digests: tuple[str, ...],
    evaluation: CapstoneEvaluationDecision,
    executed_checks: tuple[str, ...],
    not_run: tuple[str, ...],
) -> EndToEndExecutionManifest:
    """Seal one content-safe deterministic execution after all checks finish."""

    if evaluation.execution_id != execution_id:
        raise CapstoneIdentityConflict("EVALUATION_EXECUTION_ID_CONFLICT")
    binding_digests = {item.digest for item in request_bindings}
    receipt_digests = {item.digest for item in retrieval_receipts}
    receipts_by_digest = {
        item.digest: item for item in retrieval_receipts
    }
    currentness_by_digest = {
        item.digest: item for item in release_currentness_snapshots
    }
    if len(binding_digests) != len(request_bindings):
        raise CapstoneIdentityConflict("DUPLICATE_REQUEST_BINDING_DIGEST")
    if len(receipt_digests) != len(retrieval_receipts):
        raise CapstoneIdentityConflict("DUPLICATE_RETRIEVAL_RECEIPT_DIGEST")
    if len(currentness_by_digest) != len(release_currentness_snapshots):
        raise CapstoneIdentityConflict(
            "DUPLICATE_RELEASE_CURRENTNESS_SNAPSHOT_DIGEST"
        )
    if any(
        item.request_binding_digest not in binding_digests
        for item in retrieval_receipts
    ):
        raise CapstoneIdentityConflict("RECEIPT_REFERENCES_UNKNOWN_REQUEST")
    for item in answer_release_records:
        if item.request_binding_digest not in binding_digests:
            raise CapstoneIdentityConflict("RELEASE_REFERENCES_UNKNOWN_REQUEST")
        if item.retrieval_context_receipt_digest not in receipt_digests:
            raise CapstoneIdentityConflict("RELEASE_REFERENCES_UNKNOWN_RECEIPT")
        receipt = receipts_by_digest[item.retrieval_context_receipt_digest]
        if receipt.request_binding_digest != item.request_binding_digest:
            raise CapstoneIdentityConflict(
                "RELEASE_RECEIPT_REQUEST_BINDING_CONFLICT"
            )
        currentness = currentness_by_digest.get(
            item.release_currentness_snapshot_digest
        )
        if currentness is None or (
            currentness.snapshot_id != item.release_currentness_snapshot_id
            or currentness.revision != item.release_currentness_revision
        ):
            raise CapstoneIdentityConflict(
                "RELEASE_CURRENTNESS_SNAPSHOT_BINDING_CONFLICT"
            )
        if item.result == "PASS" and item.disposition == "RELEASE":
            currently_eligible = set(
                currentness.source_eligible_occurrence_ids
            ).difference(currentness.quarantined_occurrence_ids)
            if (
                currentness.dlp_result != "PASS"
                or currentness.metadata_stripping_result != "PASS"
                or currentness.destination_result != "PASS"
                or not set(item.released_occurrence_ids).issubset(
                    currently_eligible
                )
            ):
                raise CapstoneIdentityConflict(
                    "SEALED_RELEASE_GATE_EVIDENCE_CONFLICT"
                )
    if len({item.digest for item in answer_release_records}) != len(
        answer_release_records
    ):
        raise CapstoneIdentityConflict("DUPLICATE_RELEASE_RECORD_DIGEST")
    if len({item.digest for item in response_intents}) != len(response_intents):
        raise CapstoneIdentityConflict("DUPLICATE_RESPONSE_INTENT_DIGEST")
    release_record_ids = tuple(
        item.record_id for item in answer_release_records
    )
    if len(set(release_record_ids)) != len(release_record_ids):
        raise CapstoneIdentityConflict("DUPLICATE_RELEASE_RECORD_ID")
    response_intent_ids = tuple(
        item.response_intent_id
        for item in answer_release_records
        if item.response_intent_id is not None
    )
    if len(set(response_intent_ids)) != len(response_intent_ids):
        raise CapstoneIdentityConflict(
            "DUPLICATE_RESPONSE_INTENT_OWNERSHIP"
        )
    decision_ids = tuple(
        item.output_release_decision_id for item in answer_release_records
    )
    decision_digests = tuple(
        item.output_release_decision_digest for item in answer_release_records
    )
    if len(set(decision_ids)) != len(decision_ids):
        raise CapstoneIdentityConflict("DUPLICATE_OUTPUT_DECISION_ID_OWNERSHIP")
    if len(set(decision_digests)) != len(decision_digests):
        raise CapstoneIdentityConflict("DUPLICATE_OUTPUT_DECISION_OWNERSHIP")
    records_by_intent = {
        item.response_intent_id: item
        for item in answer_release_records
        if item.response_intent_id is not None
    }
    intents_by_id = {item.intent_id: item for item in response_intents}
    if len(intents_by_id) != len(response_intents):
        raise CapstoneIdentityConflict("DUPLICATE_RESPONSE_INTENT_ID")
    if set(records_by_intent) != set(intents_by_id):
        raise CapstoneIdentityConflict("DECISION_INTENT_CARDINALITY_CONFLICT")
    for intent_id, record in records_by_intent.items():
        intent = intents_by_id[intent_id]
        if (
            record.request_binding_digest != intent.request_binding_digest
            or record.output_release_decision_digest
            != intent.output_release_decision_digest
            or record.answer_candidate_digest != intent.candidate_digest
            or record.authorized_destination != intent.destination
            or record.dispatch_idempotency_key
            != intent.dispatch_idempotency_key
        ):
            raise CapstoneIdentityConflict(
                "SEALED_DECISION_INTENT_BINDING_CONFLICT"
            )
    intent_ids = set(intents_by_id)
    histories: dict[str, list[RecoveryAndIncidentRecord]] = {}
    recovery_record_ids: set[str] = set()
    for item in recovery_records:
        if item.response_intent_id not in intent_ids:
            raise CapstoneIdentityConflict("RECOVERY_REFERENCES_UNKNOWN_INTENT")
        if item.dispatch_idempotency_key != (
            intents_by_id[item.response_intent_id].dispatch_idempotency_key
        ):
            raise CapstoneIdentityConflict(
                "RECOVERY_DISPATCH_IDEMPOTENCY_KEY_CONFLICT"
            )
        if item.record_id in recovery_record_ids:
            raise CapstoneIdentityConflict("DUPLICATE_RECOVERY_RECORD_ID")
        recovery_record_ids.add(item.record_id)
        histories.setdefault(item.response_intent_id, []).append(item)
    for items in histories.values():
        previous: str | None = None
        for item in items:
            if item.previous_record_id != previous:
                raise CapstoneIdentityConflict("SEALED_RECOVERY_HISTORY_FORK")
            previous = item.record_id
    restored_histories = tuple(
        (
            intent_id,
            tuple(histories.get(intent_id, ())),
        )
        for intent_id in sorted(intent_ids)
    )
    InMemoryResponseLedger.restore(
        (
            answer_release_records,
            response_intents,
            restored_histories,
        )
    )
    evaluated = tuple(
        sorted(
            {
                *(item.digest for item in lineages),
                *(item.digest for item in request_bindings),
                *(item.digest for item in retrieval_receipts),
                *(item.digest for item in answer_release_records),
                *(item.digest for item in response_intents),
                *(item.digest for item in recovery_records),
                *(item.digest for item in release_currentness_snapshots),
            }
        )
    )
    if evaluation.evaluated_artifact_digests != evaluated:
        raise CapstoneIdentityConflict("EVALUATION_ARTIFACT_SET_CONFLICT")
    return EndToEndExecutionManifest(
        execution_id=execution_id,
        repository_revision=repository_revision,
        config_fingerprint=config_fingerprint,
        runtime_boundary=runtime_boundary,
        evidence_level=evidence_level,
        exact_command=exact_command,
        started_at=started_at,
        completed_at=completed_at,
        lineage_digests=tuple(sorted(item.digest for item in lineages)),
        request_binding_digests=tuple(
            sorted(item.digest for item in request_bindings)
        ),
        retrieval_context_receipt_digests=tuple(
            sorted(item.digest for item in retrieval_receipts)
        ),
        answer_release_record_digests=tuple(
            sorted(item.digest for item in answer_release_records)
        ),
        response_intent_digests=tuple(
            sorted(item.digest for item in response_intents)
        ),
        recovery_record_digests=tuple(
            sorted(item.digest for item in recovery_records)
        ),
        release_currentness_snapshot_digests=tuple(
            sorted(item.digest for item in release_currentness_snapshots)
        ),
        prerequisite_evidence_digests=tuple(
            sorted(prerequisite_evidence_digests)
        ),
        evaluation_decision_digest=evaluation.digest,
        executed_checks=tuple(sorted(executed_checks)),
        not_run=tuple(sorted(not_run)),
        raw_prompt_logged=False,
        protected_chunk_logged=False,
        answer_candidate_text_logged=False,
        secret_logged=False,
        raw_vector_logged=False,
    )
