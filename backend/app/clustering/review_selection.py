import logging

from app.agent.schemas import Article, CandidateCluster

logger = logging.getLogger(__name__)

MAX_CLUSTERS_FOR_REVIEW = 8


def _cluster_traffic(cluster: CandidateCluster, article_by_id: dict[str, Article]) -> int:
    return sum(article_by_id[article_id].pageviews for article_id in cluster.article_ids)


def bound_clusters_for_review(
    clusters: list[CandidateCluster],
    articles: list[Article],
) -> tuple[list[str], list[CandidateCluster]]:
    article_by_id = {article.id: article for article in articles}
    ranked = sorted(
        clusters,
        key=lambda cluster: _cluster_traffic(cluster, article_by_id),
        reverse=True,
    )

    if len(ranked) <= MAX_CLUSTERS_FOR_REVIEW:
        selected = ranked
    else:
        selected: list[CandidateCluster] = []

        for cluster in ranked:
            if len(cluster.article_ids) > 1:
                selected.append(cluster)
            if len(selected) >= MAX_CLUSTERS_FOR_REVIEW:
                break

        if len(selected) < MAX_CLUSTERS_FOR_REVIEW:
            for cluster in ranked:
                if len(cluster.article_ids) == 1 and cluster not in selected:
                    selected.append(cluster)
                if len(selected) >= MAX_CLUSTERS_FOR_REVIEW:
                    break

        selected = selected[:MAX_CLUSTERS_FOR_REVIEW]

    selected_ids = {cluster.cluster_id for cluster in selected}
    dropped = [cluster for cluster in ranked if cluster.cluster_id not in selected_ids]

    for cluster in dropped:
        traffic = _cluster_traffic(cluster, article_by_id)
        logger.info(
            "Dropped cluster %s from review queue (%d articles, %s pageviews)",
            cluster.cluster_id,
            len(cluster.article_ids),
            f"{traffic:,}",
        )

    return [cluster.cluster_id for cluster in selected], dropped
