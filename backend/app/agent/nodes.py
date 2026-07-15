import json
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

from app.agent.schemas import (
    Article,
    AudienceEntry,
    BuyingPowerRubric,
    CandidateCluster,
    ClusterMetrics,
    ReviewDecision,
)

MODEL = "gpt-4o-mini"
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

REVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["approve", "reject", "remove_outliers"],
        },
        "reason": {"type": "string"},
        "outlier_article_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["decision", "reason", "outlier_article_ids"],
    "additionalProperties": False,
}

SYNTHESIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "trending_description": {"type": "string"},
        "buying_power": {
            "type": "object",
            "properties": {
                "purchase_value": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "purchase_immediacy": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "brand_category_breadth": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "trend_durability": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "overall_buying_power": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "rationale": {"type": "string"},
            },
            "required": [
                "purchase_value",
                "purchase_immediacy",
                "brand_category_breadth",
                "trend_durability",
                "overall_buying_power",
                "rationale",
            ],
            "additionalProperties": False,
        },
        "brand_categories": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["name", "trending_description", "buying_power", "brand_categories"],
    "additionalProperties": False,
}


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    config = dotenv_values(ENV_PATH)
    api_key = config.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    client_kwargs: dict[str, str] = {
        "api_key": api_key,
        "base_url": config.get("OPENAI_BASE_URL") or "https://api.openai.com/v1",
    }
    return OpenAI(**client_kwargs)


def _cluster_prompt(cluster: CandidateCluster, articles: list[Article]) -> str:
    article_lines = []
    for article in articles:
        categories = ", ".join(article.categories)
        article_lines.append(
            f"- id: {article.id}\n"
            f"  title: {article.title}\n"
            f"  summary: {article.summary}\n"
            f"  categories: {categories}\n"
            f"  pageviews: {article.pageviews}"
        )

    return (
        "You are reviewing a candidate audience cluster for commercial targeting.\n"
        "A coherent commercial audience is a set of articles whose readers share a "
        "clear, marketable interest that advertisers could target as one segment.\n\n"
        "Decide one of:\n"
        "- approve: the cluster is coherent enough to use as a commercial audience\n"
        "- reject: the cluster mixes unrelated interests or is not commercially viable\n"
        "- remove_outliers: most articles fit, but one or more do not belong; "
        "list their ids in outlier_article_ids\n\n"
        "Always explain your reasoning in reason. "
        "Use an empty outlier_article_ids list unless decision is remove_outliers.\n\n"
        f"Cluster id: {cluster.cluster_id}\n\n"
        "Articles:\n"
        + "\n".join(article_lines)
    )


def review_cluster(cluster: CandidateCluster, articles: list[Article]) -> ReviewDecision:
    response = _get_client().chat.completions.create(
        model=MODEL,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "review_decision",
                "schema": REVIEW_RESPONSE_SCHEMA,
                "strict": True,
            },
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You review article clusters for commercial audience viability. "
                    "Respond only with JSON matching the requested schema."
                ),
            },
            {"role": "user", "content": _cluster_prompt(cluster, articles)},
        ],
    )

    payload = json.loads(response.choices[0].message.content)
    return ReviewDecision(
        cluster_id=cluster.cluster_id,
        decision=payload["decision"],
        reason=payload["reason"],
        outlier_article_ids=payload.get("outlier_article_ids", []),
    )


def _synthesis_prompt(
    cluster: CandidateCluster,
    articles: list[Article],
    metrics: ClusterMetrics,
) -> str:
    article_lines = []
    for article in articles:
        categories = ", ".join(article.categories)
        article_lines.append(
            f"- {article.title}: {article.summary} "
            f"(categories: {categories}, pageviews: {article.pageviews:,})"
        )

    return (
        "Write a commercial audience profile for this approved article cluster.\n"
        "The audience should sound specific and actionable for media planners, "
        "not generic.\n\n"
        "Provide:\n"
        "- name: a concise, marketable audience segment name\n"
        "- trending_description: 2-3 sentences on why this audience is trending now, "
        "grounded in the articles\n"
        "- buying_power: a structured rubric with ratings of low, medium, or high for:\n"
        "  purchase_value, purchase_immediacy, brand_category_breadth, "
        "trend_durability, and overall_buying_power, plus a short rationale "
        "summarizing the commercial case\n"
        "- brand_categories: 3-5 relevant advertiser categories or verticals\n\n"
        "Use the supplied metrics for context only. Do not calculate or output "
        "traffic_share or size_index.\n\n"
        f"Cluster id: {cluster.cluster_id}\n"
        f"traffic_share: {metrics.traffic_share:.4f} "
        f"({metrics.traffic_share * 100:.1f}% of approved audience traffic)\n"
        f"size_index: {metrics.size_index:.1f} (log-normalized reach score, 0-100)\n"
        f"total_pageviews: {metrics.total_pageviews:,}\n\n"
        "Articles:\n"
        + "\n".join(article_lines)
    )


