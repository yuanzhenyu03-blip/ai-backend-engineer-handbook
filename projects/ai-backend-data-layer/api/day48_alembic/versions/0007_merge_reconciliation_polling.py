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

OPERATOR UPGRADE ORDER (see the runbook's matrix — DO NOT blindly ``upgrade head`` on
a 0003-stage database):
  * A database at 0003 must first ``alembic upgrade 0006_add_reconciliation_polling``
    (gets polling schema WITHOUT Validate/Contract), deploy the resolver, run
    reconciliation until unresolved == 0, and only THEN ``upgrade head`` (which runs
    0004 Validate, 0005 Contract, 0007 merge).
  * A database already at 0004 or 0005 can ``upgrade head`` directly: that applies
    0006 (adds the columns) and 0007 (merge). Such an environment already has
    unresolved == 0 (Validate passed), so there is no legacy reconciliation to do —
    the columns are added purely for SCHEMA COMPATIBILITY with the resolver code.

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
