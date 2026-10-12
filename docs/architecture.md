# Architecture

**Labels.** *Current*: implemented and tested. *Planned*: decided, not yet built.
*Open*: not decided. *Proposed*: written up, not yet accepted.

Planned items are intended scope. The phases in the product brief give their intended
order; when each is built is decided as the work proceeds.

**Current today:** ingest of the law and a starter set of pages, links between segments,
and named authority levels. Everything else is Planned.

Scope: docs/product-brief.md. Decisions: docs/decisions/.

## 1. Purpose and scope
The system answers practitioners' questions about Canadian immigration and citizenship
rules. Every claim cites the specific clause that supports it, with that clause's
authority level and date. It refuses when the evidence does not support an answer.

Coverage is every program under IRPA, and citizenship (ADR 0015). Each program carries a
readiness level, so an answer says how well its program is covered. Passports are out of
scope.

## 2. System map
| Component | Status | Responsibility |
| --- | --- | --- |
| Frontend | Planned | Practitioner UI; talks only to the public API |
| API | Planned | HTTP boundary: validation, response shapes, streaming, rate limits |
| Services | Current for ingest | Orchestrate ingest and the single-pass answer flow |
| Workflows | Planned | Multi-step flows on LangGraph: research mode, checklist (ADR 0006) |
| Domain | Current for the corpus | Pure rules: authority levels and precedence, refs, links, rank fusion, citation validation, conflicts, refusal, and the ports services depend on |
| Integrations | Current for ingest | Implement the ports: Postgres, model providers, reranker, source fetchers and parsers, fakes for tests |
| Postgres | Current for the corpus | One store for corpus, vectors, full-text, links, lookup rows, the domain graph, answers, feedback, eval results and workflow checkpoints (ADR 0001) |
| Scope policy | Planned | A config file deciding which hosts and paths may enter the corpus, and at which authority level (ADR 0013) |
| Program taxonomy | Planned | A file defining the tree of programs and each one's readiness level (ADR 0015) |
| Requirement catalogs | Proposed | One file per program listing its requirements, which extraction maps onto (ADR 0016) |

```
frontend ─► api ─► services ─┬───────────────► domain ◄── integrations ─► Postgres
                             └─► workflows ──► domain                  ─► model provider
                                 (LangGraph)                           ─► source sites
```
**Firm boundaries, enforced by import-linter in CI:**
- Domain imports no other layer. *(Current)*
- Nothing imports from api. *(Current)*
- Services depend on domain ports, never on integrations. *(Current)*
- LangGraph is imported only in `services/workflows`. *(Planned, with the first workflow)*
- No LangChain retrievers, vector stores or loaders, and no LlamaIndex, anywhere
  (ADR 0002). *(Planned, as a contract)*

Names inside a layer are not fixed.

All request-path I/O is async (ADR 0007).

## 3. Flows

### 3.1 Ingest
**Current.** Triggered by `immicite ingest [--authority LEVEL] [--source SLUG]
[--dry-run]`. The corpus is the set of sources listed in `sources.yaml` (ADR 0009).
Coverage today: IRPA and IRPR in full, five officer-instruction pages and five public
pages.

1. Take an advisory lock, so only one ingest runs at a time.
2. Fetch each source and split it into a tree of segments along its structure: every
   provision down to subclause for law; intro, `h2` and `h3` sections for pages (ADR 0010).
   Record each segment's outgoing links (ADR 0012).
3. Hash the parsed content. Skip the source when the hash matches its current version.
4. Reuse the previous embedding when a segment's text is unchanged. Embed the rest when
   an embedder is configured; otherwise leave them for the backfill (ADR 0010).
5. In one transaction, record the new version (append-only), mark its segments current
   and the previous version's segments not current.
6. Retire sources that are no longer in the manifest: their segments stop being current.

**Properties that must hold:**
- Ingest is idempotent.
- Versions are never modified.
- A ref stays stable across versions.
- Readers never see a half-ingested source.
- An empty or failed parse never replaces a source.

