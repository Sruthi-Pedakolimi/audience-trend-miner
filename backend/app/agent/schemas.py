from typing import Literal

from pydantic import BaseModel


class Article(BaseModel):
    id: str
    title: str
    summary: str
    categories: list[str]
    pageviews: int


class CandidateCluster(BaseModel):
    cluster_id: str
    article_ids: list[str]


class ReviewDecision(BaseModel):
    cluster_id: str
    decision: Literal["approve", "reject"]
    reason: str
