"""home schema: drop ритм-tables, add debug/upload/batches

Revision ID: 63fddf1c0728
Revises: 002
Create Date: 2026-04-24 10:14:41.352822+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "63fddf1c0728"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Drop РИТМ-таблиц (home-BFF их не использует)
    # ------------------------------------------------------------------
    op.drop_index(op.f("ix_cim_resume_id"), table_name="candidate_id_mapping")
    op.drop_table("candidate_id_mapping")
    op.drop_index(op.f("ix_rom_vacancy_id"), table_name="resource_order_mapping")
    op.drop_table("resource_order_mapping")

    # ------------------------------------------------------------------
    # batches: батч-задачи скоринга
    # ------------------------------------------------------------------
    op.create_table(
        "batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vacancy_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("cancelled", sa.Boolean(), nullable=False),
        sa.Column("author_ldap", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy_cache.vacancy_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # llm_debug_artifacts: промпты + сырые ответы LLM
    # ------------------------------------------------------------------
    op.create_table(
        "llm_debug_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("match_result_id", sa.String(length=192), nullable=True),
        sa.Column("vacancy_id", sa.String(length=128), nullable=True),
        sa.Column("resume_id", sa.String(length=128), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False),
        sa.Column("llm_model", sa.String(length=128), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["match_result_id"], ["match_results.match_id"]),
        sa.ForeignKeyConstraint(["resume_id"], ["resume_cache.resume_id"]),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy_cache.vacancy_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_debug_artifacts_match_result_id"),
        "llm_debug_artifacts",
        ["match_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_debug_artifacts_stage"),
        "llm_debug_artifacts",
        ["stage"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # upload_files: метаданные загруженных файлов
    # ------------------------------------------------------------------
    op.create_table(
        "upload_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.String(length=128), nullable=True),
        sa.Column("vacancy_id", sa.String(length=128), nullable=True),
        sa.Column("resume_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resume_cache.resume_id"]),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy_cache.vacancy_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_path"),
    )
    op.create_index(
        op.f("ix_upload_files_sha256"),
        "upload_files",
        ["sha256"],
        unique=False,
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Home-only таблицы
    # ------------------------------------------------------------------
    op.drop_index(op.f("ix_upload_files_sha256"), table_name="upload_files")
    op.drop_table("upload_files")
    op.drop_index(op.f("ix_llm_debug_artifacts_stage"), table_name="llm_debug_artifacts")
    op.drop_index(
        op.f("ix_llm_debug_artifacts_match_result_id"),
        table_name="llm_debug_artifacts",
    )
    op.drop_table("llm_debug_artifacts")
    op.drop_table("batches")

    # ------------------------------------------------------------------
    # Восстанавливаем РИТМ-таблицы
    # ------------------------------------------------------------------
    op.create_table(
        "resource_order_mapping",
        sa.Column("resource_order_id", sa.String(length=256), primary_key=True),
        sa.Column("vacancy_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_rom_vacancy_id"),
        "resource_order_mapping",
        ["vacancy_id"],
        unique=False,
    )
    op.create_table(
        "candidate_id_mapping",
        sa.Column("candidate_id", sa.String(length=36), primary_key=True),
        sa.Column("resume_id", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_cim_resume_id"),
        "candidate_id_mapping",
        ["resume_id"],
        unique=False,
    )
