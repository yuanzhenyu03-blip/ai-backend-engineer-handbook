"""Day90 MCP Client boundary over application DTOs and an injected transport."""
from __future__ import annotations

from dataclasses import dataclass

from mcp_client_codec import MCPWireCodec
from mcp_client_transport import (
    DispatchCertainty,
    MCPByteTransport,
    MCPTransportFailure,
)
from mcp_protocol_model import (
    MCPRequestBinding,
    MCPRequestDTO,
    MCPResponseDTO,
    ProtocolObservation,
    ProtocolOutcome,
)
from mcp_remote_lifecycle import (
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
)


@dataclass(frozen=True)
class MCPClientExchange:
    """Exactly one decoded response or transport observation."""

    response: MCPResponseDTO | None = None
    observation: ProtocolObservation | None = None
    failure_evidence: FailureEvidence | None = None

    def __post_init__(self) -> None:
        if (self.response is None) == (self.observation is None):
            raise ValueError(
                "exchange requires exactly one response or observation"
            )
        if self.failure_evidence is not None and self.observation is None:
            raise ValueError(
                "failure evidence requires a transport observation"
            )


@dataclass(frozen=True)
class DependencyFreeMCPClientAdapter:
    """Encode, exchange and decode while leaving correlation to the app."""

    transport: MCPByteTransport
    codec: MCPWireCodec = MCPWireCodec()

    def exchange(
        self,
        request: MCPRequestDTO,
        binding: MCPRequestBinding,
        *,
        attempt_number: int = 1,
    ) -> MCPClientExchange:
        """Run one already-bound protocol attempt.

        The caller must persist the binding and dispatch boundary before this
        method.  A successful return is still only an MCPResponseDTO; local
        correlation and application output validation happen afterwards.
        """

        if request.protocol_request_id != binding.protocol_request_id:
            raise ValueError("request does not match the local binding")
        if request.method != binding.expected_method:
            raise ValueError("request method does not match the local binding")

        message = self.codec.encode_request(request)
        try:
            payload = self.transport.exchange(message)
        except MCPTransportFailure as error:
            outcome = (
                ProtocolOutcome.PRE_DISPATCH_ABORTED
                if error.dispatch_certainty
                is DispatchCertainty.PROVEN_NOT_SENT
                else ProtocolOutcome.OUTCOME_UNKNOWN
            )
            return MCPClientExchange(
                observation=ProtocolObservation(
                    outcome=outcome,
                    protocol_request_id=request.protocol_request_id,
                    application_operation_id=(
                        binding.application_operation_id
                    ),
                    reason=error.reason,
                ),
                failure_evidence=FailureEvidence(
                    operation_id=binding.application_operation_id,
                    idempotency_key=binding.idempotency_key or "not-applicable",
                    protocol_request_id=request.protocol_request_id,
                    attempt_number=attempt_number,
                    phase=FailurePhase.SEND,
                    kind=FailureKind.SEND_FAILURE,
                    dispatch_certainty=error.dispatch_certainty,
                    execution_certainty=(
                        ExecutionCertainty.PROVEN_NOT_EXECUTED
                        if error.dispatch_certainty
                        is DispatchCertainty.PROVEN_NOT_SENT
                        else ExecutionCertainty.POSSIBLY_EXECUTED
                    ),
                    evidence_source="dependency-free-byte-transport",
                ),
            )

        return MCPClientExchange(response=self.codec.decode_response(payload))
