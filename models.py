"""
SQLAlchemy ORM модели для home-стенда resume-matcher-bff.

Зеркало `resume-matcher-engine/src/database/models.py` за вычетом РИТМ-
специфичных таблиц (resource_order_mapping, candidate_id_mapping) плюс три
новых таблицы для home-сценария:

- llm_debug_artifacts: промпты и сырые ответы LLM по стадиям скоринга
- upload_files:        метаданные загруженных файлов вакансий/резюме
- batches:             батч-задачи скоринга (пачка резюме под вакансию)

Таблицы:
- candidates: Мастер-таблица кандидатов (дедупликация)
- candidate_resume_links: Связь кандидат → резюме
- candidate_scoring_links: Связь кандидат → результат скоринга
- interview_transcriptions: Транскрипции предварительных интервью
- interview_feedbacks: Обратная связь после финальных интервью
- vacancy_cache: Кэш проанализированных вакансий
- user_preferences: Пользовательские настройки (LDAP → display_name)
- resume_cache: Кэш проанализированных резюме
- match_results: Результаты скоринга
- training_data: Агрегированные записи для обучения моделей
- llm_debug_artifacts: Дебаг-артефакты LLM (home-only)
- upload_files: Метаданные загруженных файлов (home-only)
- batches: Батч-задачи скоринга (home-only)
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    """Текущий UTC как tz-aware datetime для default/onupdate."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CandidateDB(Base):
    """Мастер-таблица кандидатов для дедупликации."""

    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    name_normalized = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    alternate_names = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    resume_links = relationship("CandidateResumeLink", back_populates="candidate")
    transcriptions = relationship("InterviewTranscriptionDB", back_populates="candidate")
    feedbacks = relationship("InterviewFeedbackDB", back_populates="candidate")
    training_records = relationship("TrainingDataDB", back_populates="candidate")


class CandidateResumeLink(Base):
    """Связь кандидат → резюме (один кандидат = много резюме)."""

    __tablename__ = "candidate_resume_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    resume_id = Column(String(64), nullable=False, index=True)
    vacancy_id = Column(String(64), nullable=True, index=True)
    source_filename = Column(String(512), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=_utcnow)

    candidate = relationship("CandidateDB", back_populates="resume_links")

    __table_args__ = (
        UniqueConstraint("candidate_id", "resume_id", name="uq_candidate_resume"),
        Index("ix_crl_candidate_vacancy", "candidate_id", "vacancy_id"),
    )


class CandidateScoringLink(Base):
    """Связь кандидат → результат скоринга."""

    __tablename__ = "candidate_scoring_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    vacancy_id = Column(String(64), nullable=False, index=True)
    resume_id = Column(String(64), nullable=False)
    match_id = Column(String(128), nullable=False, unique=True)
    overall_score = Column(Integer, nullable=False)
    job_family = Column(String(50), nullable=True)
    scored_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_csl_candidate_vacancy", "candidate_id", "vacancy_id"),
    )


