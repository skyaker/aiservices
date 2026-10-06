from schemas import CandidateRequest

# ------------------------------------------------------------
# УСЛОВНАЯ МОДЕЛЬ МАШИННОГО ОБУЧЕНИЯ
# ------------------------------------------------------------

ENGLISH_LEVELS = {"none": 0, "basic": 1, "intermediate": 2, "advanced": 3}


def calculate_match_score(data: CandidateRequest) -> float:
    # Навыки - 40%, тест - 25%, опыт - 20%,
    # зарплатные ожидания - 10%, английский - 5%.
    experience_ratio = min(data.experience_years / max(data.required_experience_years, 1), 1)
    salary_ratio = min(data.salary_budget / data.salary_expectation, 1)
    english_ratio = min(
        ENGLISH_LEVELS[data.english_level] / max(ENGLISH_LEVELS[data.required_english_level], 1),
        1,
    )

    score = (
        data.skills_match_percent * 0.40
        + data.assessment_score * 0.25
        + experience_ratio * 100 * 0.20
        + salary_ratio * 100 * 0.10
        + english_ratio * 100 * 0.05
    )
    return round(min(score, 100), 2)