**Planned: automated ingestion (ADR 0013).** Ingestion runs nightly with no human
approval. A scope policy file replaces the hand-kept list for pages; `sources.yaml`
remains for law and for sources pinned by hand.
- **Admission.** Allowed hosts are canada.ca, laws-lois.justice.gc.ca and gazette.gc.ca.
  Path rules map each URL prefix to an authority level and programs.
  - Officer instructions are always admitted: every one under a program section, and
    every one the corpus links to from outside those sections. A page admitted only by a
    link does not have its own links followed.
  - Public pages are admitted under program paths, or when cited by at least two current
    segments.
  - From the Canada Gazette, only ministerial instructions issued under IRPA.
  - A page matching no rule is quarantined, never guessed.
- **Quality checks before a version is published.** Fetch succeeded; English; main
  content found; "Date modified" present; a sensible segment count; not a duplicate; no
  drastic shrinkage against the previous version. A failure is quarantined with its
  reason and the previous version stays current.
- **Limits per run** on new pages, embedding spend and corpus size. Reaching one stops
  the run and raises an alert. The first run across all programs is a one-off backfill
  with raised limits.
- **Run report.** Sources added, updated and quarantined, and new unresolved links,
  stored in the database and posted as a run summary.
- **Rollback** marks a source's previous version current again.
- Pages that serve every program carry a `cross-program` tag.

**Planned: lookup tables (ADR 0014).** Lists that need exact matching (eligible fields of
study, the DLI list, the fee schedule) are ingested as versioned rows with a key. A list
loads only when a parser for it exists in the repo; otherwise it is recorded as a link.

**Planned: more law.** The Citizenship Act and Regulations, and ministerial instructions
and public policies at their own authority level.

### 3.2 Ask: single pass (Planned)
1. Work out the program. Use the one in the request, or classify the question with a
   small model. Below a confidence threshold, search with no program filter (ADR 0015).
2. Route exact refs such as R205(c) or A40(1) directly to their segments.
3. Rewrite the question into search terms.
4. Run hybrid search over current segments: top 50 by vector (with iterative scans when
   filtered) and top 50 by full-text, fused with reciprocal rank fusion.
5. Rerank the top 40 and keep 8. Reserve up to 2 of the 8 for Act and Regulations
   segments when any are in the top 40, so conflicts with the law stay visible.
6. When the question turns on a row of an official list, look the row up exactly and add
   it to the evidence (ADR 0014). Code runs the lookup; the model does not.
7. Generate structured output from that evidence only.
8. Validate in code (ADR 0003).
9. Attach gap notices: for each cited segment, any link to an in-scope page or list that
   is not held (ADR 0017). Attach the programs used, their readiness, and the high-stakes
   notice where it applies.
10. Record the answer, its retrieval trace, model versions, cost and latency.

**Properties that must hold:**
- Every returned claim cites a segment retrieved, or a row looked up, for this request.
- With no supported claim, the response is a refusal.
- Every response carries its source dates and the readiness of its programs.
- Precedence is decided in code from authority levels, not by the model (ADR 0011).
- A low-confidence program detection never narrows the search.

**Room to tune:** candidate counts, fusion parameters, the law reservation, prompts and
models. All are judged by evals, and each run records its configuration.

**Planned, behind a flag: following links.** Fill the reserved law slots by following
links one hop, and only upwards in authority, instead of choosing law by similarity. Both
settings are compared in evals, and it stays off unless it helps (ADR 0017).

### 3.3 Research mode (Planned)
For questions that chain several rules (for example, study permit → PGWP → Canadian
Experience Class):

```
plan sub-questions → retrieve per sub-question → assess ─┬─ enough → answer → validate
                         ▲                               │
                         └───────── gaps, max 2 rounds ──┘
```
- Retrieval and validation reuse the single-pass components.
- Graph state holds refs and ids, never full objects.
- The answer is a chain of cited steps. Facts that would change the outcome are listed
  as branches, never resolved by guessing.
- For structured programs it follows the `leads_to` pathways in the domain graph
  (ADR 0016, Proposed).

### 3.4 Checklist (Proposed, ADR 0016)
The checklist reads the domain graph. It is no longer assembled from retrieved text.

