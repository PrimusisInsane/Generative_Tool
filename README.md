# Media Summarizer — Book & Movie Summary Generator

A full-stack GenAI application that generates structured, grounded summaries of books and movies — combining real factual data (TMDB, Google Books, Wikipedia) with Gemini-powered rewriting, tuned by user-selected spoiler level and length.

---

## Architecture Overview

```
React (Vite) frontend
        │  fetch() → GraphQL mutation
        ▼
FastAPI + Ariadne (GraphQL layer)
        │
        ▼
generations.py (retry: bad JSON + transient server errors)
        │
        ├──► Redis (cache check by title+media_type+spoiler_level+length)
        │
        ▼
media_fetch.py ──┬──► TMDB API (movies: genre, overview, ratings)
                 ├──► Google Books API (books: authors, categories, description)
                 └──► wiki_fetch.py → Wikipedia (real plot depth, via search ranking)
        │
        ▼  (merged into one source_data dict)
llm_client.py → Gemini API (rewrites grounded facts into requested shape)
        │
        ▼
schema.py (Pydantic validation: SummaryResponse)
        │
        ▼
storage.py → Postgres (summaries table, full history)
```

**Core design principle:** the LLM never relies on its own memory of a book/movie's plot. Every summary is *grounded* — built from real, fetched, structured data — and the model's job is narrowly to rewrite that data into the requested tone/length/spoiler-level, not to recall or invent plot details.

---

## Why Grounding Instead of Pure Model Memory

The project started with a title-only design (just ask Gemini "summarize Dune"), relying entirely on the model's parametric memory. This was rejected early for one real reason: **hallucination risk on obscure or ambiguous titles.** A model asked to recall an unfamiliar or ambiguous work will often generate plausible-sounding but incorrect plot details rather than admitting uncertainty.

The fix, mirroring a Retrieval-Augmented Generation (RAG) pattern: fetch real facts first, then have the LLM synthesize *only* from those facts. This shifts the model's job from "remember accurately" (unreliable) to "rewrite known facts well" (a genuine LLM strength).

---

## Data Sources

| Source | Provides | Auth |
|---|---|---|
| **TMDB** (movies) | Title, genre names, official overview, release date, rating, vote count | Bearer token (API Read Access Token, v4) |
| **Google Books** (books) | Title, authors, categories, publisher description, published date | API key (query param) |
| **Wikipedia** (both) | Full plot section — real named characters, complete narrative including ending | None required (open API) |

**Why three sources, not one:** TMDB/Google Books give clean, structured metadata but only short marketing-style blurbs (50-100 words) — enough for a short/medium summary but nowhere near enough for a genuinely long or full-spoiler summary. Wikipedia's "Plot" section fills that gap with real, detailed, ending-inclusive plot text (600-900+ words for well-known titles), at the cost of being unstructured prose rather than clean metadata. Combining both gives the best of each.

---

## Repo Structure

```
MY_GEN_TOOL/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app + CORS + GraphQL mount
│   │   ├── config.py               # pydantic-settings, reads .env
│   │   ├── db.py                   # async SQLAlchemy engine + session
│   │   ├── models.py               # Summary model (Mapped[] style)
│   │   ├── schema.py                # SummaryResponse Pydantic schema
│   │   ├── graphql_schema.py       # Ariadne type_defs + resolvers
│   │   ├── services/
│   │   │   ├── media_fetch.py      # TMDB + Google Books fetchers, merges in Wikipedia plot
│   │   │   ├── wiki_fetch.py       # Wikipedia search + plot-section extraction
│   │   │   ├── prompts.py          # SUMMARY_SYSTEM_PROMPT + user prompt builder
│   │   │   ├── llm_client.py       # real Gemini call + markdown-fence stripper
│   │   │   ├── generations.py      # retry logic + Redis caching wrapper
│   │   │   └── storage.py          # save validated summary to Postgres
│   │   └── scripts/
│   │       ├── test_fetch.py       # manual smoke-test for media_fetch
│   │       ├── test_wiki.py        # manual smoke-test for wiki_fetch
│   │       └── test_llm.py         # manual smoke-test for full pipeline
│   ├── alembic/                    # migrations (async env.py)
│   ├── docker-compose.yml          # Postgres + Redis
│   ├── pyproject.toml              # Poetry, PEP 621 format
│   └── .env                        # secrets, never committed
│
└── frontend/
    └── src/
        └── App.jsx                 # form → GraphQL mutation → rendered results
```

---

## Backend, Step by Step

### 1. Schema design (done first, before any code)
`SummaryResponse`, using `Literal` types for stricter validation than plain strings:
```python
from pydantic import BaseModel
from typing import Literal

class SummaryResponse(BaseModel):
    title: str
    media_type: Literal["book", "movie"]
    genre: list[str]
    themes: list[str]
    summary: str
    confidence: Literal["high", "medium", "low"]
```
`Literal` means Pydantic rejects any response where the model returns something outside the exact allowed values — stronger validation than the plain `str` fields used in an earlier project.

