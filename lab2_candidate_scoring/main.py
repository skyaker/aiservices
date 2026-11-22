import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from database import get_predictions, get_predictions_by_request_id, get_predictions_by_weekday, init_db, make_pagination_links, save_predictions
from llm import build_explanation_prompt, call_llm
from queue_worker import INFERENCE_TIMEOUT_SECONDS, MAX_BATCH_SIZE, MAX_BATCH_WAIT_MS, QUEUE_MAX_SIZE, dynamic_queue
from schemas import BatchPredictionResponse, BatchRequest, CandidateRequest, HealthResponse, LLMChatRequest, LLMChatResponse, ModelInfoResponse, PaginatedPredictionsResponse, PaginationMeta, PredictionResponse, PredictWithLLMResponse
from services import make_prediction, validate_business_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = "candidate-match-scoring-model"
MODEL_VERSION = "2.0.0"
MODEL_TYPE = "rule-based candidate matching"
MODEL_READY = True


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await dynamic_queue.start()
    yield
    await dynamic_queue.stop()


app = FastAPI(
    title="Candidate Scoring API",
    description="REST API для предварительной оценки соответствия кандидата вакансии.",
    version=MODEL_VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(round(time.perf_counter() - started_at, 6))
    logger.info("HTTP request | request_id=%s | method=%s | path=%s | status=%s", request_id, request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "request_id": getattr(request.state, "request_id", None)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors(), "request_id": getattr(request.state, "request_id", None)})


def ensure_model_ready() -> None:
    if not MODEL_READY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model is unavailable")


def ensure_business_rules(data: CandidateRequest) -> None:
    error = validate_business_rules(data)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)


async def create_and_save_prediction(request_id: str, data: CandidateRequest, source: str) -> PredictionResponse:
    ensure_model_ready()
    ensure_business_rules(data)
    try:
        result = await asyncio.wait_for(asyncio.to_thread(make_prediction, request_id, data), timeout=INFERENCE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Inference timed out") from exc
    await save_predictions([result], source=source)
    return result


@app.get("/health", response_model=HealthResponse, summary="Проверка состояния API")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/model-info", response_model=ModelInfoResponse, summary="Информация о модели")
async def model_info() -> ModelInfoResponse:
    return ModelInfoResponse(model_name=MODEL_NAME, model_version=MODEL_VERSION, model_type=MODEL_TYPE, status="ready" if MODEL_READY else "unavailable")


@app.post("/predict", response_model=PredictionResponse, summary="Оценить соответствие кандидата")
async def predict(request: Request, payload: CandidateRequest) -> PredictionResponse:
    return await create_and_save_prediction(request.state.request_id, payload, source="single")


@app.post("/batch-predict", response_model=BatchPredictionResponse, summary="Пакетная оценка откликов")
async def batch_predict(request: Request, payload: BatchRequest) -> BatchPredictionResponse:
    ensure_model_ready()
    for item in payload.items:
        ensure_business_rules(item)
    started_at = time.perf_counter()
    request_id = request.state.request_id
    try:
        results = await asyncio.wait_for(asyncio.gather(*[asyncio.to_thread(make_prediction, request_id, item) for item in payload.items]), timeout=INFERENCE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Batch inference timed out") from exc
    await save_predictions(results, source="explicit_batch")
    return BatchPredictionResponse(request_id=request_id, batch_size=len(results), processing_time_ms=round((time.perf_counter() - started_at) * 1000, 2), items=results)


@app.post("/predict-queued", response_model=PredictionResponse, summary="Оценка через очередь dynamic batching")
async def predict_queued(request: Request, payload: CandidateRequest) -> PredictionResponse:
    ensure_model_ready()
    ensure_business_rules(payload)
    try:
        return await dynamic_queue.submit(request.state.request_id, payload)
    except OverflowError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Inference queue is full") from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Queued inference timed out") from exc


@app.get("/queue-status", summary="Статус очереди инференса")
async def queue_status() -> dict:
    return {"queue_size": dynamic_queue.queue.qsize(), "queue_max_size": QUEUE_MAX_SIZE, "max_batch_size": MAX_BATCH_SIZE, "max_batch_wait_ms": MAX_BATCH_WAIT_MS, "inference_timeout_seconds": INFERENCE_TIMEOUT_SECONDS}


@app.post("/llm/chat", response_model=LLMChatResponse, summary="Отправить запрос внешней LLM")
async def llm_chat(request: Request, payload: LLMChatRequest) -> LLMChatResponse:
    return await call_llm(request.state.request_id, payload)


@app.post("/predict-with-llm", response_model=PredictWithLLMResponse, summary="Оценка кандидата с пояснением LLM")
async def predict_with_llm(request: Request, payload: CandidateRequest) -> PredictWithLLMResponse:
    prediction = await create_and_save_prediction(request.state.request_id, payload, source="with_llm")
    llm_response = await call_llm(request.state.request_id, LLMChatRequest(prompt=build_explanation_prompt(prediction)))
    return PredictWithLLMResponse(prediction=prediction, llm=llm_response)


@app.get("/predictions", response_model=list[PredictionResponse], summary="Список сохраненных прогнозов")
async def list_predictions(limit: int = Query(default=10, ge=1, le=100), match_level: Literal["low", "medium", "high"] | None = None) -> list[PredictionResponse]:
    return await get_predictions(limit=limit, match_level=match_level)


@app.get("/requests/{request_id}/predictions", response_model=list[PredictionResponse], summary="Все прогнозы batch-запроса")
async def get_request_predictions(request_id: str) -> list[PredictionResponse]:
    results = await get_predictions_by_request_id(request_id)
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Predictions not found")
    return results


@app.get("/predictions/by-weekday", response_model=PaginatedPredictionsResponse, summary="Пагинация прогнозов по дню недели")
async def predictions_by_weekday(
    weekday: Literal["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=5, ge=1, le=100),
) -> PaginatedPredictionsResponse:
    data, total = await get_predictions_by_weekday(weekday, page, per_page)
    total_pages, next_page, prev_page = make_pagination_links(weekday, page, per_page, total)
    if page > total_pages and total > 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return PaginatedPredictionsResponse(data=data, meta=PaginationMeta(weekday=weekday, current_page=page, per_page=per_page, total_pages=total_pages, total_items=total, next_page=next_page, prev_page=prev_page))


@app.get("/predictions/{request_id}", response_model=PredictionResponse, summary="Один прогноз по request_id")
async def get_prediction(request_id: str) -> PredictionResponse:
    results = await get_predictions_by_request_id(request_id)
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    if len(results) > 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request ID belongs to batch; use /requests/{request_id}/predictions")
    return results[0]


@app.get("/", summary="Корневой endpoint")
async def root() -> dict:
    return {"service": "Candidate Scoring API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
