import logging
import time
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, status

# ------------------------------------------------------------
# ИМПОРТ МОДУЛЕЙ ПРИЛОЖЕНИЯ
# ------------------------------------------------------------

from model import calculate_match_score
from schemas import CandidateRequest, HealthResponse, ModelInfoResponse, PredictionResponse
from services import get_match_level, get_recommendation
from storage import predictions

# ------------------------------------------------------------
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# FASTAPI-ПРИЛОЖЕНИЕ И КОНСТАНТЫ
# ------------------------------------------------------------

MODEL_NAME = "candidate-match-scoring-model"
MODEL_VERSION = "1.0.0"
MODEL_TYPE = "rule-based candidate matching"
MODEL_READY = True

app = FastAPI(
    title="Candidate Scoring API",
    description=(
        "Учебный REST API для предварительной оценки соответствия кандидата вакансии. "
        "Результат носит рекомендательный характер и не заменяет решение HR-специалиста."
    ),
    version=MODEL_VERSION,
)

# ------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round(time.perf_counter() - start_time, 6))
    return response


# ------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, summary="Проверка состояния API")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/model-info", response_model=ModelInfoResponse, summary="Информация о модели")
def model_info() -> ModelInfoResponse:
    return ModelInfoResponse(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        model_type=MODEL_TYPE,
        status="ready" if MODEL_READY else "unavailable",
    )


@app.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Оценить соответствие кандидата вакансии",
)
def predict(request: CandidateRequest) -> PredictionResponse:
    if not MODEL_READY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model is unavailable")

    # БИЗНЕС-ВАЛИДАЦИЯ
    if request.salary_expectation > request.salary_budget * 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Salary expectation cannot exceed the vacancy budget by more than two times",
        )
    if request.required_experience_years > 0 and request.experience_years == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has no relevant experience for a vacancy requiring experience",
        )

    score = calculate_match_score(request)
    level = get_match_level(score)
    result = PredictionResponse(
        request_id=str(uuid.uuid4()),
        application_id=request.application_id,
        candidate_id=request.candidate_id,
        vacancy_id=request.vacancy_id,
        match_score=score,
        match_level=level,
        recommendation=get_recommendation(level),
        model_version=MODEL_VERSION,
    )
    predictions[result.request_id] = result
    logger.info(
        "Candidate scored | request_id=%s | application_id=%s | match_score=%s",
        result.request_id,
        result.application_id,
        result.match_score,
    )
    return result


@app.get("/predictions", response_model=list[PredictionResponse], summary="Список результатов скоринга")
def get_predictions(
    limit: int = Query(default=10, ge=1, le=100, description="Максимальное число результатов"),
    match_level: Literal["low", "medium", "high"] | None = Query(
        default=None, description="Фильтр по уровню соответствия"
    ),
) -> list[PredictionResponse]:
    values = list(predictions.values())
    if match_level is not None:
        values = [item for item in values if item.match_level == match_level]
    return values[:limit]


@app.get(
    "/predictions/{request_id}",
    response_model=PredictionResponse,
    summary="Получить результат по идентификатору запроса",
)
def get_prediction(request_id: str) -> PredictionResponse:
    result = predictions.get(request_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
