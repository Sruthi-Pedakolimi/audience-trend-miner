import time
from typing import Any
from urllib.parse import quote

import httpx

from app.services.wikipedia_client import USER_AGENT

SUMMARY_BASE_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
CATEGORIES_API_URL = "https://en.wikipedia.org/w/api.php"

MAX_ENRICHMENT_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 2.0
RETRYABLE_STATUS_CODES = {429, 503}

MAINTENANCE_CATEGORY_PREFIXES = (
    "All ",
    "Articles containing",
    "Articles with",
    "CS1 ",
    "Commons ",
    "Coordinates on",
    "Pages using",
    "Short description",
    "Use ",
    "Webarchive ",
    "Wikipedia ",
)


def _title_to_wiki_key(title: str) -> str:
    return title.replace(" ", "_")


def _is_maintenance_category(category: str) -> bool:
    return category.startswith(MAINTENANCE_CATEGORY_PREFIXES)


def _clean_categories(raw_categories: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for category in raw_categories:
        name = category.removeprefix("Category:")
        if _is_maintenance_category(name) or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)

    return cleaned


def _get_with_retry(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
) -> httpx.Response:
    backoff = INITIAL_BACKOFF_SECONDS

    for attempt in range(MAX_ENRICHMENT_RETRIES + 1):
        response = client.get(url, params=params)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            response.raise_for_status()
            return response

        if attempt < MAX_ENRICHMENT_RETRIES:
            time.sleep(backoff)
            backoff *= 2
            continue

        response.raise_for_status()

    raise RuntimeError("retry loop exited without response")


def fetch_page_summary(
    title: str,
    *,
    client: httpx.Client,
) -> dict[str, Any]:
    url = f"{SUMMARY_BASE_URL}/{quote(_title_to_wiki_key(title))}"
    response = _get_with_retry(client, url)
    return response.json()


def fetch_page_categories(
    title: str,
    *,
    client: httpx.Client,
) -> list[str]:
    categories: list[str] = []
    params: dict[str, str | int] = {
        "action": "query",
        "titles": title,
        "prop": "categories",
        "cllimit": 500,
        "format": "json",
    }

    while True:
        response = _get_with_retry(client, CATEGORIES_API_URL, params=params)
        payload = response.json()

        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            if "missing" in page:
                return []
            for item in page.get("categories", []):
                categories.append(item["title"])

        if "continue" not in payload:
            break
        params.update(payload["continue"])

    return _clean_categories(categories)


def enrich_title(
    title: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    http = client or httpx.Client(
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
    )

    try:
        summary_payload = fetch_page_summary(title, client=http)
        summary = summary_payload.get("extract") or summary_payload.get("description", "")
        categories = fetch_page_categories(title, client=http)

        return {
            "title": title,
            "summary": summary,
            "categories": categories,
        }
    finally:
        if owns_client:
            http.close()


if __name__ == "__main__":
    sample_titles = [
        "Erling Haaland",
        "Lindsey Graham",
        "2026 FIFA World Cup",
    ]

    for title in sample_titles:
        enriched = enrich_title(title)
        print(f"=== {title} ===")
        print(f"summary ({len(enriched['summary'])} chars):")
        print(enriched["summary"])
        print(f"\ncategories ({len(enriched['categories'])}):")
        for category in enriched["categories"][:15]:
            print(f"  - {category}")
        if len(enriched["categories"]) > 15:
            print(f"  ... and {len(enriched['categories']) - 15} more")
        print()
