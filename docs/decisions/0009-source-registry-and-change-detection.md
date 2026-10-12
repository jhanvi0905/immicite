# 0009 · Source registry, versions and change detection
Status: accepted (tiers renamed by 0011; page slugs derived by 0012; the curated
manifest is superseded by 0013 once that is built)

## Context
Ingest needs to know which documents make up the corpus, and when one has changed. The
raw bytes of a source are not a reliable signal: the Justice Laws XML carries a
consolidation date that moves without any amendment, and Canada.ca pages are rendered
per request. Tier and program labels decide legal precedence, so they cannot be guessed.

## Decision
- **The corpus is a curated manifest**, `sources.yaml`, in git. Each entry has a slug,
  title, tier, kind, programs, language, official URL and licence. It holds URLs and
  metadata only, never source text. Adding a document is a reviewed change.
- **A version is identified by a hash of its parsed content**: every segment's ref, text,
  heading path and date, plus the source's published date. Unchanged content creates no
  version; `sources.last_checked_at` records that it was checked.
- **The raw payload is stored on the version row in Postgres.** A parser fix can then
  re-segment without refetching, and corpus snapshots (0008) are self-contained.
- **A source removed from the manifest is retired**: its segments stop being current and
  its versions are kept. Returning it to the manifest makes it current again.
- **Fetching is polite**: an identifying User-Agent, robots.txt respected, one request
  per second per host, retries with backoff.
- **An empty parse is a failure**, never a new version. One source failing does not stop
  the others, and the job exits non-zero.

## Alternatives considered
- A crawler that discovers pages: unbounded, hard to verify, and it cannot assign tiers.
- Hashing raw bytes: a new version on nearly every run, with nothing actually changed.
- HTTP `ETag` or `Last-Modified`: Canada.ca reports the request time as `Last-Modified`.
- Raw files on disk under `data/raw/`: a second store to keep in step with the database.
- A browser-like User-Agent: Canada.ca rejects it, and it misstates who is asking.

## Consequences
- The corpus grows only as fast as someone adds sources. Coverage is a deliberate choice.
- A parser change alters the content hash, so the next ingest creates a new version of
  every affected source. Unchanged segments keep their embeddings (0010).
- The slug of a page is part of its refs, so renaming a slug renames its refs.
- Stored raw pages make the database, not git, the place government text lives.
