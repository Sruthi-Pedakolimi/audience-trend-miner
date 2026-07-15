import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import review_cluster
from app.agent.schemas import Article, CandidateCluster, ReviewDecision
from app.clustering.candidate_clusterer import cluster_articles
from app.clustering.embeddings import embed_articles

MAX_CLUSTER_REVIEW_ATTEMPTS = 2


class GraphState(TypedDict):
    articles: list[Article]
    candidate_clusters: dict[str, CandidateCluster]
    pending_cluster_ids: list[str]
    cluster_reviews: dict[str, ReviewDecision]
    approved_clusters: dict[str, CandidateCluster]
    rejected_clusters: dict[str, CandidateCluster]
    cluster_review_attempts: dict[str, int]


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


def apply_review_decisions_node(state: GraphState) -> GraphState:
    approved_clusters = dict(state.get("approved_clusters", {}))
    rejected_clusters = dict(state.get("rejected_clusters", {}))
    cluster_review_attempts = dict(state.get("cluster_review_attempts", {}))
    candidate_clusters = dict(state["candidate_clusters"])
    pending_for_rereview: list[str] = []

    for cluster_id, review in state["cluster_reviews"].items():
        cluster_review_attempts[cluster_id] = (
            cluster_review_attempts.get(cluster_id, 0) + 1
        )
        cluster = candidate_clusters[cluster_id]

        if review.decision == "approve":
            approved_clusters[cluster_id] = cluster
        elif review.decision == "reject":
            rejected_clusters[cluster_id] = cluster
        elif review.decision == "remove_outliers":
            article_ids = [
                article_id
                for article_id in cluster.article_ids
                if article_id not in review.outlier_article_ids
            ]
            if article_ids:
                candidate_clusters[cluster_id] = CandidateCluster(
                    cluster_id=cluster_id,
                    article_ids=article_ids,
                )
            else:
                rejected_clusters[cluster_id] = cluster
                continue

            if cluster_review_attempts[cluster_id] >= MAX_CLUSTER_REVIEW_ATTEMPTS:
                rejected_clusters[cluster_id] = candidate_clusters[cluster_id]
            else:
                pending_for_rereview.append(cluster_id)

    return {
        "approved_clusters": approved_clusters,
        "rejected_clusters": rejected_clusters,
        "candidate_clusters": candidate_clusters,
        "pending_cluster_ids": pending_for_rereview,
        "cluster_review_attempts": cluster_review_attempts,
    }


def route_after_apply(state: GraphState) -> str:
    if state["pending_cluster_ids"]:
        return "review_clusters"
    return END


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("cluster", cluster_node)
    graph.add_node("review_clusters", review_clusters_node)
    graph.add_node("apply_review_decisions", apply_review_decisions_node)
    graph.add_edge(START, "cluster")
    graph.add_edge("cluster", "review_clusters")
    graph.add_edge("review_clusters", "apply_review_decisions")
    graph.add_conditional_edges("apply_review_decisions", route_after_apply)
    return graph.compile()


if __name__ == "__main__":
    fixture_path = Path(__file__).resolve().parents[2] / "tests/fixtures/sample_articles.json"
    raw_articles = json.loads(fixture_path.read_text())
    articles = [Article.model_validate(item) for item in raw_articles]
    article_by_id = {article.id: article for article in articles}

    app = build_graph()
    result = app.invoke(
        {
            "articles": articles,
            "candidate_clusters": {},
            "pending_cluster_ids": [],
            "cluster_reviews": {},
            "approved_clusters": {},
            "rejected_clusters": {},
            "cluster_review_attempts": {},
        }
    )

    def print_clusters(title: str, clusters: dict[str, CandidateCluster]) -> None:
        print(title)
        if not clusters:
            print("  (none)")
            print()
            return

        for cluster_id in sorted(clusters):
            cluster = clusters[cluster_id]
            titles = [article_by_id[article_id].title for article_id in cluster.article_ids]
            print(f"  {cluster_id}: {', '.join(titles)}")
        print()

    print_clusters(
        f"approved_clusters ({len(result['approved_clusters'])})",
        result["approved_clusters"],
    )
    print_clusters(
        f"rejected_clusters ({len(result['rejected_clusters'])})",
        result["rejected_clusters"],
    )