```
program → its requirements → the facts each depends on
              │
   missing fact that changes the result? ─ yes → ask practitioner (interrupt) → resume ┐
              │ no                                                                     │
              ▼                                                                        │
   apply facts and exemptions → cited items → validate ◄───────────────────────────────┘
```
- Offered only for structured programs. For any other program it returns `not_available`
  and suggests research mode.
- The interrupt lives in its own node, with nothing but the question before it, because
  a resumed node re-runs from its start.
- State is checkpointed in Postgres and resumed by `thread_id`.
- Every item cites the quote that states it.

### 3.5 Extraction into the domain graph (Proposed, ADR 0016)
1. After a version is published, a model reads each new or changed segment and proposes
   candidate nodes and edges.
2. Code keeps a candidate only if its quote appears word for word in the segment, it maps
   to an entry in the program's requirement catalog, and its types are valid.
3. Kept facts are stored with their provenance and versioned with the segment.
4. Statements that map to no catalog entry are listed in the run report.

Extraction is its own pass. It never blocks a version from being published, for the same
reason embedding does not (ADR 0010).

## 4. Data and contracts

**Sources of truth**
| What | Where | Status |
| --- | --- | --- |
| Schema | Alembic migrations | Current |
| Law and pinned sources in the corpus | `sources.yaml` in git: URLs and metadata only | Current |
| Which pages may enter the corpus | Scope policy file in git | Planned |
| Programs and their readiness | Taxonomy file in git | Planned |
| Requirement catalogs | One file per program in git | Proposed |
| Ontology: node and edge types | Code | Proposed |
| Corpus: sources, versions, segments, links, embeddings | Postgres | Current |
| Lookup rows; run reports; quarantined pages | Postgres | Planned |
| Domain graph: nodes, edges, provenance | Postgres | Proposed |
| Answers, retrieval traces, citations, feedback | Postgres | Planned |
| Workflow checkpoints | Postgres, in tables created by LangGraph's Postgres checkpointer | Planned |
| Eval cases | `evals/cases/*.yaml` in git, written by a human | Planned |
| Eval results | Postgres; each run records git SHA, config, model versions, corpus snapshot id | Planned |
| Corpus snapshots for evals | Private Azure Blob container (ADR 0008) | Planned |
| Government page text | Never in git. Raw payloads live on the version row in Postgres | Current |

**Key shapes** (conceptual; migrations hold the detail)

*Current*
- **Authority level:** name and rank. Highest first: Act, Regulations, ministerial
  instructions and public policies, officer instructions, public guidance (ADR 0011).
- **Source:** slug, title, authority level, kind, programs, language, download URL,
  licence, last-checked time. A law also has the address of its reading site in the
  manifest, which citation links are built from.
- **Version:** source, content hash, raw payload, captured date, published date.
  Append-only.
- **Segment:** version, parent segment, ref, kind, depth, heading path, body (its own
  text only), official URL (to the clause or heading where the publisher allows), text
  hash, last-amended date, language, `is_current`, 1,024-dimension embedding (empty
  until embedded), generated full-text vector, and the publisher's anchor.
- **Segment link:** segment, position, origin (page link or law cross-reference), link
  text, normalised target address and fragment, target class, and the ref the target
  would have. No foreign key on the target, and whether the target is held is never
  stored: it is computed when reading (ADR 0012).

*Planned*
- **Lookup table and row:** a table is a source with versions; a row has a key and its
  fields (ADR 0014).
- **Program:** a node in the taxonomy tree, with its readiness level: indexed, evaluated
  or structured (ADR 0015).
- **Run report:** one per ingest run, with sources added, updated and quarantined, and
  new unresolved links (ADR 0013).
- **Answer:** endpoint, question, status, response, programs, model versions, prompt
  version, tokens, cost, latency, plus a retrieval row for each candidate at each stage
  and a citation row for each claim.
- **Feedback:** answer, kind (helpful, wrong citation, outdated, other), note, created
  date.

*Proposed (ADR 0016)*
- **Graph node:** type (Program, Requirement, Fact, Document, Lookup table, Exemption)
  and its catalog entry.
- **Graph edge:** type (`leads_to`, `requires`, `depends_on_fact`, `evidenced_by`,
  `checked_against`, `excepted_by`) between two nodes.
