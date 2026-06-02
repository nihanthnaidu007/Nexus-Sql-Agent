def compute_confidence_score(
    correction_attempts: int,
    result_quality_status: str,
    syntax_warnings: list,
    served_from_cache: bool,
    cache_similarity: float = 0.0
) -> float:
    base = 1.0
    base -= correction_attempts * 0.15
    if result_quality_status == "OVERFLOW":
        base -= 0.10
    if result_quality_status == "EMPTY":
        base -= 0.20
    for _ in syntax_warnings:
        base -= 0.05
    if served_from_cache:
        base = min(1.0, base + cache_similarity * 0.10)
    return round(max(0.0, min(1.0, base)), 3)


def confidence_badge(score: float) -> tuple:
    if score >= 0.85:
        return ("HIGH", "high")
    if score >= 0.65:
        return ("MEDIUM", "medium")
    return ("LOW", "low")
