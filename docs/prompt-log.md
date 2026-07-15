# Prompt Log

This is a representative log of how the system was built using Cursor as the agentic IDE, showing the incremental, test-then-commit workflow used throughout. Prompts are lightly cleaned up for readability but reflect the actual development sequence — small, testable asks rather than large upfront specifications, since verifying each piece before building on top of it mattered more than moving fast.

## Foundation

**Scaffolding**
> "Set up a FastAPI backend called audience-trend-miner under backend/app/. I want folders: api/, services/, clustering/, agent/... Add a main.py with a FastAPI app and a single GET /health endpoint."

**Schemas + test fixture**
> "need a couple pydantic models... Article, CandidateCluster, ReviewDecision... also can you make me a small fake dataset... 12 wikipedia-style articles I can test clustering against."

Built a hand-crafted 12-article fixture with four deliberate themes (eco/home-energy, celebrity/entertainment, sensitive/noise, unrelated singletons) specifically to stress-test clustering and review logic before touching live data.

## Clustering

**Embeddings + candidate clustering**
> "ok now the actual clustering... embed title + summary + categories... group them into CandidateCluster objects using agglomerative clustering with cosine distance, some reasonable distance threshold i can tune later... print which articles ended up in which cluster."

Cursor iterated on the distance threshold itself — started at 0.45 (produced only singletons), tested pairwise distances, converged on 0.85 after confirming the eco-themed articles actually grouped together. This is a case where the agentic IDE debugged a parameter rather than me hand-tuning it.

## Agent nodes (built and tested standalone before wiring into the graph)

**Reviewer**
> "ok now the reviewer node... asks gpt-4o-mini whether it's actually a coherent commercial audience or not. should be able to approve, reject, or say remove_outliers..."

Tested against both a clean fixture case (the eco cluster) and a deliberately incoherent one (hurricane season + presidential election) to confirm the reviewer discriminates rather than rubber-stamping. Also caught and fixed a real bug here: the reviewer's decisions were non-deterministic run-to-run at default temperature; locked temperature low (~0.1-0.2) across all judgment-making LLM calls for reproducibility.

**Synthesizer**
> "now the synthesizer - takes an approved cluster + its metrics and calls gpt-4o-mini to write the audience entry... buying power assessment - not just high/med/low, want actual reasoning behind it..."

Initial output returned buying power as unstructured prose; refined into a 4-factor rubric (purchase value, purchase immediacy, brand-category breadth, trend durability) as a deliberate follow-up once the first version's limitation was visible, rather than specifying the full rubric upfront.

**Critic**
> "next node - editorial critic. takes a finished audience entry and scores it 1-5 on cluster coherence, commercial relevance, evidence grounding, audience specificity, buying power justification... cap it at one revision max."

Stress-tested against a deliberately weak, mismatched entry (an audience description completely disconnected from its source articles) to confirm the critic actually catches bad output rather than defaulting to approval — it did, correctly scoring evidence_grounding at 1/5 and requesting revision with specific feedback.

## Graph wiring (built incrementally, one node at a time)

Rather than wiring the full LangGraph pipeline in one pass, each addition was tested in isolation before the next was layered on:
1. Skeleton (cluster node only) — confirmed the graph compiles and runs
2. + review_clusters node — confirmed decisions matched standalone node tests
3. + deterministic apply_review_decisions node (approve/reject/trim-and-requeue)
4. + router and one-repair-cap — closing the visible cluster-repair loop
5. + metrics → synthesize → critique_and_revise_once → finalize

At step 4, verified the repair loop with real cases: a cluster that got repaired and passed on its second review (e-bike removed from the eco cluster), and one that used its single repair attempt and still failed (Taylor Swift + MCU, even after removing Academy Awards) — confirming the retry cap terminates correctly rather than looping or force-approving.

## Live data integration

**Wikipedia client** — built incrementally: single-day fetch first (to see the real response shape before writing filtering logic), then filtering (once real junk patterns like `Special:` and `Wikipedia:` pages were visible), then 7-day aggregation with `days_trending` tracking, then failure handling as a separate pass (since it can't be verified live on demand).

**A real finding from live-data testing:** running the pipeline on live trending articles surfaced a case the fixture never tested — a cluster built around a recent celebrity death, which passed the reviewer's coherence check (trivially, being a single article) despite being exactly the "breaking global news tragedy" noise the brief calls out. Fixed by adding an explicit sensitivity check to the reviewer's prompt, verified the fix against the same live case, then reran the full pipeline to confirm.

## Frontend

Built incrementally in the same pattern: raw JSON fetch first (verify the connection works), then the portfolio card component, then the evidence drawer (initially collapsed at the bottom — moved to a top-level tab after recognizing it was actually the strongest evidence of the noise-filtering requirement and was easy to miss where it started), then the run-configuration panel with a real `/generate` endpoint (verified via timing: ~39s for a fresh pipeline run vs ~0.01s for a cache hit, proving the button genuinely executes the agent pipeline rather than serving static output).