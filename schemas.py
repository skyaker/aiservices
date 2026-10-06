from typing import Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------
# PYDANTIC-МОДЕЛЬ ВХОДНЫХ ДАННЫХ
# ------------------------------------------------------------

class CandidateRequest(BaseModel):
    application_id: str = Field(..., min_length=1, max_length=64, description="ID отклика")
    candidate_id: str = Field(..., min_length=1, max_length=64, description="ID кандидата")
    vacancy_id: str = Field(..., min_length=1, max_length=64, description="ID вакансии")
    experience_years: float = Field(..., ge=0, le=50, description="Релевантный опыт, лет")
    required_experience_years: float = Field(
        ..., ge=0, le=50, description="Требуемый опыт для вакансии, лет"
    )
    skills_match_percent: int = Field(
        ..., ge=0, le=100, description="Соответствие навыков вакансии, %"
    )
    assessment_score: int = Field(
        ..., ge=0, le=100, description="Результат профильного тестирования, %"
    )
    salary_expectation: int = Field(
        ..., gt=0, le=10_000_000, description="Ожидаемая месячная зарплата, руб."
    )
    salary_budget: int = Field(
        ..., gt=0, le=10_000_000, description="Верхняя граница бюджета вакансии, руб."
    )
    english_level: Literal["none", "basic", "intermediate", "advanced"] = Field(
        ..., description="Уровень английского языка"
    )
    required_english_level: Literal["none", "basic", "intermediate", "advanced"] = Field(
        ..., description="Минимальный уровень английского для вакансии"
    )


# ------------------------------------------------------------
# PYDANTIC-МОДЕЛЬ ОТВЕТА /predict
# ------------------------------------------------------------

class PredictionResponse(BaseModel):
    request_id: str
    application_id: str
    candidate_id: str
    vacancy_id: str
    match_score: float = Field(..., ge=0, le=100)
    match_level: Literal["low", "medium", "high"]
    recommendation: str
    model_version: str


# ------------------------------------------------------------
# МОДЕЛИ ОТВЕТОВ /health И /model-info
# ------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str


class ModelInfoResponse(BaseModel):
    model_name: str
    model_version: str
    model_type: str
    status: str
