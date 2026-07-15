import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import review_cluster
from app.agent.schemas import Article, CandidateCluster, ReviewDecision
from app.clustering.candidate_clusterer import cluster_articles
from app.clustering.embeddings import embed_articles


class GraphState(TypedDict):
    articles: list[Article]
    candidate_clusters: dict[str, CandidateCluster]
    pending_cluster_ids: list[str]
    cluster_reviews: dict[str, ReviewDecision]


def cluster_node(state: GraphState) -> GraphState:
    articles = state["articles"]
    embeddings = embed_articles(articles)
    clusters = cluster_articles(articles, embeddings)
    candidate_clusters = {
        cluster.cluster_id: cluster for cluster in clusters
    }

    return {
        "candidate_clusters": candidate_clusters,
        "pending_cluster_ids": list(candidate_clusters.keys()),
    }


def review_clusters_node(state: GraphState) -> GraphState:
    article_by_id = {article.id: article for article in state["articles"]}
    cluster_reviews: dict[str, ReviewDecision] = {}

    for cluster_id in state["pending_cluster_ids"]:
        cluster = state["candidate_clusters"][cluster_id]
        cluster_articles = [
            article_by_id[article_id] for article_id in cluster.article_ids
        ]
        cluster_reviews[cluster_id] = review_cluster(cluster, cluster_articles)

    return {"cluster_reviews": cluster_reviews}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("cluster", cluster_node)
    graph.add_node("review_clusters", review_clusters_node)
    graph.add_edge(START, "cluster")
    graph.add_edge("cluster", "review_clusters")
    graph.add_edge("review_clusters", END)
    return graph.compile()


if __name__ == "__main__":
    fixture_path = Path(__file__).resolve().parents[2] / "tests/fixtures/sample_articles.json"
    raw_articles = json.loads(fixture_path.read_text())
    articles = [Article.model_validate(item) for item in raw_articles]

    app = build_graph()
    result = app.invoke(
        {
            "articles": articles,
            "candidate_clusters": {},
            "pending_cluster_ids": [],
            "cluster_reviews": {},
        }
    )

    print(f"Reviewed {len(result['cluster_reviews'])} clusters\n")
    for cluster_id in sorted(result["cluster_reviews"]):
        review = result["cluster_reviews"][cluster_id]
        print(f"=== {cluster_id} ===")
        print(review.model_dump_json(indent=2))
        print()
