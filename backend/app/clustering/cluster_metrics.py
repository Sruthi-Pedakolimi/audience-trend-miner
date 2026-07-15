import json
import math
from pathlib import Path

from app.agent.schemas import Article, CandidateCluster, ClusterMetrics, ReviewDecision


def _cluster_pageviews(cluster: CandidateCluster, pageviews_by_id: dict[str, int]) -> int:
    return sum(pageviews_by_id[article_id] for article_id in cluster.article_ids)


def _log_normalize(values: list[float]) -> list[float]:
    if not values:
        return []

    if len(values) == 1:
        return [100.0]

    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        return [100.0 for _ in values]

    scale = max_value - min_value
    return [((value - min_value) / scale) * 100 for value in values]


def compute_cluster_metrics(
    approved_clusters: list[CandidateCluster],
    articles: list[Article],
) -> list[ClusterMetrics]:
    if not approved_clusters:
        return []

    pageviews_by_id = {article.id: article.pageviews for article in articles}
    cluster_pageviews = [
        _cluster_pageviews(cluster, pageviews_by_id) for cluster in approved_clusters
    ]
    total_pageviews = sum(cluster_pageviews)

    log_pageviews = [math.log1p(pageviews) for pageviews in cluster_pageviews]
    size_indices = _log_normalize(log_pageviews)

    return [
        ClusterMetrics(
            cluster_id=cluster.cluster_id,
            traffic_share=(
                cluster_pageview / total_pageviews if total_pageviews else 0.0
            ),
            size_index=size_index,
            total_pageviews=cluster_pageview,
        )
        for cluster, cluster_pageview, size_index in zip(
            approved_clusters, cluster_pageviews, size_indices
        )
    ]


def approved_clusters_from_reviews(
    clusters: list[CandidateCluster],
    decisions: list[ReviewDecision],
) -> list[CandidateCluster]:
    decisions_by_id = {decision.cluster_id: decision for decision in decisions}

    approved: list[CandidateCluster] = []
    for cluster in clusters:
        decision = decisions_by_id.get(cluster.cluster_id)
        if decision is None or decision.decision == "reject":
            continue

        article_ids = [
            article_id
            for article_id in cluster.article_ids
            if article_id not in decision.outlier_article_ids
        ]
        if article_ids:
            approved.append(
                CandidateCluster(cluster_id=cluster.cluster_id, article_ids=article_ids)
            )

    return approved


if __name__ == "__main__":
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
    metrics = compute_cluster_metrics(approved_clusters, articles)

    total_pageviews = sum(metric.total_pageviews for metric in metrics)
    print(f"Approved clusters: {len(approved_clusters)}")
    print(f"Total pageviews across approved set: {total_pageviews:,}\n")

    for cluster, metric in zip(approved_clusters, metrics):
        titles = [article_by_id[article_id].title for article_id in cluster.article_ids]
        print(f"{metric.cluster_id}")
        print(f"  articles: {', '.join(titles)}")
        print(f"  total_pageviews: {metric.total_pageviews:,}")
        print(f"  traffic_share: {metric.traffic_share:.4f} ({metric.traffic_share * 100:.1f}%)")
        print(f"  size_index: {metric.size_index:.1f}")
        print()
