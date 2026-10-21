import time

import httpx
from fastapi import HTTPException, status

from schemas import LLMChatRequest, LLMChatResponse, PredictionResponse

LLM_BASE_URL = "https://vireonix.ai/v1"
LLM_TIMEOUT_SECONDS = 60.0


async def call_llm(request_id: str, payload: LLMChatRequest) -> LLMChatResponse:
    started_at = time.perf_counter()
    body = {
        "model": payload.model,
        "messages": [{"role": "user", "content": payload.prompt}],
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{LLM_BASE_URL}/chat/completions", json=body)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="LLM request timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM provider is unavailable") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM provider returned an error")
    try:
        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        answer = message["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid LLM provider response") from exc

    return LLMChatResponse(
        request_id=request_id,
        requested_model=payload.model,
        returned_model=data.get("model"),
        answer=answer,
        reasoning=message.get("reasoning") or message.get("reasoning_content"),
        finish_reason=choice.get("finish_reason"),
        usage=data.get("usage"),
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )


def build_explanation_prompt(prediction: PredictionResponse) -> str:
    return (
        "Сформируй краткое нейтральное объяснение для HR-специалиста на русском языке. "
        "Не принимай окончательное кадровое решение и не добавляй новые факты. "
        f"Оценка соответствия: {prediction.match_score}; уровень: {prediction.match_level}; "
        f"рекомендация сервиса: {prediction.recommendation}."
    )