def synthesize_audience(
    cluster: CandidateCluster,
    articles: list[Article],
    metrics: ClusterMetrics,
) -> AudienceEntry:
    response = _get_client().chat.completions.create(
        model=MODEL,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "audience_entry",
                "schema": SYNTHESIS_RESPONSE_SCHEMA,
                "strict": True,
            },
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You write audience intelligence briefs for advertising teams. "
                    "Be concrete, insight-led, and grounded in the supplied articles. "
                    "Respond only with JSON matching the requested schema."
                ),
            },
            {
                "role": "user",
                "content": _synthesis_prompt(cluster, articles, metrics),
            },
        ],
    )

    payload = json.loads(response.choices[0].message.content)
    buying_power_payload = payload["buying_power"]
    return AudienceEntry(
        cluster_id=cluster.cluster_id,
        name=payload["name"],
        trending_description=payload["trending_description"],
        buying_power=BuyingPowerRubric.model_validate(buying_power_payload),
        brand_categories=payload["brand_categories"],
        traffic_share=metrics.traffic_share,
        size_index=metrics.size_index,
    )


if __name__ == "__main__":
    from app.clustering.cluster_metrics import (
        approved_clusters_from_reviews,
        compute_cluster_metrics,
    )

    fixture_path = Path(__file__).resolve().parents[2] / "tests/fixtures/sample_articles.json"
    raw_articles = json.loads(fixture_path.read_text())
    articles = [Article.model_validate(item) for item in raw_articles]
    article_by_id = {article.id: article for article in articles}

    candidate_clusters = [
        CandidateCluster(
            cluster_id="cl-001",
            article_ids=["art-001", "art-002", "art-003", "art-004"],
        ),
        CandidateCluster(
            cluster_id="cl-002",
            article_ids=["art-005", "art-006", "art-007"],
        ),
        CandidateCluster(
            cluster_id="cl-003",
            article_ids=["art-008", "art-009"],
        ),
        CandidateCluster(
            cluster_id="cl-004",
            article_ids=["art-010"],
        ),
        CandidateCluster(
            cluster_id="cl-005",
            article_ids=["art-011"],
        ),
        CandidateCluster(
            cluster_id="cl-006",
            article_ids=["art-012"],
        ),
    ]
    review_decisions = [
        ReviewDecision(
            cluster_id="cl-001",
            decision="remove_outliers",
            reason="E-bike is transport-focused, not home energy.",
            outlier_article_ids=["art-003"],
        ),
        ReviewDecision(
            cluster_id="cl-002",
            decision="approve",
            reason="Coherent entertainment and pop-culture audience.",
        ),
        ReviewDecision(
            cluster_id="cl-003",
            decision="reject",
            reason="Disaster coverage and election politics are unrelated.",
        ),
        ReviewDecision(
            cluster_id="cl-004",
            decision="approve",
            reason="Single-topic home baking audience.",
        ),
        ReviewDecision(
            cluster_id="cl-005",
            decision="approve",
            reason="Single-topic deep-sea science audience.",
        ),
        ReviewDecision(
            cluster_id="cl-006",
            decision="approve",
            reason="Single-topic stamp-collecting hobby audience.",
        ),
    ]

    approved_clusters = approved_clusters_from_reviews(
        candidate_clusters, review_decisions
    )
    metrics_by_id = {
        metric.cluster_id: metric
        for metric in compute_cluster_metrics(approved_clusters, articles)
    }

    cluster = next(c for c in approved_clusters if c.cluster_id == "cl-001")
    cluster_articles = [article_by_id[article_id] for article_id in cluster.article_ids]
    entry = synthesize_audience(
        cluster, cluster_articles, metrics_by_id[cluster.cluster_id]
    )

    print("=== cl-001 audience entry ===")
    print(entry.model_dump_json(indent=2))
    print()