- **Provenance:** for every node and edge, the segment and the exact quote that states it.

**Ref format (firm; used in the API and in eval cases)**
- Regulations: `R` plus the section path, for example `R205(c)(ii)`.
- Act: `A` plus the section path, for example `A40(1)`.
- Definitions: the parent ref, `#`, the term, for example `R1(1)#common-law-partner`.
- Schedules: the prefix, `Sch`, the number, for example `RSch1.1`.
- A page's source slug is derived from its address: `pdi-…` for officer instructions,
  `ircc-…` for other IRCC pages.
- Page sections: `<source-slug>#<heading-slug>`, with subsections nested as
  `<source-slug>#<heading-slug>/<subheading-slug>` and the text above the first heading
  as `<source-slug>#intro`. The publisher's anchor is stored beside the ref, so a link to
  `page.html#s12` still resolves to its section.
- List rows *(Planned)*: `<table-slug>#<row-key>`.
- *Open:* prefixes for the Citizenship Act and Regulations. `A` and `R` mean IRPA and
  IRPR.

**Public API** (all Planned)
| Endpoint | Purpose |
| --- | --- |
| `POST /ask` | Single-pass cited answer. Firm once shipped |
| `POST /research` | Multi-step cited answer; adds `steps` |
| `POST /checklist`, `POST /checklist/{thread_id}/resume` | Returns `needs_input` with a question, `completed` with cited items, or `not_available`. Shape Open |
| `GET /programs` | The program taxonomy with readiness levels |
| `GET /sources/{ref}?version_id=` | A segment in context, current or as cited |
| `POST /answers/{id}/feedback` | Practitioner feedback |
| `GET /health` | Liveness (Current); database check Planned |

`POST /ask` request. `program` is optional:
```json
{ "question": "string", "program": "string | null" }
```
Response:
```json
{
  "answer_id": "uuid",
  "status": "answered | refused | out_of_scope",
  "programs": [{ "slug": "string", "readiness": "indexed | evaluated | structured",
                 "detected": true }],
  "claims": [{ "text": "string", "refs": ["R205(c)(ii)"] }],
  "conflicts": [{ "governing_ref": "string | null", "other_ref": "string",
                  "note": "string" }],
  "gaps": [{ "from_ref": "string", "title": "string", "url": "string",
             "kind": "page | list" }],
  "notices": ["string"],
  "sources": [{ "ref": "string", "segment_id": "uuid", "version_id": "uuid",
                "authority": "regulations", "authority_rank": 2,
                "title": "string", "url": "string",
                "last_amended_on": "date | null", "captured_at": "datetime" }],
  "refusal_reason": "string | null"
}
```
- `governing_ref` is null when neither side governs by rank (ADR 0011).
- `gaps` lists in-scope pages and lists that a cited segment links to and the corpus
  does not hold (ADR 0017).
- `notices` carries the high-stakes notice and any other standing notice.

**Streaming.** With `Accept: text/event-stream`, the same endpoint sends server-sent
events: `stage` events (`searching`, `ranking`, `writing`, `checking`), then exactly one
`result` event carrying the response above, or one `error` event. Unvalidated text is
never streamed (ADR 0007). Because these are POST requests, clients read the stream with
`fetch` rather than `EventSource`.

**Privacy and retention**
- The MVP accepts no client data, and the UI tells users not to enter personal details.
- Question text is stored for evaluation and debugging. Retention period and redaction
  are Open, and must be decided before public launch.

## 5. AI behavior

**Model roles:**
- embeddings
- program classification (small model) *(Planned, ADR 0015)*
- question rewriting, planning and assessment (small model)
- answer generation (larger model)
- reranking
- extraction of requirements at ingest *(Proposed, ADR 0016)*
- eval judging (small model)

**What models never do:**
- decide eligibility
- answer from anything beyond the question and the evidence gathered for the request
- call tools or take actions; lookups and graph walks are run by code
- add a fact to the domain graph without a word-for-word quote that code has checked

