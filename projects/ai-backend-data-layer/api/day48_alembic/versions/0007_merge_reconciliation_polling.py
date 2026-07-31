"""Merge: re-unify the reconciliation-polling branch with the Contract head.

Revision ID: 0007_merge_reconciliation_polling
Revises: 0005_contract_legacy, 0006_add_reconciliation_polling
Create Date: 2026-07-31

This is a NO-DDL MERGE revision. It exists ONLY to bring the graph back to a SINGLE
head after the intentional branch introduced by 0006_add_reconciliation_polling
(which branches off 0003_add_lease_constraints so a database still at the 0003 stage
can obtain the reconciliation polling schema WITHOUT first running Validate (0004) /
Contract (0005)).

Its two parents are the two branch tips:
  * 0005_contract_legacy               (0003 -> 0004 -> 0005)
  * 0006_add_reconciliation_polling    (0003 -> 0006)

WHY A MERGE (not a linear rewrite): rewriting 0004/0005's down_revision would break
immutability for any database already recorded at 0004 or 0005. Branch + merge keeps
every published revision's parentage intact while restoring a single head.

CONTRACT GATE — this merge head (0007) DEPENDS ON 0005_contract_legacy, so
``alembic upgrade head`` from a 0003- or 0004-stage database would AUTOMATICALLY run
the DESTRUCTIVE, human-gated 0005 Contract. ``upgrade head`` is therefore NOT the
default command for a 0003- or 0004-stage database; use EXPLICIT staged targets and
run ``upgrade head`` (which crosses Contract) ONLY as the final step after the
Contract gate (Switch complete + observation period + health evidence + explicit
human approval) is met.

OPERATOR UPGRADE ORDER (see the runbook's matrix — do NOT jump a 0003/0004 DB to head):
  * A database at 0003: staged order 0003 -> 0006 -> reconciliation -> 0004 -> observation
    -> head. (1) ``alembic upgrade 0006_add_reconciliation_polling`` (polling schema ONLY,
    no Validate/Contract). (2) deploy the resolver and run reconciliation (no Provider).
    (3) ONLY when unresolved == 0: ``alembic upgrade 0004_validate_lease`` (Validate ONLY).
    (4) complete Switch + observation + health evidence. (5) ONLY after explicit human
    Contract approval: ``alembic upgrade head`` (runs 0005 Contract + 0007 merge).
  * A database at 0004: ``alembic upgrade 0006_add_reconciliation_polling`` for runtime
    SCHEMA COMPATIBILITY — do NOT ``upgrade head`` (it would auto-run destructive 0005).
    Whether reconciliation is needed NOW is decided from current data + a schema-compat
    check, not assumed. Still complete Switch + observation + health + human Contract
    approval before ``alembic upgrade head``.
  * A database already at 0005: ``alembic upgrade head`` is fine — it applies only 0006
    then 0007 and crosses NO new Contract (0005 is already recorded as applied).

TRANSIENT alembic_version: during this staged rollout a database may briefly record
MORE THAN ONE head (e.g. 0006 alongside 0004). That is a transient per-database state,
not a claim that the repository graph has multiple final heads — the single final head
is 0007_merge_reconciliation_polling.

This revision performs NO schema change; upgrade()/downgrade() are intentionally empty.
"""

# revision identifiers, used by Alembic.
revision = "0007_merge_reconciliation_polling"
down_revision = ("0005_contract_legacy", "0006_add_reconciliation_polling")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-DDL merge: it only re-unifies the graph to a single head.
    pass


def downgrade() -> None:
    # Splitting the merge back into two heads is the reverse of a no-DDL merge.
    pass
