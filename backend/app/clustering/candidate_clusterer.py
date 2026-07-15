import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from app.agent.schemas import Article, CandidateCluster

DEFAULT_DISTANCE_THRESHOLD = 0.85


def cluster_articles(
    articles: list[Article],
    embeddings: np.ndarray,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> list[CandidateCluster]:
    if len(articles) == 0:
        return []

    if len(articles) == 1:
        return [CandidateCluster(cluster_id="cl-001", article_ids=[articles[0].id])]

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(embeddings)

    groups: dict[int, list[str]] = defaultdict(list)
    for article, label in zip(articles, labels):
        groups[int(label)].append(article.id)

    return [
        CandidateCluster(
            cluster_id=f"cl-{index:03d}",
            article_ids=article_ids,
        )
        for index, article_ids in enumerate(groups.values(), start=1)
    ]


if __name__ == "__main__":
    from app.clustering.embeddings import embed_articles

    fixture_path = Path(__file__).resolve().parents[2] / "tests/fixtures/sample_articles.json"
    raw_articles = json.loads(fixture_path.read_text())
    articles = [Article.model_validate(item) for item in raw_articles]
    article_by_id = {article.id: article for article in articles}

    embeddings = embed_articles(articles)
    clusters = cluster_articles(articles, embeddings)

    print(f"Distance threshold: {DEFAULT_DISTANCE_THRESHOLD}")
    print(f"Found {len(clusters)} clusters\n")

    for cluster in clusters:
        print(f"{cluster.cluster_id} ({len(cluster.article_ids)} articles)")
        for article_id in cluster.article_ids:
            print(f"  - {article_by_id[article_id].title}")
        print()