**Untrusted text.** User questions and retrieved text are treated as data, not
instructions. With no tools and validation in code, a successful prompt injection can at
most produce a refusal or an unsupported claim, and validation removes unsupported claims.
The same holds at ingest: an instruction hidden in a page cannot become a graph fact
unless it is a verbatim quote that maps to a catalog entry.

**Output validation** (ADR 0003). Code:
- removes claims citing refs not retrieved, or rows not looked up, for this request
- refuses when no claim survives
- resolves conflicts by authority level, except those involving ministerial instructions
  and public policies, which it shows without naming a governing side (ADR 0011)
- attaches source dates, readiness and gap notices

**Failure handling:**
| Failure | Response |
| --- | --- |
| Model timeout (30 s) or error | A clear error, never a partial answer |
| Rate limiting from the model provider (HTTP 429) | Retry with backoff, then the same clear error |
| Output that fails the schema | One retry, then a refusal |
| Reranker unavailable | Fall back to fused order, and record the fallback |
| Program classifier unavailable or unsure | Search with no program filter |

**Model versions.** Deployments use the "upgrade once the current version expires" policy.
Each answer records the versions used, and evals re-run when any version changes.

**Prompts.** Prompts are versioned in code, and each answer records its prompt version.

**Human review:**
- Practitioners verify citations and report problems through feedback.
- Feedback is triaged by a human before any of it becomes an eval case.

**Quality.** Every metric is reported per program, with confidence intervals (ADR 0015).
- retrieval recall at 5 and MRR
- citation support
- conflict detection
- refusal accuracy
- program detection accuracy
- partial-coverage answers carrying the right gap notice
- coverage: the share of in-scope outbound links whose target is held, with a report
  ranking missing targets by how often they are cited (ADR 0017)
- extraction precision and recall per requirement catalog *(Proposed)*
- cost
- p50 and p95 latency

Eval categories: lookup, numeric, conditional, multi-hop, conflict, refusal, partial
coverage, program detection and high-stakes. Targets are in the product brief.

Comparisons that decide whether a feature stays:
- research mode against single-pass `/ask`, on the multi-hop and conditional categories
- link-following against similarity, for the reserved law slots
- the graph-walk checklist against a model-built checklist

## 6. Frontend boundary (Planned)
- **Demo page.** Server-rendered by the API, and enough to try the product.
- **Product frontend (later).** A separate deployable using a TypeScript client generated
  from the OpenAPI schema. It consumes the streaming contract and never talks to the
  database or the models directly.
- **CORS.** An explicit allowlist.
- **Authentication.** Open; required before the product frontend ships.

## 7. Operations

| | Development | CI | Eval job | Deployed |
| --- | --- | --- | --- | --- |
| Database | Postgres 17 + pgvector in a local container | Postgres service container, fixture data | Service container restored from a corpus snapshot | Azure Database for PostgreSQL Flexible Server |
| Models | Azure Foundry via `az login` | Fakes only | Azure Foundry via OIDC | Azure Foundry via managed identity |
| Runs | On demand | Every pull request | Retrieval metrics on PRs touching `src/` or `evals/`; judged metrics on `main` and on demand; weekly against a fresh snapshot | Container Apps (API) + Container Apps Job (nightly ingest) |

Development and CI are Current. The eval job and deployment are Planned.

**Deployment.** `azd up` with Bicep. Migrations run before the new revision takes
traffic, and follow expand-then-contract, so the running revision keeps working. The
LangGraph checkpointer's `setup()` runs in the same step.

**Scheduled work (Planned, ADR 0013):**
- Nightly ingest, bounded by the per-run limits, ending in a run report.
- A weekly corpus snapshot and eval run. A drop in scores raises an alert, because a
  corpus change can shift answers when no code changed.

**Reliability:**
- The API is stateless. Ingest never runs inside request handling.
- The demo scales to zero (cold starts are acceptable). The product deployment keeps at
  least one replica.
- Database backups use Flexible Server's automated backups.
- A bad page cannot go half-live: each source switches to its new version in one
  transaction, and rollback switches it back.

**Abuse and cost controls:**
- per-client rate limit on answer endpoints
- daily spend cap computed from `answers.cost_usd`, which returns a clear "try again
  tomorrow" error when reached
