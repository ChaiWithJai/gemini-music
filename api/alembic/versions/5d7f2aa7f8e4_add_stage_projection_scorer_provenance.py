"""add_stage_projection_scorer_provenance

Revision ID: 5d7f2aa7f8e4
Revises: d2781838fb3c
Create Date: 2026-02-28 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5d7f2aa7f8e4"
down_revision: Union[str, None] = "d2781838fb3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stage_score_projections",
        sa.Column(
            "scorer_source",
            sa.String(length=20),
            nullable=False,
            server_default="deterministic",
        ),
    )
    op.add_column(
        "stage_score_projections",
        sa.Column("scorer_model", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "stage_score_projections",
        sa.Column(
            "scorer_confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "stage_score_projections",
        sa.Column(
            "scorer_evidence_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_index(
        "ix_stage_score_projections_scorer_source",
        "stage_score_projections",
        ["scorer_source"],
        unique=False,
    )

    op.alter_column(
        "stage_score_projections",
        "scorer_source",
        server_default=None,
    )
    op.alter_column(
        "stage_score_projections",
        "scorer_confidence",
        server_default=None,
    )
    op.alter_column(
        "stage_score_projections",
        "scorer_evidence_json",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage_score_projections_scorer_source",
        table_name="stage_score_projections",
    )
    op.drop_column("stage_score_projections", "scorer_evidence_json")
    op.drop_column("stage_score_projections", "scorer_confidence")
    op.drop_column("stage_score_projections", "scorer_model")
    op.drop_column("stage_score_projections", "scorer_source")
