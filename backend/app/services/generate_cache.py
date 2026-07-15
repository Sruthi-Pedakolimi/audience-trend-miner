import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.agent.schemas import Article, CandidateCluster, PortfolioEntry, ReviewDecision

CACHE_ROOT = Path(__file__).resolve().parents[2] / "sample_outputs" / "cache"
ARTICLES_CACHE_DIR = CACHE_ROOT / "articles"


def _normalize_week_ending(week_ending: date) -> str:
    return week_ending.isoformat()


def generate_cache_path(
    week_ending: date,
    article_limit: int,
    data_mode: str,
) -> Path:
    key = (
        f"{_normalize_week_ending(week_ending)}__{article_limit}__{data_mode}.json"
    )
    return CACHE_ROOT / key


def articles_cache_path(week_ending: date, article_limit: int) -> Path:
    key = f"{_normalize_week_ending(week_ending)}__{article_limit}.json"
    return ARTICLES_CACHE_DIR / key


def load_generate_cache(
    week_ending: date,
    article_limit: int,
    data_mode: str,
) -> dict | None:
    path = generate_cache_path(week_ending, article_limit, data_mode)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_generate_cache(
    *,
    week_ending: date,
    article_limit: int,
    data_mode: str,
    articles: list[Article],
    final_portfolio: list[PortfolioEntry],
    rejected_clusters: dict[str, CandidateCluster],
    cluster_reviews: dict[str, ReviewDecision],
) -> Path:
    path = generate_cache_path(week_ending, article_limit, data_mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "week_ending": _normalize_week_ending(week_ending),
        "article_limit": article_limit,
        "data_mode": data_mode,
        "articles": [article.model_dump() for article in articles],
        "final_portfolio": [entry.model_dump() for entry in final_portfolio],
        "rejected_clusters": {
            cluster_id: cluster.model_dump()
            for cluster_id, cluster in rejected_clusters.items()
        },
        "cluster_reviews": {
            cluster_id: review.model_dump()
            for cluster_id, review in cluster_reviews.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def save_articles_cache(
    *,
    week_ending: date,
    article_limit: int,
    articles: list[Article],
) -> Path:
    path = articles_cache_path(week_ending, article_limit)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "week_ending": _normalize_week_ending(week_ending),
        "article_limit": article_limit,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "articles": [article.model_dump() for article in articles],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_articles_cache(week_ending: date, article_limit: int) -> list[Article]:
    path = articles_cache_path(week_ending, article_limit)
    if not path.exists():
        raise FileNotFoundError(
            f"No cached articles for week_ending={week_ending.isoformat()} "
            f"article_limit={article_limit}"
        )

    payload = json.loads(path.read_text())
    return [Article.model_validate(item) for item in payload["articles"]]