- per-run limits on new pages, embedding spend and corpus size
- budget alert on the resource group
- incremental ingest

**Fetching.** An identifying user agent, robots.txt respected, one request per second per
host, retries with backoff *(Current)*. Conditional requests where the host supports
them *(Planned)*: Justice Laws does; Canada.ca sends no `ETag` and reports the request
time as `Last-Modified`, so its pages are fetched and hashed every run.

**Observability.**
- Cost and latency are stored on every answer.
- OpenTelemetry instrumentation is Planned; the tracing backend is Open and must be
  decided before public launch.

**Secrets:**
- Entra authentication wherever it is supported.
- No keys in the repository.
- GitHub secret scanning with push protection.

## 8. Where hard rules are enforced
| Rule | Enforced by | Status |
| --- | --- | --- |
| Layer boundaries | import-linter contracts in CI | Current |
| LangGraph confined; no RAG frameworks | import-linter contracts in CI | Planned |
| Versions are append-only | Database trigger plus an integration test | Current |
| One current segment per ref; only current segments are searched | Partial indexes plus integration tests | Current |
| Unit tests never touch the network | pytest-socket in `tests/unit` | Current |
| No government text committed | `.gitignore` plus a CI check that fails if anything under `data/` is tracked | Current |
| Claims cite only retrieved segments or looked-up rows | Validation code plus unit tests; citation-support eval | Planned |
| Scope changes only by pull request | The scope policy is a file in git; ingest reads nothing else | Planned |
| A page matching no path rule is never ingested | Admission code plus tests; quarantine | Planned |
| Authority level is never inferred | Path rules only; no default level | Planned |
| A claimed readiness level is supported by results | CI check comparing the taxonomy file with the latest eval results | Planned |
| A graph fact has a verbatim quote | Extraction code plus tests | Proposed |
| No secrets committed | GitHub secret scanning push protection | Planned |
| Agents never edit eval cases or read `.env` | Claude Code permission deny rules | Planned |

## 9. Decisions and open questions
**Accepted and built:**
- 0001 Single service on Postgres with pgvector
- 0004 Local database, cloud models, fake providers in tests
- 0009 Source registry, versions and change detection
- 0010 Segments form a tree; embedding is decoupled from ingest
- 0011 Named authority levels replace the three tiers (the order itself is proposed)
- 0012 Links between segments are recorded; page slugs are derived

**Accepted, not yet built:**
- 0002 No RAG framework for retrieval and validation
- 0003 Model output is validated in code
- 0005 Information, not advice
- 0006 LangGraph for multi-step workflows
- 0007 Async I/O and progress streaming
- 0008 Evals run against pinned corpus snapshots
- 0013 Ingestion is automated and governed by a scope policy
- 0014 Lists that need exact matching are lookup tables
- 0015 All programs are covered, each at a stated readiness level
- 0017 Links are used for gap notices and coverage first

**Proposed:**
- 0016 A domain graph of requirements, with every fact tied to a quote

**Open, and blocking public launch:**
- Tracing backend.
- Question retention period and redaction.
- Authentication provider (blocks the product frontend).
- The audience: the brief says licensed practitioners; 0005 says applicants come first.

**Open, needing a practitioner:**
- Confirmation of the authority order, and precedence between the Regulations and
  ministerial instructions or public policies.
- Quebec selection programs: in or out.

**Open, to settle before the feature that needs it:**
- The confidence threshold for program detection.
- Path prefixes for every program section.
- Ref prefixes for the Citizenship Act and Regulations.
- Which segment levels are embedded and retrieved, and how long page sections are split.
- Whether admission by citation count is sticky.
- Whether rollback also holds a source, so the next run does not undo it.
- The per-run limits, and where alerts and run summaries are sent.
- Who writes and reviews requirement catalogs.
- Targets for program detection accuracy, gap notices and extraction precision.
- The row key for each lookup table, and whether each list is in its page or loaded by
  script.
- A parser for Canada Gazette pages.
- Whether the reranker endpoint supports Entra authentication.
- Checklist contract and thread expiry.

**Open:**
- Answer caching keyed on question, program and corpus version.
