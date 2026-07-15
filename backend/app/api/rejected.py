import json

from fastapi import APIRouter, HTTPException

from app.agent.graph import LIVE_CACHE_PATH
from app.agent.schemas import ReviewDecision

router = APIRouter()


@router.get("/rejected")
def get_rejected() -> dict:
    if not LIVE_CACHE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No cached run found at {LIVE_CACHE_PATH}",
        )

    payload = json.loads(LIVE_CACHE_PATH.read_text())
    articles_by_id = {article["id"]: article for article in payload["articles"]}
    cluster_reviews = {
        cluster_id: ReviewDecision.model_validate(review)
        for cluster_id, review in payload.get("cluster_reviews", {}).items()
    }

    rejected = []
    for cluster_id, cluster in payload["rejected_clusters"].items():
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

    return {
        "generated_at": payload["generated_at"],
        "source": payload["source"],
        "rejected": rejected,
    }
