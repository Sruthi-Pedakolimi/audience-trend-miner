import time
from datetime import date

import httpx

from app.agent.schemas import Article
from app.services.article_enrichment import _title_to_wiki_key, enrich_title
from app.services.wikipedia_client import USER_AGENT, aggregate_weekly_top

DEFAULT_WEEKLY_TOP_N = 30
DEFAULT_ENRICH_N = 15
ENRICHMENT_DELAY_SECONDS = 1.0


def build_live_articles(
    *,
    end_date: date | None = None,
    weekly_top_n: int = DEFAULT_WEEKLY_TOP_N,
    enrich_n: int = DEFAULT_ENRICH_N,
) -> list[Article]:
    top_titles, weekly_pageviews, _ = aggregate_weekly_top(
        end_date=end_date,
        top_n=weekly_top_n,
    )
    titles_to_enrich = top_titles[:enrich_n]
    articles: list[Article] = []

    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        for index, title in enumerate(titles_to_enrich):
            if index > 0:
                time.sleep(ENRICHMENT_DELAY_SECONDS)

            try:
                enriched = enrich_title(title, client=client)
            except httpx.HTTPError as exc:
                print(f"skipping {title!r}: enrichment failed ({exc})")
                continue

            summary = enriched["summary"].strip()
            if not summary:
                print(f"skipping {title!r}: empty summary")
                continue

            articles.append(
                Article(
                    id=_title_to_wiki_key(title),
                    title=title,
                    summary=summary,
                    categories=enriched["categories"],
                    pageviews=weekly_pageviews[title],
                )
            )

    if not articles:
        raise RuntimeError("No articles could be enriched from weekly top titles")

    return articles
