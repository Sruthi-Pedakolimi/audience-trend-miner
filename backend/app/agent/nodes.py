import json
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

from app.agent.schemas import Article, CandidateCluster, ReviewDecision

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


if __name__ == "__main__":
    fixture_path = Path(__file__).resolve().parents[2] / "tests/fixtures/sample_articles.json"
    raw_articles = json.loads(fixture_path.read_text())
    articles = [Article.model_validate(item) for item in raw_articles]
    article_by_id = {article.id: article for article in articles}

    test_clusters = [
        CandidateCluster(
            cluster_id="cl-001",
            article_ids=["art-001", "art-002", "art-003", "art-004"],
        ),
        CandidateCluster(
            cluster_id="cl-003",
            article_ids=["art-008", "art-009"],
        ),
    ]

    for cluster in test_clusters:
        cluster_articles = [article_by_id[article_id] for article_id in cluster.article_ids]
        decision = review_cluster(cluster, cluster_articles)
        print(f"=== {cluster.cluster_id} ===")
        print(decision.model_dump_json(indent=2))
        print()
