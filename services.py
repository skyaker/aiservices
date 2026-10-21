from schemas import CandidateRequest, PredictionResponse


# ------------------------------------------------------------
# БИЗНЕС-ЛОГИКА И ПОСТПРОЦЕССИНГ
# ------------------------------------------------------------

def get_match_level(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def get_recommendation(level: str) -> str:
    recommendations = {
        "high": "Пригласить кандидата на интервью с нанимающим менеджером",
        "medium": "Провести первичное HR-интервью и уточнить соответствие требованиям",
        "low": "Не рекомендовать к следующему этапу по текущей вакансии",
    }
    return recommendations[level]


def validate_business_rules(data: CandidateRequest) -> str | None:
    if data.salary_expectation > data.salary_budget * 2:
        return "Salary expectation cannot exceed the vacancy budget by more than two times"
    if data.required_experience_years > 0 and data.experience_years == 0:
        return "Candidate has no relevant experience for a vacancy requiring experience"
    return None


def make_prediction(request_id: str, data: CandidateRequest) -> PredictionResponse:
    from model import calculate_match_score

    score = calculate_match_score(data)
    level = get_match_level(score)
    return PredictionResponse(
        request_id=request_id,
        application_id=data.application_id,
        candidate_id=data.candidate_id,
        vacancy_id=data.vacancy_id,
        match_score=score,
        match_level=level,
        recommendation=get_recommendation(level),
        model_version="2.0.0",
    )
