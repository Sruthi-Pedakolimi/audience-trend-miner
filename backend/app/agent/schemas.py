from typing import Literal

from pydantic import BaseModel, Field

RatingLevel = Literal["low", "medium", "high"]


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
    decision: Literal["approve", "reject", "remove_outliers"]
    reason: str
    outlier_article_ids: list[str] = []


class ReviewRepair(BaseModel):
    article_id: str
    article_title: str
    reason: str


class ClusterMetrics(BaseModel):
    cluster_id: str
    traffic_share: float
    size_index: float
    total_pageviews: int


class BuyingPowerRubric(BaseModel):
    purchase_value: RatingLevel
    purchase_immediacy: RatingLevel
    brand_category_breadth: RatingLevel
    trend_durability: RatingLevel
    overall_buying_power: RatingLevel
    rationale: str


class AudienceEntry(BaseModel):
    cluster_id: str
    name: str
    trending_description: str
    buying_power: BuyingPowerRubric
    brand_categories: list[str]
    traffic_share: float
    size_index: float


class EditorialScores(BaseModel):
    cluster_coherence: int = Field(ge=1, le=5)
    commercial_relevance: int = Field(ge=1, le=5)
    evidence_grounding: int = Field(ge=1, le=5)
    audience_specificity: int = Field(ge=1, le=5)
    buying_power_justification: int = Field(ge=1, le=5)


class EditorialReview(BaseModel):
    cluster_id: str
    scores: EditorialScores
    decision: Literal["approve", "revise"]
    feedback: str


class PortfolioEntry(BaseModel):
    cluster_id: str
    cluster: CandidateCluster
    metrics: ClusterMetrics
    entry: AudienceEntry
    editorial_review: EditorialReview
    review_repairs: list[ReviewRepair] = []
