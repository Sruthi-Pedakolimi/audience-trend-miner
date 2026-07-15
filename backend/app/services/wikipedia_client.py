from datetime import date, timedelta
from typing import Any

import httpx

BASE_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top"
PROJECT = "en.wikipedia.org"
ACCESS = "all-access"


def _pageviews_top_url(year: int, month: int, day: int) -> str:
    return f"{BASE_URL}/{PROJECT}/{ACCESS}/{year}/{month:02d}/{day:02d}"


USER_AGENT = "audience-trend-miner/0.1 (research prototype; contact: local-dev)"
MAX_ALLOWED_DAY_FETCH_FAILURES = 2


def fetch_top_pageviews(
    year: int,
    month: int,
    day: int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    url = _pageviews_top_url(year, month, day)
    owns_client = client is None
    http = client or httpx.Client(
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        response = http.get(url)
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            http.close()


def parse_top_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items", [])
    if not items:
        return []
    return items[0].get("articles", [])


def is_junk_article(article_key: str) -> bool:
    lower = article_key.lower()
    if lower == "main_page":
        return True
    return lower.startswith("special:") or lower.startswith("wikipedia:")


def normalize_title(article_key: str) -> str:
    return article_key.replace("_", " ")


def filter_top_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for item in articles:
        article_key = item["article"]
        if is_junk_article(article_key):
            continue

        filtered.append(
            {
                "title": normalize_title(article_key),
                "article": article_key,
                "views": item["views"],
            }
        )

    for rank, item in enumerate(filtered, start=1):
        item["rank"] = rank

    return filtered


def yesterday() -> date:
    return date.today() - timedelta(days=1)


def weekly_date_range(end_date: date, days: int = 7) -> list[date]:
    return [end_date - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def aggregate_weekly_top(
    end_date: date | None = None,
    *,
    days: int = 7,
    top_n: int = 30,
    client: httpx.Client | None = None,
) -> tuple[list[str], dict[str, int], dict[str, int]]:
    end = end_date or yesterday()
    weekly_pageviews: dict[str, int] = {}
    days_trending: dict[str, int] = {}

    owns_client = client is None
    http = client or httpx.Client(
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
    )
    failures: list[tuple[date, Exception]] = []

    try:
        for day in weekly_date_range(end, days=days):
            try:
                payload = fetch_top_pageviews(
                    day.year, day.month, day.day, client=http
                )
            except httpx.HTTPError as exc:
                failures.append((day, exc))
                if len(failures) > MAX_ALLOWED_DAY_FETCH_FAILURES:
                    failed_dates = ", ".join(
                        failed_day.isoformat() for failed_day, _ in failures
                    )
                    raise RuntimeError(
                        f"Failed to fetch {len(failures)} of {days} daily pageview "
                        f"lists ({failed_dates})"
                    ) from exc
                continue

            articles = filter_top_articles(parse_top_articles(payload))

            seen_titles: set[str] = set()
            for article in articles:
                title = article["title"]
                weekly_pageviews[title] = weekly_pageviews.get(title, 0) + article["views"]
                if title not in seen_titles:
                    days_trending[title] = days_trending.get(title, 0) + 1
                    seen_titles.add(title)
    finally:
        if owns_client:
            http.close()

    top_titles = sorted(
        weekly_pageviews,
        key=lambda title: weekly_pageviews[title],
        reverse=True,
    )[:top_n]

    top_weekly_pageviews = {title: weekly_pageviews[title] for title in top_titles}
    top_days_trending = {title: days_trending.get(title, 0) for title in top_titles}

    return top_titles, top_weekly_pageviews, top_days_trending


if __name__ == "__main__":
    end = yesterday()
    top_titles, weekly_pageviews, days_trending = aggregate_weekly_top(end)

    start = end - timedelta(days=6)
    print(f"weekly window: {start.isoformat()} to {end.isoformat()}")
    print(f"top titles returned: {len(top_titles)}\n")
    print("top 20:")
    for rank, title in enumerate(top_titles[:20], start=1):
        print(
            f"  {rank:>2}. {title} | "
            f"pageviews={weekly_pageviews[title]:,} | "
            f"days_trending={days_trending[title]}"
        )
