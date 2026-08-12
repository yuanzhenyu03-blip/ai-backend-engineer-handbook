"""Day61 — S3/MinIO Result Artifact store (bytes) with idempotent HEAD verification.

Object Storage owns the RESULT BYTES; PostgreSQL owns the business truth + Artifact
metadata/reference (job/attempt association, key, checksum, size, content type, provenance,
timestamps). This adapter writes to a deterministic PER-ATTEMPT key and verifies it with a
metadata-only HEAD, never overwriting on a checksum/metadata conflict.

``boto3`` is imported LAZILY so ``py_compile`` and the pure-logic tests do not require it;
running against a real MinIO/S3 is INTEGRATION_RUNTIME (NOT RUN by the updating agent — see
the design/runbook). No endpoint URL, access key, or secret is hardcoded; they come from env.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

from day61_provider_artifact_logic import (
    ArtifactVerdict,
    ExpectedArtifact,
    HeadMetadata,
    result_artifact_key,
    verify_artifact_head,
)


def sha256_of(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _client():
    import boto3  # lazy; only needed for a real run

    return boto3.client(
        "s3",
        endpoint_url=os.environ["DAY61_S3_ENDPOINT_URL"],           # e.g. http://127.0.0.1:9000
        aws_access_key_id=os.environ["DAY61_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["DAY61_S3_SECRET_KEY"],
        region_name=os.environ.get("DAY61_S3_REGION", "us-east-1"),
    )


@dataclass(frozen=True)
class ArtifactRef:
    key: str
    checksum: str
    size_bytes: int
    content_type: str


class S3ArtifactStore:
    def __init__(self, bucket: Optional[str] = None) -> None:
        self._bucket = bucket or os.environ.get("DAY61_S3_BUCKET", "day61-artifacts")

    def key_for(self, tenant_id: str, job_id: str, attempt_id: str) -> str:
        return result_artifact_key(tenant_id, job_id, attempt_id)

    def head(self, key: str) -> HeadMetadata:
        import botocore.exceptions  # lazy

        try:
            resp = _client().head_object(Bucket=self._bucket, Key=key)
        except botocore.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return HeadMetadata(False, None, None, None)
            raise
        meta = resp.get("Metadata", {})
        return HeadMetadata(
            exists=True,
            checksum=meta.get("checksum"),
            size_bytes=int(resp.get("ContentLength", 0)),
            content_type=resp.get("ContentType"),
        )

    def put_if_safe(self, key: str, data: bytes, content_type: str, expected: ExpectedArtifact) -> ArtifactVerdict:
        """Idempotent, non-overwriting write for THIS Attempt's key.

        * ABSENT   -> upload, then re-HEAD to VERIFY (upload success alone is not enough).
        * VERIFIED -> the object already matches (a prior try/timeout succeeded): do NOT
          re-upload; the caller forward-repairs the DB reference + guarded completion.
        * CONFLICT -> the key exists with different bytes/metadata: do NOT overwrite or
          succeed; the caller preserves the candidate/orphan object and reconciles.
        """
        verdict = verify_artifact_head(self.head(key), expected)
        if verdict is ArtifactVerdict.ABSENT:
            _client().put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type,
                Metadata={"checksum": expected.checksum},
            )
            return verify_artifact_head(self.head(key), expected)  # re-verify by HEAD
        return verdict