### 2. TMDB fetcher — with a real correctness fix
Two-step fetch: search returns `genre_ids` (numbers only), so a second call to `/movie/{id}` gets actual genre names.

**Real bug hit and fixed:** initial testing on "The Avengers" and similar ambiguous titles showed the naive `results[0]` approach can grab the wrong film. TMDB's search does rank by relevance/popularity, which usually self-corrects, but isn't guaranteed for every ambiguous title.

### 3. Google Books fetcher — a real correctness bug, caught and fixed
First version picked "the first result with a non-empty description" — this silently returned **"Children of Dune"** instead of **"Dune"** when searching for "Dune," because it didn't check that the candidate's title actually matched the search term.

**Fix:** filter candidates to those whose title exactly matches (case-insensitive) the searched title *first*, then among those matches prefer one with a populated description. Returns `None` rather than a wrong book if no exact match exists — a wrong-but-present result is worse than an honest "not found."

### 4. Wikipedia fetcher — the piece that unlocked real depth

**First attempt failed:** the `wikipedia` PyPI package (unmaintained) threw `JSONDecodeError` because Wikipedia's API now expects a proper `User-Agent` header, which that old package doesn't reliably send.

**Fix:** switched to `Wikipedia-API` (actively maintained, note the capitalization — a different package), with an explicit `user_agent` and native async support:
```python
wiki = wikipediaapi.AsyncWikipedia(
    user_agent="MediaSummarizerApp/1.0 (personal learning project)",
    language="en",
)
```

**Second bug, more subtle:** guessing exact page title strings (`"Dune (film)"`) failed, because that string resolves to a **disambiguation page** (no plot section), while the real content lives at a more specific title like `"Dune (2021 film)"`. The fix moved from guessing exact titles to using Wikipedia's own `search()` API and iterating results in ranked order until one actually has a real "Plot" section:

```python
async def fetch_wikipedia_plot(title: str, media_type: str) -> str | None:
    hint = "film" if media_type == "movie" else "novel"
    results = await wiki.search(f"{title} {hint}", limit=5)

    for page_title, page in results.pages.items():
        if not await page.exists():
            continue
        sections = await page.sections
        plot = _find_plot_section(sections)
        if plot:
            return plot.strip()

    return None
```

This correctly skips disambiguation pages (no plot section → keep trying) and lands on the real, specific film/novel page.

### 5. Merging sources
```python
async def fetch_media_data(title: str, media_type: str) -> dict | None:
    metadata = await fetch_movie_data(title) if media_type == "movie" else await fetch_book_data(title)
    if metadata is None:
        return None
    metadata["full_plot"] = await fetch_wikipedia_plot(title, media_type)  # None if unavailable
    return metadata
```
Returns `None` only if TMDB/Google Books itself finds nothing — a cheap short-circuit that skips the Gemini call entirely for non-existent titles. `full_plot` is optional; its absence doesn't block a summary, it just limits how detailed/confident it can be.

### 6. Prompt engineering — grounded, not memory-based
```python
SUMMARY_SYSTEM_PROMPT = """You are a summarization assistant for books and movies.
You will be given real factual data about a specific work, fetched from a database.
Your job is to rewrite that data into a summary matching the requested tone, length, 
and spoiler level.

Grounding rules:
- Base your summary ONLY on the provided source data
- Do not add plot details, character names, or events not present in the source data
- If the source data is thin or vague, write a shorter summary rather than inventing 
  detail to fill space
- If spoiler_level is "full" but the source data does not reveal the ending (common 
  for premise-only synopses), set confidence to "low" and note the gap explicitly

Length rules:
- "short": one paragraph (~150 words)
- "medium": 3 paragraphs (~400 words)
- "long": multiple paragraphs (~1500 words)

Output ONLY valid JSON matching this schema...
"""
```

**Real lesson learned about length vs. grounding:** requesting "long" (~1500 words) is only meaningful when real plot-depth data (Wikipedia) is available. Against a bare 60-word TMDB blurb, the grounding rule and the length rule directly conflict — the model correctly refuses to pad with invented content, producing a short summary and `confidence: "low"` instead. This is the system working as designed, not a bug: the confidence field exists precisely to surface this honestly rather than hide it.

### 7. Retry logic — two distinct failure modes
```python
async def get_validated_summary(source_data, spoiler_level, length, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            raw = await call_llm(source_data, spoiler_level, length)
            return SummaryResponse.model_validate(json.loads(raw))
        except genai_errors.ServerError:
            await asyncio.sleep(2)  # transient 503s from Gemini's servers
        except (json.JSONDecodeError, ValidationError):
            pass  # malformed JSON, retry immediately
    raise last_error
```
Handles both a malformed LLM response *and* Gemini's own transient server errors (503s under high demand) — a real error encountered during development, not a hypothetical.

