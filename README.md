# Candidate Scoring API

Учебный FastAPI-сервис для предварительной оценки соответствия кандидата вакансии. Во второй версии добавлены SQLite, сквозной `request_id`, пакетная обработка, очередь и внешняя LLM.

## Возможности

- `GET /health` - проверка работоспособности;
- `GET /model-info` - сведения о модели;
- `POST /predict` - предварительная оценка отклика;
- `GET /predictions/{request_id}` - получение одного результата;
- `GET /predictions?limit=10&match_level=high` - список и фильтрация результатов;
- `GET /predictions/by-weekday` - пагинация результатов по дню недели;
- `POST /batch-predict` - явный пакетный инференс до 8 откликов;
- `POST /predict-queued` и `GET /queue-status` - очередь и dynamic batching;
- `POST /llm/chat` - запрос к OpenAI-совместимому внешнему LLM API;
- `POST /predict-with-llm` - оценка кандидата с LLM-пояснением;
- SQLite через `aiosqlite` для постоянного хранения результатов;
- структурная валидация Pydantic (`422`) и бизнес-валидация (`400`);
- автоматическая OpenAPI-документация: `/docs` и заголовки `X-Request-ID`, `X-Process-Time`.

## Запуск

```bash
nix develop
uvicorn main:app --reload
```

После запуска откройте <http://127.0.0.1:8000/docs>.

SQLite-база `candidate_scoring.db` создаётся автоматически при первом запуске и не хранится в Git.

## Пример запроса

```json
{
  "application_id": "APP-001",
  "candidate_id": "CAND-001",
  "vacancy_id": "VAC-PYTHON-01",
  "experience_years": 4,
  "required_experience_years": 3,
  "skills_match_percent": 85,
  "assessment_score": 80,
  "salary_expectation": 180000,
  "salary_budget": 220000,
  "english_level": "intermediate",
  "required_english_level": "intermediate"
}
```

## Логика оценки

`match_score` складывается из совпадения навыков (40%), результата теста (25%), опыта (20%), ожиданий по зарплате (10%) и английского языка (5%). Уровни: `high` от 75, `medium` от 50, иначе `low`.

## Проверка

```bash
nix develop --command python -c 'from main import app; print(app.openapi()["paths"].keys())'
```
