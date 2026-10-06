# Candidate Scoring API

Учебный FastAPI-сервис для предварительной оценки соответствия кандидата вакансии. Он возвращает прозрачный балл соответствия и рекомендацию для HR-специалиста; окончательное кадровое решение сервис не принимает.

## Возможности

- `GET /health` - проверка работоспособности;
- `GET /model-info` - сведения о модели;
- `POST /predict` - предварительная оценка отклика;
- `GET /predictions/{request_id}` - получение одного результата;
- `GET /predictions?limit=10&match_level=high` - список и фильтрация результатов;
- структурная валидация Pydantic (`422`) и бизнес-валидация (`400`);
- автоматическая OpenAPI-документация: `/docs`.

## Запуск

```bash
nix develop
uvicorn main:app --reload
```

После запуска откройте <http://127.0.0.1:8000/docs>.

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

## Тесты

```bash
nix develop --command pytest -q
```
