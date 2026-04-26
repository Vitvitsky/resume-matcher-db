"""tz-aware datetime columns: TIMESTAMP WITHOUT TZ → TIMESTAMP WITH TZ

Revision ID: 004
Revises: 63fddf1c0728
Create Date: 2026-04-26 19:30:00.000000+00:00

Все 17 timestamp-колонок home-схемы переводятся с
`TIMESTAMP WITHOUT TIME ZONE` на `TIMESTAMP WITH TIME ZONE` (TIMESTAMPTZ).

Существующие naive значения интерпретируются как UTC через
`USING col AT TIME ZONE 'UTC'` — это корректно, т.к. вся история home-стенда
писалась через `datetime.utcnow()` (naive UTC).

Downgrade обратное: tz-aware значения нормализуются обратно к naive UTC через
`USING col AT TIME ZONE 'UTC'`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "63fddf1c0728"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table_name, [columns]) — все timestamp-колонки актуальной схемы home-стенда
_TIMESTAMP_COLUMNS: list[tuple[str, list[str]]] = [
    ("candidates", ["created_at", "updated_at"]),
    ("candidate_resume_links", ["uploaded_at"]),
    ("candidate_scoring_links", ["scored_at"]),
    ("interview_transcriptions", ["created_at"]),
    ("interview_feedbacks", ["interview_date", "created_at"]),
    ("vacancy_cache", ["created_at"]),
    ("user_preferences", ["updated_at"]),
    ("resume_cache", ["created_at"]),
    ("match_results", ["created_at"]),
    ("training_data", ["created_at", "updated_at"]),
    ("llm_debug_artifacts", ["created_at"]),
    ("upload_files", ["created_at"]),
    ("batches", ["created_at", "updated_at"]),
]


def upgrade() -> None:
    for table, columns in _TIMESTAMP_COLUMNS:
        for col in columns:
            op.alter_column(
                table,
                col,
                type_=sa.DateTime(timezone=True),
                postgresql_using=f"{col} AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    for table, columns in _TIMESTAMP_COLUMNS:
        for col in columns:
            op.alter_column(
                table,
                col,
                type_=sa.DateTime(timezone=False),
                postgresql_using=f"{col} AT TIME ZONE 'UTC'",
            )
