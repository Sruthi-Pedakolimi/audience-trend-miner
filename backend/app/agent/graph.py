import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import critique_entry, review_cluster, synthesize_audience
from app.agent.schemas import (
    Article,
    AudienceEntry,
    CandidateCluster,
    ClusterMetrics,
    EditorialReview,
    PortfolioEntry,
    ReviewDecision,
)
from app.clustering.cluster_metrics import compute_cluster_metrics
from app.clustering.candidate_clusterer import cluster_articles
from app.clustering.embeddings import embed_articles

MAX_CLUSTER_REVIEW_ATTEMPTS = 2
LIVE_CACHE_PATH = Path(__file__).resolve().parents[2] / "sample_outputs" / "live_run.json"


class GraphState(TypedDict):
    articles: list[Article]
    candidate_clusters: dict[str, CandidateCluster]
    pending_cluster_ids: list[str]
    cluster_reviews: dict[str, ReviewDecision]
    approved_clusters: dict[str, CandidateCluster]
    rejected_clusters: dict[str, CandidateCluster]
    cluster_review_attempts: dict[str, int]
    cluster_metrics: dict[str, ClusterMetrics]
    audience_entries: dict[str, AudienceEntry]
    editorial_reviews: dict[str, EditorialReview]
    final_portfolio: list[PortfolioEntry]


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
    cluster_reviews = dict(state.get("cluster_reviews", {}))

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


def metrics_node(state: GraphState) -> GraphState:
    approved_clusters = [
        state["approved_clusters"][cluster_id]
        for cluster_id in sorted(state["approved_clusters"])
    ]
    metrics_list = compute_cluster_metrics(approved_clusters, state["articles"])

    return {
        "cluster_metrics": {
            metrics.cluster_id: metrics for metrics in metrics_list
        }
    }


def synthesize_node(state: GraphState) -> GraphState:
    article_by_id = {article.id: article for article in state["articles"]}
    audience_entries: dict[str, AudienceEntry] = {}

    for cluster_id in sorted(state["approved_clusters"]):
        cluster = state["approved_clusters"][cluster_id]
        cluster_articles = [
            article_by_id[article_id] for article_id in cluster.article_ids
        ]
        metrics = state["cluster_metrics"][cluster_id]
        audience_entries[cluster_id] = synthesize_audience(
            cluster, cluster_articles, metrics
        )

    return {"audience_entries": audience_entries}


def critique_and_revise_once_node(state: GraphState) -> GraphState:
    article_by_id = {article.id: article for article in state["articles"]}
    audience_entries = dict(state["audience_entries"])
    editorial_reviews: dict[str, EditorialReview] = {}

    for cluster_id in sorted(state["approved_clusters"]):
        cluster = state["approved_clusters"][cluster_id]
        cluster_articles = [
            article_by_id[article_id] for article_id in cluster.article_ids
        ]
        metrics = state["cluster_metrics"][cluster_id]
        entry = audience_entries[cluster_id]

        review = critique_entry(
            entry, cluster, cluster_articles, allow_revision=True
        )
        if review.decision == "revise":
            entry = synthesize_audience(
                cluster,
                cluster_articles,
                metrics,
                revision_feedback=review.feedback,
            )
            audience_entries[cluster_id] = entry
            review = critique_entry(
                entry, cluster, cluster_articles, allow_revision=False
            )

        editorial_reviews[cluster_id] = review

    return {
        "audience_entries": audience_entries,
        "editorial_reviews": editorial_reviews,
    }


def finalize_node(state: GraphState) -> GraphState:
    final_portfolio = [
        PortfolioEntry(
            cluster_id=cluster_id,
            cluster=state["approved_clusters"][cluster_id],
            metrics=state["cluster_metrics"][cluster_id],
            entry=state["audience_entries"][cluster_id],
            editorial_review=state["editorial_reviews"][cluster_id],
        )
        for cluster_id in sorted(state["approved_clusters"])
    ]

    return {"final_portfolio": final_portfolio}


