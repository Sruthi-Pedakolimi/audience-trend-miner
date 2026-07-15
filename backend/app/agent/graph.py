import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.schemas import Article, CandidateCluster
from app.clustering.candidate_clusterer import cluster_articles
from app.clustering.embeddings import embed_articles


class GraphState(TypedDict):
    articles: list[Article]
    candidate_clusters: dict[str, CandidateCluster]


def cluster_node(state: GraphState) -> GraphState:
    articles = state["articles"]
    embeddings = embed_articles(articles)
    clusters = cluster_articles(articles, embeddings)

    return {
        "candidate_clusters": {
            cluster.cluster_id: cluster for cluster in clusters
        }
    }


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("cluster", cluster_node)
    graph.add_edge(START, "cluster")
    graph.add_edge("cluster", END)
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
        }
    )

    print(f"Found {len(result['candidate_clusters'])} candidate clusters\n")
    for cluster_id in sorted(result["candidate_clusters"]):
        cluster = result["candidate_clusters"][cluster_id]
        print(f"{cluster.cluster_id} ({len(cluster.article_ids)} articles)")
        for article_id in cluster.article_ids:
            print(f"  - {article_by_id[article_id].title}")
        print()