class InterviewTranscriptionDB(Base):
    """Транскрипция предварительного интервью."""

    __tablename__ = "interview_transcriptions"

    id = Column(String(36), primary_key=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    vacancy_id = Column(String(64), nullable=False, index=True)
    audio_filename = Column(String(512), nullable=False)
    audio_storage_path = Column(String(1024), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    language = Column(String(10), default="ru")
    whisper_model = Column(String(100), nullable=True)
    full_text = Column(Text, nullable=False)
    segments_json = Column(JSON, default=list)
    summary_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    candidate = relationship("CandidateDB", back_populates="transcriptions")

    __table_args__ = (
        Index("ix_it_candidate_vacancy", "candidate_id", "vacancy_id"),
    )


class InterviewFeedbackDB(Base):
    """Обратная связь после финального интервью."""

    __tablename__ = "interview_feedbacks"

    id = Column(String(36), primary_key=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    vacancy_id = Column(String(64), nullable=False, index=True)
    interviewer_name = Column(String(255), nullable=False)
    interview_date = Column(DateTime(timezone=True), nullable=False)
    overall_score = Column(Integer, nullable=False)
    technical_score = Column(Integer, nullable=True)
    cultural_fit_score = Column(Integer, nullable=True)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    recommendation = Column(String(20), nullable=False)
    comments = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    candidate = relationship("CandidateDB", back_populates="feedbacks")

    __table_args__ = (
        Index("ix_if_candidate_vacancy", "candidate_id", "vacancy_id"),
    )


class VacancyCacheDB(Base):
    """Кэш проанализированных вакансий (VacancyArtifact)."""

    __tablename__ = "vacancy_cache"

    vacancy_id = Column(String(128), primary_key=True)
    artifact_json = Column(Text, nullable=False)
    input_hash = Column(String(64), nullable=True, index=True)
    author_ldap = Column(String(128), nullable=True)
    role_title = Column(String(256), nullable=True)
    job_family = Column(String(50), nullable=True, index=True)
    domain = Column(String(100), nullable=True)
    role_level = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class UserPreferencesDB(Base):
    """Пользовательские настройки (LDAP → display_name)."""

    __tablename__ = "user_preferences"

    ldap = Column(String(128), primary_key=True)
    display_name = Column(String(255), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ResumeCacheDB(Base):
    """Кэш проанализированных резюме (ResumeArtifact)."""

    __tablename__ = "resume_cache"

    resume_id = Column(String(128), primary_key=True)
    input_hash = Column(String(64), nullable=False, index=True)
    artifact_json = Column(Text, nullable=False)
    candidate_name = Column(String(256), nullable=True)
    total_experience_years = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class MatchResultDB(Base):
    """Результаты скоринга (MatchArtifact)."""

    __tablename__ = "match_results"

    match_id = Column(String(192), primary_key=True)
    vacancy_id = Column(String(128), nullable=False, index=True)
    resume_id = Column(String(128), nullable=False, index=True)
    artifact_json = Column(Text, nullable=False)
    overall_score = Column(Integer, nullable=True)
    candidate_name = Column(String(256), nullable=True)
    vacancy_name = Column(String(256), nullable=True)
    job_family = Column(String(50), nullable=True, index=True)
    red_flags_count = Column(Integer, nullable=True)
    summary_short = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_match_vacancy_resume", "vacancy_id", "resume_id"),)


class TrainingDataDB(Base):
    """Записи тренировочных данных для файн-тюнинга."""

    __tablename__ = "training_data"

    id = Column(String(36), primary_key=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    vacancy_id = Column(String(64), nullable=False, index=True)
    resume_id = Column(String(64), nullable=False)
    match_id = Column(String(128), nullable=True)
    vacancy_requirements_json = Column(JSON, nullable=False)
    resume_text = Column(Text, nullable=False)
    candidate_profile_json = Column(JSON, nullable=False)
    scoring_result_json = Column(JSON, nullable=True)
    interview_transcript = Column(Text, nullable=True)
    interview_summary_json = Column(JSON, nullable=True)
    feedbacks_json = Column(JSON, default=list)
    hiring_decision = Column(String(20), nullable=True)
    quality_label = Column(String(20), nullable=True)
    dataset_version = Column(String(20), nullable=False)
    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    candidate = relationship("CandidateDB", back_populates="training_records")

    __table_args__ = (
        Index("ix_td_candidate_vacancy", "candidate_id", "vacancy_id"),
        Index("ix_td_quality_label", "quality_label"),
        Index("ix_td_hiring_decision", "hiring_decision"),
        Index("ix_td_is_complete", "is_complete"),
    )


# ---------------------------------------------------------------------------
# Home-only таблицы (revision 003)
# ---------------------------------------------------------------------------


class LLMDebugArtifactDB(Base):
    """Промпты и сырые ответы LLM для дебага скоринга."""

    __tablename__ = "llm_debug_artifacts"

    id = Column(String(36), primary_key=True)
    match_result_id = Column(
        String(192), ForeignKey("match_results.match_id"), nullable=True, index=True
    )
    vacancy_id = Column(
        String(128), ForeignKey("vacancy_cache.vacancy_id"), nullable=True
    )
    resume_id = Column(
        String(128), ForeignKey("resume_cache.resume_id"), nullable=True
    )
    stage = Column(String(64), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=False)
    pipeline_version = Column(String(32), nullable=False)
    llm_model = Column(String(128), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class UploadFileDB(Base):
    """Метаданные загруженных файлов (вакансии/резюме)."""

    __tablename__ = "upload_files"

    id = Column(String(36), primary_key=True)
    kind = Column(String(16), nullable=False)  # 'vacancy' | 'resume'
    original_filename = Column(String(512), nullable=False)
    stored_path = Column(String(1024), nullable=False, unique=True)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    uploaded_by = Column(String(128), nullable=True)
    vacancy_id = Column(
        String(128), ForeignKey("vacancy_cache.vacancy_id"), nullable=True
    )
    resume_id = Column(
        String(128), ForeignKey("resume_cache.resume_id"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class BatchDB(Base):
    """Батч-задачи скоринга (пачка резюме под одну вакансию)."""

    __tablename__ = "batches"

    id = Column(String(36), primary_key=True)
    vacancy_id = Column(
        String(128), ForeignKey("vacancy_cache.vacancy_id"), nullable=False
    )
    status = Column(String(32), nullable=False, default="pending")
    total = Column(Integer, nullable=False)
    completed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    cancelled = Column(Boolean, nullable=False, default=False)
    author_ldap = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