def route_after_apply(state: GraphState) -> str:
    if state["pending_cluster_ids"]:
        return "review_clusters"
    return "metrics"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("cluster", cluster_node)
    graph.add_node("review_clusters", review_clusters_node)
    graph.add_node("apply_review_decisions", apply_review_decisions_node)
    graph.add_node("metrics", metrics_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("critique_and_revise_once", critique_and_revise_once_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "cluster")
    graph.add_edge("cluster", "review_clusters")
    graph.add_edge("review_clusters", "apply_review_decisions")
    graph.add_conditional_edges("apply_review_decisions", route_after_apply)
    graph.add_edge("metrics", "synthesize")
    graph.add_edge("synthesize", "critique_and_revise_once")
    graph.add_edge("critique_and_revise_once", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def empty_graph_state(articles: list[Article]) -> GraphState:
    return {
        "articles": articles,
        "candidate_clusters": {},
        "pending_cluster_ids": [],
        "cluster_reviews": {},
        "approved_clusters": {},
        "rejected_clusters": {},
        "cluster_review_attempts": {},
        "cluster_metrics": {},
        "audience_entries": {},
        "editorial_reviews": {},
        "final_portfolio": [],
    }


def load_fixture_articles() -> list[Article]:
    fixture_path = Path(__file__).resolve().parents[2] / "tests/fixtures/sample_articles.json"
    raw_articles = json.loads(fixture_path.read_text())
    return [Article.model_validate(item) for item in raw_articles]


def print_graph_results(result: GraphState, articles: list[Article]) -> None:
    article_by_id = {article.id: article for article in articles}

    print(f"final_portfolio ({len(result['final_portfolio'])} entries)\n")
    for portfolio_entry in result["final_portfolio"]:
        titles = [
            article_by_id[article_id].title
            for article_id in portfolio_entry.cluster.article_ids
        ]
        print(f"=== {portfolio_entry.cluster_id}: {portfolio_entry.entry.name} ===")
        print(f"articles: {', '.join(titles)}")
        print(
            f"metrics: traffic_share={portfolio_entry.metrics.traffic_share:.1%}, "
            f"size_index={portfolio_entry.metrics.size_index:.1f}"
        )
        print(f"editorial: {portfolio_entry.editorial_review.decision}")
        print(portfolio_entry.entry.model_dump_json(indent=2))
        print()

    print(f"rejected_clusters ({len(result['rejected_clusters'])})\n")
    for cluster_id in sorted(result["rejected_clusters"]):
        cluster = result["rejected_clusters"][cluster_id]
        titles = [article_by_id[article_id].title for article_id in cluster.article_ids]
        print(f"  {cluster_id}: {', '.join(titles)}")


def run_graph(articles: list[Article]) -> GraphState:
    app = build_graph()
    return app.invoke(empty_graph_state(articles))


def save_live_cache(articles: list[Article], result: GraphState) -> Path:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "live",
        "articles": [article.model_dump() for article in articles],
        "final_portfolio": [
            entry.model_dump() for entry in result["final_portfolio"]
        ],
        "rejected_clusters": {
            cluster_id: cluster.model_dump()
            for cluster_id, cluster in result["rejected_clusters"].items()
        },
        "cluster_reviews": {
            cluster_id: review.model_dump()
            for cluster_id, review in result["cluster_reviews"].items()
        },
    }
    LIVE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVE_CACHE_PATH.write_text(json.dumps(payload, indent=2))
    return LIVE_CACHE_PATH


def load_live_cache() -> tuple[list[Article], GraphState]:
    if not LIVE_CACHE_PATH.exists():
        raise FileNotFoundError(
            f"No cached live run found at {LIVE_CACHE_PATH}. "
            "Run with --live --write-cache first."
        )

    payload = json.loads(LIVE_CACHE_PATH.read_text())
    articles = [Article.model_validate(item) for item in payload["articles"]]
    result: GraphState = {
        **empty_graph_state(articles),
        "final_portfolio": [
            PortfolioEntry.model_validate(item) for item in payload["final_portfolio"]
        ],
        "rejected_clusters": {
            cluster_id: CandidateCluster.model_validate(cluster)
            for cluster_id, cluster in payload["rejected_clusters"].items()
        },
        "cluster_reviews": {
            cluster_id: ReviewDecision.model_validate(review)
            for cluster_id, review in payload.get("cluster_reviews", {}).items()
        },
    }
    return articles, result


if __name__ == "__main__":
    import argparse

    from app.services.live_articles import build_live_articles

    parser = argparse.ArgumentParser(description="Run the audience trend miner graph")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--fixture",
        action="store_true",
        help="Run on the local sample_articles.json fixture",
    )
    source.add_argument(
        "--live",
        action="store_true",
        help="Run on live Wikipedia weekly top articles",
    )
    source.add_argument(
        "--cached",
        action="store_true",
        help="Replay a saved live run from sample_outputs/live_run.json",
    )
    parser.add_argument(
        "--write-cache",
        action="store_true",
        help="With --live, save articles and final output to sample_outputs/",
    )
    args = parser.parse_args()

    if args.cached:
        articles, result = load_live_cache()
        print(f"loaded cached live run ({len(articles)} articles)\n")
        print_graph_results(result, articles)
    elif args.fixture:
        articles = load_fixture_articles()
        print(f"loaded {len(articles)} fixture articles\n")
        result = run_graph(articles)
        print_graph_results(result, articles)
    else:
        print("fetching weekly top titles and enriching top 15...")
        articles = build_live_articles()
        print(f"loaded {len(articles)} live articles\n")
        for article in articles:
            print(
                f"  - {article.title} | pageviews={article.pageviews:,} | "
                f"categories={len(article.categories)}"
            )
        print()

        result = run_graph(articles)
        if args.write_cache:
            cache_path = save_live_cache(articles, result)
            print(f"saved live run cache to {cache_path}\n")
        print_graph_results(result, articles)
