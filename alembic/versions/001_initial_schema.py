"""Начальная схема базы данных (все таблицы resume-matcher)

Revision ID: 001
Revises:
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vacancy_cache: кэш проанализированных вакансий (VacancyArtifact)
    # ------------------------------------------------------------------
    op.create_table(
        "vacancy_cache",
        sa.Column("vacancy_id", sa.String(128), primary_key=True),
        sa.Column("artifact_json", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("author_ldap", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_vacancy_cache_input_hash", "vacancy_cache", ["input_hash"])

    # ------------------------------------------------------------------
    # resume_cache: кэш проанализированных резюме (ResumeArtifact)
    # ------------------------------------------------------------------
    op.create_table(
        "resume_cache",
        sa.Column("resume_id", sa.String(128), primary_key=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("artifact_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_resume_cache_input_hash", "resume_cache", ["input_hash"])

    # ------------------------------------------------------------------
    # match_results: результаты скоринга (MatchArtifact)
    # ------------------------------------------------------------------
    op.create_table(
        "match_results",
        sa.Column("match_id", sa.String(192), primary_key=True),
        sa.Column("vacancy_id", sa.String(128), nullable=False),
        sa.Column("resume_id", sa.String(128), nullable=False),
        sa.Column("artifact_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("vacancy_id", "resume_id", name="ix_match_vacancy_resume"),
    )
    op.create_index("ix_match_results_vacancy_id", "match_results", ["vacancy_id"])
    op.create_index("ix_match_results_resume_id", "match_results", ["resume_id"])

    # ------------------------------------------------------------------
    # resource_order_mapping: РИТМ resource_order_id → vacancy_id
    # ------------------------------------------------------------------
    op.create_table(
        "resource_order_mapping",
        sa.Column("resource_order_id", sa.String(256), primary_key=True),
        sa.Column("vacancy_id", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_rom_vacancy_id", "resource_order_mapping", ["vacancy_id"])

    # ------------------------------------------------------------------
    # candidate_id_mapping: candidate_id → resume_id
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_id_mapping",
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column("resume_id", sa.String(128), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_cim_resume_id", "candidate_id_mapping", ["resume_id"])

    # ------------------------------------------------------------------
    # user_preferences: настройки пользователей (LDAP → display_name)
    # ------------------------------------------------------------------
    op.create_table(
        "user_preferences",
        sa.Column("ldap", sa.String(128), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # ------------------------------------------------------------------
    # candidates: мастер-таблица кандидатов (дедупликация)
    # ------------------------------------------------------------------
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_normalized", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("alternate_names", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_candidates_name", "candidates", ["name"])
    op.create_index("ix_candidates_name_normalized", "candidates", ["name_normalized"])
    op.create_index("ix_candidates_email", "candidates", ["email"])

    # ------------------------------------------------------------------
    # candidate_resume_links: кандидат → резюме
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_resume_links",
        sa.Column(
            "id", sa.Integer(), sa.Identity(always=False), primary_key=True
        ),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id"),
            nullable=False,
        ),
        sa.Column("resume_id", sa.String(64), nullable=False),
        sa.Column("vacancy_id", sa.String(64), nullable=True),
        sa.Column("source_filename", sa.String(512), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("candidate_id", "resume_id", name="uq_candidate_resume"),
    )
    op.create_index("ix_crl_candidate_id", "candidate_resume_links", ["candidate_id"])
    op.create_index("ix_crl_resume_id", "candidate_resume_links", ["resume_id"])
    op.create_index("ix_crl_vacancy_id", "candidate_resume_links", ["vacancy_id"])

    # ------------------------------------------------------------------
    # candidate_scoring_links: кандидат → результат скоринга
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_scoring_links",
        sa.Column(
            "id", sa.Integer(), sa.Identity(always=False), primary_key=True
        ),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id"),
            nullable=False,
        ),
        sa.Column("vacancy_id", sa.String(64), nullable=False),
        sa.Column("resume_id", sa.String(64), nullable=False),
        sa.Column("match_id", sa.String(128), nullable=False, unique=True),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("job_family", sa.String(50), nullable=True),
        sa.Column(
            "scored_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_csl_candidate_vacancy",
        "candidate_scoring_links",
        ["candidate_id", "vacancy_id"],
    )

    # ------------------------------------------------------------------
    # interview_transcriptions: транскрипции интервью
    # ------------------------------------------------------------------
    op.create_table(
        "interview_transcriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id"),
            nullable=False,
        ),
        sa.Column("vacancy_id", sa.String(64), nullable=False),
        sa.Column("audio_filename", sa.String(512), nullable=False),
        sa.Column("audio_storage_path", sa.String(1024), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("whisper_model", sa.String(100), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("segments_json", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_it_candidate_vacancy",
        "interview_transcriptions",
        ["candidate_id", "vacancy_id"],
    )

    # ------------------------------------------------------------------
    # interview_feedbacks: обратная связь после интервью
    # ------------------------------------------------------------------
    op.create_table(
        "interview_feedbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id"),
            nullable=False,
        ),
        sa.Column("vacancy_id", sa.String(64), nullable=False),
        sa.Column("interviewer_name", sa.String(255), nullable=False),
        sa.Column("interview_date", sa.TIMESTAMP(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=True),
        sa.Column("cultural_fit_score", sa.Integer(), nullable=True),
        sa.Column("strengths", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("weaknesses", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("recommendation", sa.String(20), nullable=False),
        sa.Column("comments", sa.Text(), server_default=""),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_if_candidate_vacancy",
        "interview_feedbacks",
        ["candidate_id", "vacancy_id"],
    )

    # ------------------------------------------------------------------
    # training_data: тренировочные данные для файн-тюнинга
    # ------------------------------------------------------------------
    op.create_table(
        "training_data",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id"),
            nullable=False,
        ),
        sa.Column("vacancy_id", sa.String(64), nullable=False),
        sa.Column("resume_id", sa.String(64), nullable=False),
        sa.Column("match_id", sa.String(128), nullable=True),
        sa.Column("vacancy_requirements_json", JSONB(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("candidate_profile_json", JSONB(), nullable=False),
        sa.Column("scoring_result_json", JSONB(), nullable=True),
        sa.Column("interview_transcript", sa.Text(), nullable=True),
        sa.Column("interview_summary_json", JSONB(), nullable=True),
        sa.Column("feedbacks_json", JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("hiring_decision", sa.String(20), nullable=True),
        sa.Column("quality_label", sa.String(20), nullable=True),
        sa.Column("dataset_version", sa.String(20), nullable=False),
        sa.Column("is_complete", sa.Boolean(), server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_td_candidate_vacancy", "training_data", ["candidate_id", "vacancy_id"]
    )
    op.create_index("ix_td_quality_label", "training_data", ["quality_label"])
    op.create_index("ix_td_hiring_decision", "training_data", ["hiring_decision"])
    op.create_index("ix_td_is_complete", "training_data", ["is_complete"])


def downgrade() -> None:
    # Удаляем в обратном порядке (с учётом FK)
    op.drop_table("training_data")
    op.drop_table("interview_feedbacks")
    op.drop_table("interview_transcriptions")
    op.drop_table("candidate_scoring_links")
    op.drop_table("candidate_resume_links")
    op.drop_table("candidates")
    op.drop_table("user_preferences")
    op.drop_table("candidate_id_mapping")
    op.drop_table("resource_order_mapping")
    op.drop_table("match_results")
    op.drop_table("resume_cache")
    op.drop_table("vacancy_cache")
