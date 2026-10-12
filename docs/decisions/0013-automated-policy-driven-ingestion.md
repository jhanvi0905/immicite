# 0013 · Ingestion is automated and governed by a scope policy
Status: accepted, not yet built (supersedes the curated manifest in 0009; amends 0008)

## Context
0009 made the corpus a hand-kept list, because a crawler cannot assign authority levels
and has no natural stopping point. That list does not scale: ten pages already cite 71
pages the corpus lacks, and coverage is now every program (0015). The objection to
automation was never automation itself. It was guessing authority and growing without
bound. Both can be ruled out by policy.

## Decision
- **Ingestion runs nightly with no human approval.** The first run across all programs
  is a one-off backfill with raised limits.
- **A scope config file in the repo replaces approval.** Scope changes happen only
  through pull requests to it. It holds:
  - allowed hosts: canada.ca, laws-lois.justice.gc.ca, gazette.gc.ca. Any other host is
    recorded as a link and never fetched.
  - path rules mapping each URL prefix to an authority level and programs.
  - admission rules:
    - officer instructions are always admitted: every one under a program section, and
      every one the corpus links to from outside those sections. A page admitted only
      because it was linked to does not have its own links followed (one hop).
    - public pages are admitted under program paths, or when cited by at least two
      current segments.
    - from the Canada Gazette, only ministerial instructions issued under IRPA.
- **A page matching no rule is quarantined, never guessed**, because authority level
  decides precedence.
- **Quality checks before a version is published.** The fetch succeeded; the page is
  English; the main content was found; a "Date modified" is present; the segment count
  is sensible; the content is not a duplicate of a page held under another address; and
  the page did not shrink drastically against its previous version. A failure is
  quarantined with its reason and the previous version stays current.
- **Limits per run** on new pages, embedding spend and corpus size. Reaching one stops
  the run and raises an alert.
- **Polite fetching**: robots.txt respected, an identifying user agent, rate limits, and
  conditional requests where the host supports them.
- **Every run produces a report**: sources added, updated and quarantined, and new
  unresolved links. It is stored in the database and posted as a run summary.
- **Rollback** marks a source's previous version current again.
- **A corpus snapshot is cut weekly and evals run against it**, with an alert when scores
  drop. This amends 0008, where cutting a snapshot was a deliberate manual step.
- Pages that serve every program, such as procedural decision-making guidance, carry a
  `cross-program` tag.

## Alternatives considered
- Keeping the curated manifest: safe, and too slow to reach useful coverage.
- A ranked backlog approved by a person in batches: still a person in the loop nightly.
- An open crawl from seed pages: unbounded, and it would have to guess authority.

## Consequences
- The corpus grows to hundreds of pages, with new versions arriving often.
- The policy file becomes the most sensitive file in the repo: a wrong path rule assigns
  the wrong authority to every page under it. It needs tests and review.
- `sources.yaml` remains for law and for any source pinned by hand.
- **Known limit:** Canada.ca sends no `ETag` and reports the request time as
  `Last-Modified`, so conditional requests save nothing there. Those pages are fetched
  and hashed every run. Justice Laws does support them.

## Open
- Path prefixes for every program section.
- Whether admission by citation count is sticky. Without that, a page leaves and
  re-enters the corpus as the pages citing it are edited.
- Whether rollback also holds the source. Without that, the next run fetches the same
  bad page and makes it current again.
- The limits themselves, and where alerts and run summaries are sent.
- Gazette pages do not use the Canada.ca layout and need their own parser before any is
  ingested.
