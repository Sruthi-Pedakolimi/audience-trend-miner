from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.graph import run_graph
from app.agent.schemas import PortfolioEntry, ReviewDecision
from app.services.generate_cache import (
    list_cached_article_limits,
    load_articles_cache,
    load_generate_cache,
    save_articles_cache,
    save_generate_cache,
)
from app.services.live_articles import build_live_articles

router = APIRouter()

ARTICLE_LIMIT_OPTIONS = (10, 15, 20, 25)


class GenerateRequest(BaseModel):
    week_ending: date
    article_limit: Literal[10, 15, 20, 25] = 15
    data_mode: Literal["live", "cached"] = "live"
    force_refresh: bool = False


def _build_rejected(payload: dict) -> list[dict]:
    articles_by_id = {article["id"]: article for article in payload["articles"]}
    cluster_reviews = {
        cluster_id: ReviewDecision.model_validate(review)
        for cluster_id, review in payload.get("cluster_reviews", {}).items()
    }

    rejected = []
    for cluster_id, cluster in payload.get("rejected_clusters", {}).items():
        review = cluster_reviews.get(cluster_id)
        article_titles = [
            articles_by_id[article_id]["title"]
            for article_id in cluster["article_ids"]
            if article_id in articles_by_id
        ]
        rejected.append(
            {
                "cluster_id": cluster_id,
                "article_ids": cluster["article_ids"],
                "article_titles": article_titles,
                "decision": review.decision if review else None,
                "reason": review.reason if review else None,
            }
        )

    rejected.sort(key=lambda item: item["cluster_id"])
    return rejected


def _format_response(payload: dict, cache_status: Literal["hit", "miss"]) -> dict:
    portfolio = [
        PortfolioEntry.model_validate(entry).model_dump()
        for entry in payload["final_portfolio"]
    ]
    return {
        "generated_at": payload["generated_at"],
        "cache_status": cache_status,
        "week_ending": payload["week_ending"],
        "article_limit": payload["article_limit"],
        "data_mode": payload["data_mode"],
        "portfolio": portfolio,
        "rejected": _build_rejected(payload),
    }


def _load_articles(request: GenerateRequest) -> list:
    if request.data_mode == "live":
        articles = build_live_articles(
            end_date=request.week_ending,
            enrich_n=request.article_limit,
        )
        save_articles_cache(
            week_ending=request.week_ending,
            article_limit=request.article_limit,
            articles=articles,
        )
        return articles

    try:
        return load_articles_cache(request.week_ending, request.article_limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate")
def generate_portfolio(request: GenerateRequest) -> dict:
    if not request.force_refresh:
        cached = load_generate_cache(
            request.week_ending,
            request.article_limit,
            request.data_mode,
        )
        if cached is not None:
            return _format_response(cached, "hit")

    articles = _load_articles(request)
    result = run_graph(articles)
    save_generate_cache(
        week_ending=request.week_ending,
        article_limit=request.article_limit,
        data_mode=request.data_mode,
        articles=articles,
        final_portfolio=result["final_portfolio"],
        rejected_clusters=result["rejected_clusters"],
        cluster_reviews=result["cluster_reviews"],
    )

    cached = load_generate_cache(
        request.week_ending,
        request.article_limit,
        request.data_mode,
    )
    if cached is None:
        raise HTTPException(status_code=500, detail="Failed to save generate cache")

    return _format_response(cached, "miss")


@router.get("/cached-article-limits")
def get_cached_article_limits(week_ending: date) -> dict:
    return {
        "week_ending": week_ending.isoformat(),
        "article_limits": list_cached_article_limits(week_ending),
        "all_options": list(ARTICLE_LIMIT_OPTIONS),
    }
