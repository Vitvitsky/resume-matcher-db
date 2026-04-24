"""Денормализованные колонки для кэш-таблиц (ускорение list-запросов)

Добавляет колонки-дубли из artifact_json для быстрых выборок
без парсинга JSON. artifact_json сохраняется как JSONB для полного артефакта.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vacancy_cache: поля для dashboard-списка вакансий
    # ------------------------------------------------------------------
    op.add_column("vacancy_cache", sa.Column("role_title", sa.String(256), nullable=True))
    op.add_column("vacancy_cache", sa.Column("job_family", sa.String(50), nullable=True))
    op.add_column("vacancy_cache", sa.Column("domain", sa.String(100), nullable=True))
    op.add_column("vacancy_cache", sa.Column("role_level", sa.String(50), nullable=True))
    op.create_index("ix_vacancy_cache_job_family", "vacancy_cache", ["job_family"])

    # ------------------------------------------------------------------
    # resume_cache: имя кандидата и опыт
    # ------------------------------------------------------------------
    op.add_column("resume_cache", sa.Column("candidate_name", sa.String(256), nullable=True))
    op.add_column("resume_cache", sa.Column("total_experience_years", sa.Float(), nullable=True))

    # ------------------------------------------------------------------
    # match_results: поля для списка кандидатов по вакансии
    # ------------------------------------------------------------------
    op.add_column("match_results", sa.Column("overall_score", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("candidate_name", sa.String(256), nullable=True))
    op.add_column("match_results", sa.Column("vacancy_name", sa.String(256), nullable=True))
    op.add_column("match_results", sa.Column("job_family", sa.String(50), nullable=True))
    op.add_column("match_results", sa.Column("red_flags_count", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("summary_short", sa.Text(), nullable=True))
    op.create_index("ix_match_results_job_family", "match_results", ["job_family"])

    # ------------------------------------------------------------------
    # Бэкфилл существующих данных из artifact_json
    # ------------------------------------------------------------------
    conn = op.get_bind()

    # Бэкфилл vacancy_cache
    rows = conn.execute(sa.text("SELECT vacancy_id, artifact_json FROM vacancy_cache")).fetchall()
    import json
    for vacancy_id, artifact_json in rows:
        try:
            data = json.loads(artifact_json)
            job = data.get("data", data)
            conn.execute(
                sa.text("""
                    UPDATE vacancy_cache SET
                        role_title = :role_title,
                        job_family = :job_family,
                        domain = :domain,
                        role_level = :role_level
                    WHERE vacancy_id = :vid
                """),
                {
                    "vid": vacancy_id,
                    "role_title": job.get("role_title"),
                    "job_family": job.get("job_family"),
                    "domain": job.get("domain"),
                    "role_level": job.get("role_level"),
                },
            )
        except Exception:
            continue

    # Бэкфилл resume_cache
    rows = conn.execute(sa.text("SELECT resume_id, artifact_json FROM resume_cache")).fetchall()
    for resume_id, artifact_json in rows:
        try:
            data = json.loads(artifact_json)
            cand = data.get("data", data)
            conn.execute(
                sa.text("""
                    UPDATE resume_cache SET
                        candidate_name = :candidate_name,
                        total_experience_years = :total_experience_years
                    WHERE resume_id = :rid
                """),
                {
                    "rid": resume_id,
                    "candidate_name": cand.get("name"),
                    "total_experience_years": cand.get("total_experience_years"),
                },
            )
        except Exception:
            continue

    # Бэкфилл match_results
    rows = conn.execute(sa.text("SELECT match_id, artifact_json FROM match_results")).fetchall()
    for match_id, artifact_json in rows:
        try:
            data = json.loads(artifact_json)
            scoring = data.get("data", data)
            candidate_name = data.get("candidate_name")
            if not candidate_name:
                cand = data.get("candidate") or {}
                candidate_name = cand.get("name") if isinstance(cand, dict) else None
            red_flags = scoring.get("red_flags") or []
            red_flags_count = len(red_flags) if isinstance(red_flags, list) else 0
            summary_short = scoring.get("summary_short") or scoring.get("summary") or ""
            if isinstance(summary_short, dict):
                summary_short = summary_short.get("text", "") or summary_short.get("summary_short", "")
            conn.execute(
                sa.text("""
                    UPDATE match_results SET
                        overall_score = :overall_score,
                        candidate_name = :candidate_name,
                        vacancy_name = :vacancy_name,
                        job_family = :job_family,
                        red_flags_count = :red_flags_count,
                        summary_short = :summary_short
                    WHERE match_id = :mid
                """),
                {
                    "mid": match_id,
                    "overall_score": int(scoring.get("overall_score", 0)) if scoring.get("overall_score") is not None else None,
                    "candidate_name": candidate_name,
                    "vacancy_name": scoring.get("vacancy_name"),
                    "job_family": scoring.get("job_family"),
                    "red_flags_count": red_flags_count,
                    "summary_short": summary_short[:500] if summary_short else None,
                },
            )
        except Exception:
            continue


def downgrade() -> None:
    # match_results
    op.drop_index("ix_match_results_job_family", table_name="match_results")
    op.drop_column("match_results", "summary_short")
    op.drop_column("match_results", "red_flags_count")
    op.drop_column("match_results", "job_family")
    op.drop_column("match_results", "vacancy_name")
    op.drop_column("match_results", "candidate_name")
    op.drop_column("match_results", "overall_score")

    # resume_cache
    op.drop_column("resume_cache", "total_experience_years")
    op.drop_column("resume_cache", "candidate_name")

    # vacancy_cache
    op.drop_index("ix_vacancy_cache_job_family", table_name="vacancy_cache")
    op.drop_column("vacancy_cache", "role_level")
    op.drop_column("vacancy_cache", "domain")
    op.drop_column("vacancy_cache", "job_family")
    op.drop_column("vacancy_cache", "role_title")
