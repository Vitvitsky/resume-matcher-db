"""overall_score: Integer → Float для сохранения precision

Revision ID: 005
Revises: 004
Create Date: 2026-04-26 22:30:00.000000+00:00

Engine выдаёт overall_score как float (например 78.5), но при записи в
MatchResultDB и CandidateScoringLink значение truncate'илось до int. Теперь
оба поля Float, чтобы сохранить точность и видеть дробные баллы в UI.

Существующие int-значения корректно поднимаются как float через USING ...::float.
Downgrade обратно к Integer теряет дробную часть (это ожидаемая семантика).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "match_results",
        "overall_score",
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="overall_score::float",
    )
    op.alter_column(
        "candidate_scoring_links",
        "overall_score",
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="overall_score::float",
    )


def downgrade() -> None:
    op.alter_column(
        "match_results",
        "overall_score",
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="overall_score::integer",
    )
    op.alter_column(
        "candidate_scoring_links",
        "overall_score",
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="overall_score::integer",
    )
