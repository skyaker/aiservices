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


# ------------------------------------------------------------
# МОДЕЛИ BATCHING И ПАГИНАЦИИ
# ------------------------------------------------------------

class BatchRequest(BaseModel):
    items: list[CandidateRequest] = Field(
        ..., min_length=1, max_length=8, description="Список откликов для пакетной оценки"
    )


class BatchPredictionResponse(BaseModel):
    request_id: str
    batch_size: int
    processing_time_ms: float
    items: list[PredictionResponse]


class PaginationMeta(BaseModel):
    weekday: str
    current_page: int
    per_page: int
    total_pages: int
    total_items: int
    next_page: str | None
    prev_page: str | None


class PaginatedPredictionsResponse(BaseModel):
    data: list[PredictionResponse]
    meta: PaginationMeta


# ------------------------------------------------------------
# МОДЕЛИ ДЛЯ ВНЕШНЕЙ LLM
# ------------------------------------------------------------

class LLMChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)
    model: str = Field(default="auto", min_length=1)
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_tokens: int = Field(default=300, ge=1, le=2000)


class LLMChatResponse(BaseModel):
    request_id: str
    requested_model: str
    returned_model: str | None
    answer: str
    reasoning: str | None = None
    finish_reason: str | None = None
    usage: dict | None = None
    latency_ms: float


class PredictWithLLMResponse(BaseModel):
    prediction: PredictionResponse
    llm: LLMChatResponse
