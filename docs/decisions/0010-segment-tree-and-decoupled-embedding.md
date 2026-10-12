# 0010 · Segments form a tree; embedding is decoupled from ingest
Status: accepted (anchors and links added by 0012)

## Context
Citations point at clauses such as `R205(c)(ii)`, so every clause must be addressable.
A clause rarely stands alone: paragraph (c) means little without the sentence that
introduces it. Which level is best to embed and retrieve is a retrieval question that
evals should answer (M4), not one to fix at ingest. Ingest also has to be buildable and
testable without model access, and should not stall when the model provider is down.

## Decision
- **Every addressable unit is a segment row, linked to its parent.** For law: section,
  subsection, paragraph, subparagraph, clause, subclause and definition. For pages: an
  intro, each `h2` section and each `h3` subsection. A segment's body is its own text
  only; its heading path records where it sits.
- **Ref format, extending the firm format in the architecture:**
  - Definitions: parent ref, `#`, term slug. `R1(1)#common-law-partner`.
  - Schedules: prefix, `Sch`, number. `RSch1.1`, `ASch`. A schedule is one segment.
  - Page subsections nest under their section: `<slug>#<section>/<subsection>`.
  - Text above a page's first heading: `<slug>#intro`.
  - Repeated headings on a page get `-2`, `-3` in document order.
- **Every segment carries the official URL closest to it**, set at parse time.
  - Law: the section's page on the Justice Laws reading site, with the provision's own
    anchor below section level, such as `…/section-205.html#688813` for `R205(c)(ii)`.
    The anchor is the `lims:id` the XML gives that provision. Schedules link to the law.
  - Pages: the page address plus the heading's `id` when it has one, otherwise the page.
- **Only law in force is ingested**: the body and numbered schedules. Amendments not in
  force and related provisions in the same file are excluded.
- **Dates.** Law segments take their section's last-amended date, or its in-force date
  when it was never amended; the XML dates nothing below section level. Page segments
  take the page's modified date.
- **Officer instructions are segmented like public pages**, by heading. This settles the
  open question on Tier 2 depth for now; evals may revise it.
- **Embedding does not block ingest.** The embedding column is nullable. With an
  embedder configured, ingest embeds changed segments before the new version becomes
  current. Without one, segments become current without vectors and a backfill embeds
  them later. A segment whose text hash is unchanged keeps its embedding across versions.

## Alternatives considered
- One row per section, with clauses inside the text: refs below section level could not
  be resolved, validated or shown in context.
- One row per leaf clause only: loses the introducing sentence and the structure.
- Embedding inside ingest, always: ingest could not run or be tested without the model
  provider, and an outage there would freeze the corpus.
- Fixing the embedded level now: a guess, expensive to undo once retrieval is tuned to it.

## Consequences
- Retrieval must choose which levels to embed and how to assemble context from the tree.
  That choice is tunable without re-ingesting.
- Segments with no text of their own (a section made only of subsections) exist for
  navigation and are never embedded.
- A current segment can lack a vector until the backfill runs. It is still found by
  exact ref and full-text search. `immicite status` reports the count, and a deployed
  ingest must run with an embedder.
- A URL is part of a version's content hash, so a publisher renumbering its anchors
  produces a new version rather than silently stale links.
- Long page sections are stored whole. Splitting them further is a retrieval decision.
