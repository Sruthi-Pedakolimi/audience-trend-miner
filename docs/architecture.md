# Architecture

## Overview

Audience Trend Miner turns a week of Wikipedia trending-article traffic into a portfolio of marketer-ready audience segments. The system is a hybrid pipeline: statistical grouping proposes structure, an LLM reviewer validates and repairs that structure with bounded authority, deterministic code computes anything that needs to be reproducible and comparable, and a second LLM stage handles the creative/commercial synthesis and self-critique.

The goal was to avoid two failure modes: (1) pure embeddings clustering with no judgment layer, which produces statistically-similar-but-commercially-meaningless groupings, and (2) a single LLM call doing everything, which is neither auditable nor correctable when it gets something wrong.

## Data flow

1. **Wikipedia Pageviews API** (public, unauthenticated) — the API only exposes daily top-1000 lists, not weekly ones. The client fetches the last 7 available days (data lags ~1 day, so it starts from yesterday), filters out non-article pages (`Main_Page`, `Special:*`, `Wikipedia:*` namespace pages), and aggregates by normalized title. For each surviving article it tracks total weekly pageviews and `days_trending` — the count of days it appeared in that day's top list — as a signal for distinguishing sustained interest from single-day spikes. A single day's fetch failure is tolerated (skipped); more than 2 of 7 failing raises an error.

2. **Enrichment** — the top N aggregated titles are enriched via Wikipedia's summary REST API (`/page/summary/{title}`) for a description, and the older MediaWiki action API (`action=query&prop=categories`) for categories, since the summary endpoint doesn't return them. Maintenance/meta categories (`Articles with...`, `CS1...`) are filtered out, topical ones kept. Enrichment calls are rate-limited with retry-and-backoff, since Wikipedia's API returns 429s under sustained request volume.

3. **Candidate clustering** (`clustering/`) — articles are embedded (title + summary + categories) using `sentence-transformers/all-MiniLM-L6-v2`, run locally with no external API dependency. Agglomerative clustering with cosine distance groups them into candidate clusters. The distance threshold (0.85) was tuned empirically: lower thresholds left every article as its own singleton, since Wikipedia summary text is fairly distinct even for thematically related topics. Before review, candidate clusters are ranked by total traffic and capped at 8 sent downstream, to bound LLM cost and latency; smaller/tinier clusters beyond the cap are dropped and logged, not silently discarded.

4. **Cluster review (LangGraph, visible conditional loop)** — this is the architectural centerpiece the challenge specifically names. An LLM (gpt-4o-mini, low temperature for reproducibility) reviews each candidate cluster and returns one of three decisions: `approve`, `reject`, or `remove_outliers` (with which article(s) to strip). A separate deterministic node applies that decision — approved clusters move to an approved set, rejected ones to a rejected set (with reason preserved for the evidence UI), and `remove_outliers` clusters get trimmed and routed back through review exactly once (a `LangGraph` conditional edge), capped at one repair attempt per cluster. If a repaired cluster still fails review, it's rejected outright rather than looping indefinitely or being force-approved.

   The reviewer's prompt explicitly checks two things: **coherence** (do these articles represent one targetable interest/behavior) and **sensitivity** (is the cluster driven by tragedy, death, or breaking news rather than a genuine ongoing interest) — the latter was added after live-data testing surfaced a real case: a recent celebrity death initially cleared review because it was technically internally coherent (one article, trivially consistent with itself), even though it's exactly the kind of non-commercial noise the brief calls out.

5. **Metrics** (deterministic, no LLM) — computed only once all clusters are resolved, since normalization needs the full approved set. `traffic_share` is proportional (cluster pageviews / total approved pageviews). `size_index` is log-normalized to 0-100 across the approved set, specifically to prevent one dominant viral topic from flattening every other audience's score to near-zero.

6. **Synthesis** (LLM) — for each approved cluster, generates a market-friendly name, a trend narrative grounded in the actual source articles, a structured 4-factor buying-power rubric (purchase value, purchase immediacy, brand-category breadth, trend durability — each rated + an overall rating + rationale), and suggested brand categories. Metrics are passed in as fixed inputs; the LLM never calculates them.

7. **Editorial critique** (LLM, bounded internal loop) — scores each synthesized entry 1-5 across five dimensions (cluster coherence, commercial relevance, evidence grounding, audience specificity, buying-power justification). If any score is weak, the entry gets exactly one revision pass with the critic's feedback fed back into synthesis; whatever comes back after that is final, no further looping. This was deliberately kept as internal node logic rather than a second visible LangGraph branch — the challenge names the *clustering* loop as the required architectural centerpiece, and a second graph-level loop here would add complexity without a comparable payoff.

## Why LangGraph, specifically

The workflow isn't linear — the cluster reviewer can change the shape of the data mid-pipeline (removing an article, requesting re-evaluation), and that decision needs to route execution differently depending on outcome. That's the concrete justification for using a graph-based orchestration framework instead of a plain function-call script: the cluster-repair loop is a real conditional edge with a bounded retry, not logic hidden inside a Python loop.

## Caching strategy

Two distinct caching layers, not to be confused with each other:
- **Article cache** (`data_mode: cached`) — reuses previously fetched-and-enriched Wikipedia articles for a given `week_ending` + `article_limit`, avoiding redundant Wikipedia calls. The pipeline (clustering → review → synthesis → critique) still runs fully live on this cached input.
- **Result cache** (`POST /generate`, keyed on `week_ending + article_limit + data_mode`) — if the exact same request has been run before, the full result (including all LLM output) is returned instantly. A genuinely new combination of inputs always triggers a real end-to-end pipeline run.

This distinction matters for the demo: cached mode makes runs fast and immune to Wikipedia rate limits, but every unique combination of inputs still proves the agent pipeline executes for real, not just that a static file is being served.

## Deliberately out of scope

- Cluster split/merge (only approve/reject/remove_outliers) — sufficient to prove the reviewer has real structural authority without the added complexity of arbitrary graph branching.
- Multi-provider LLM fallback — single provider (OpenAI) kept the build simpler; a prior project (LIA) already demonstrates this pattern is something I can build when the tradeoff calls for it.
- `Send`-based parallel fan-out for cluster review — sequential processing is fine at this scale (typically ≤8 clusters); parallelism would add state-merging complexity without a proportional benefit for a prototype.
- Production-grade cache invalidation (model/prompt versioning in the cache key) — the current key (`week_ending + article_limit + data_mode`) is sufficient for the MVP; a production system would extend it.