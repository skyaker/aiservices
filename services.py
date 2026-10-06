# ------------------------------------------------------------
# ПОСТПРОЦЕССИНГ
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