### 8. Caching — four-parameter key
```python
def _cache_key(title, media_type, spoiler_level, length) -> str:
    return f"summary:{media_type}:{title.strip().lower()}:{spoiler_level}:{length}"
```
Unlike a single-parameter cache (e.g. just `enemy_type` in an earlier project), a summary's identity depends on **four** inputs — the same title with different spoiler/length settings is a genuinely different output and needs its own cache entry.

**Real gotcha hit during testing:** after upgrading the pipeline (adding Wikipedia), an old cached entry from *before* the upgrade kept returning stale, thin, low-confidence results — masking the fact that the fix had actually worked. Lesson: cache entries don't know when your underlying logic changes; clear or version cache keys after any pipeline change during active development (`docker compose exec redis redis-cli DEL "<key>"` or `FLUSHALL` for a full reset).

### 9. Persistence
Same pattern as prior projects — every generation (cached or not) is saved to Postgres as a permanent history log; Redis only ever skips the *LLM call*, never the database write.

### 10. GraphQL — nullable result for the "not found" case
```graphql
type Mutation {
    generateSummary(title: String!, mediaType: String!, spoilerLevel: String!, length: String!): SummaryResult
}
```
Note `SummaryResult` (no `!`) — nullable by design. If TMDB/Google Books can't find the title at all, the mutation returns `null` rather than erroring, letting the frontend show a clean "not found" message without wasting a Gemini call on a nonexistent title.

---

## Frontend

Vite + React, plain CSS, calling GraphQL via plain `fetch()` (no client library) — same minimal-dependency approach as prior projects.

**Form fields:** title (text input), media type (book/movie dropdown), spoiler level (none/mild/full dropdown), length (short/medium/long dropdown).

**Key UI behaviors:**
- `confidence === "low"` renders a visible warning badge — the direct payoff of designing the confidence field as a first-class signal, not just a logged value
- `null` mutation result renders a "no match found" message instead of crashing
- Multi-paragraph summaries render as genuinely separate `<p>` tags via `summary.split('\n\n').map(...)`, since HTML collapses literal `\n` characters by default and won't visually break paragraphs without either this split or `white-space: pre-wrap` CSS

---

## Real Issues Hit and Resolved

| Problem | Root Cause | Fix |
|---|---|---|
| `ImportError: cannot import name 'settings'` | `config.py` was completely empty | Filled in `Settings` class + `settings = Settings()` instance |
| TMDB key looked "invalid" | Copied placeholder text (`YOUR_TOKEN_HERE`) instead of the real token | Used the actual copied token |
| Google Books returned "Children of Dune" for a "Dune" search | No exact-title-match filtering, just "first result with a description" | Added exact-title match filter before preferring populated descriptions |
| Wikipedia fetch crashed with `JSONDecodeError` | Unmaintained `wikipedia` package sending an inadequate `User-Agent` | Switched to actively maintained `Wikipedia-API` package with explicit `user_agent` |
| Wikipedia "Dune (film)" found nothing useful | That title resolves to a disambiguation page, not the real film page | Replaced title-guessing with `wiki.search()` + iterate ranked results for one with a real plot section |
| Frontend showed one giant paragraph instead of several | HTML collapses `\n` characters by default | Split summary text on `\n\n` into separate `<p>` elements |
| "Long"/"full spoiler" summaries stayed short and low-confidence | Source data (TMDB/Google Books blurb) too thin to support 1500 words honestly | Understood as correct grounding behavior, not a bug — later fixed properly by adding Wikipedia as a richer source |
| Gemini call failed with `429 RESOURCE_EXHAUSTED` | Free tier daily quota (20 requests/day) exhausted from active testing | Not a bug — wait for quota reset, or rely on cached results during heavy testing |
| Stale low-confidence result after adding Wikipedia | Redis cache still holding a pre-upgrade cached entry (1hr TTL) | Manually cleared the specific cache key; lesson to version/clear cache during active pipeline changes |

---

## What This Project Demonstrates Beyond the First GenAI App

1. **True RAG architecture** — three merged real data sources feeding a grounded prompt, not a single title handed to model memory.
2. **Confidence as a first-class, honest signal** — not just a field that exists, but one that's designed to visibly warn users when the underlying data can't support what they asked for (e.g. full spoilers from a premise-only blurb).
3. **Correctness bugs in data fetching are a distinct category from LLM bugs** — the "Children of Dune" and "Dune (film) disambiguation page" issues had nothing to do with prompt engineering or the LLM at all; they were data-layer correctness problems that would have silently fed the LLM wrong information no matter how good the prompt was.
9. **Caching interacts with iterative development in a way that can mislead you** — a stale cache entry can make a real fix look like it didn't work, which is a distinct debugging skill from anything specific to LLMs.

---

## Natural Next Steps
- A "detailed source available" indicator (`hasDetailedSource` GraphQL field) so users know upfront whether "full/long" will actually deliver depth for a given title
- A `summaries` history view on the frontend (query already exists, just needs a UI)
- Debug logging for word-count of fetched plot data, surfaced in real server logs rather than one-off test scripts
- Explore whether "medium" length summaries over-compress and drop named details even when rich source data is available