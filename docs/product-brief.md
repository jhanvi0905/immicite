# Product brief: canada-immigration-rag

## One line
Cited answers on Canadian immigration and citizenship rules for licensed practitioners.
Every claim links to the exact clause of the Act, the Regulations or IRCC guidance, ranked
by legal authority, dated, and refused when unsupported.

## Problem
Immigration practitioners work from several layers of official sources that do not always
agree. Public IRCC pages simplify the rules, officer instructions add operational detail,
ministerial instructions and public policies adjust them, and the Act and Regulations
govern. Practitioners cross-check these layers by hand on nearly every file. The costly
mistakes happen where the layers quietly disagree, or where one was updated and another
was not.

General-purpose AI assistants make this worse. They blend sources, cite whole pages at
best, rarely say how current their information is, and answer confidently when the
evidence is thin. A practitioner cannot put that output in front of a client or an
officer without redoing the research.

## What makes it different
- **Clause-level citations.** Claims point to a section, subsection or paragraph, such as
  a specific regulation paragraph, not to a page.
- **Authority ranking.** Every piece of text carries its authority level. When levels
  disagree, the answer shows both and states which one governs.
- **Dated answers.** Every response states the dates of the sources it relied on.
- **Calibrated refusal.** When the evidence does not support an answer, the product says
  what it searched for and could not find.
- **Measured quality.** Retrieval accuracy, citation support, conflict detection, refusal
  accuracy, cost and latency are measured and published.
- **Honest about readiness.** Every answer states how well its program is covered:
  indexed, evaluated or structured. It also says when a source it relied on points to
  material the corpus does not hold.
- **Rules as structure.** For structured programs, requirements, the facts they depend on
  and the documents that evidence them are held as a graph, each tied to the exact quote
  that states it.

## Product principles
1. **Cite or stay silent.** No claim appears without a supporting clause.
2. **Authority beats clarity.** A clearer but lower-authority source never silently
   overrides a higher one.
3. **Date everything.** A practitioner always knows how current an answer is.
4. **Inform, never decide.** The product states the rules that apply. It never says
   whether a particular person qualifies.
5. **Measure before claiming.** Targets are set before building and checked on every
   change. Quality is claimed only for programs that have been measured.

## Scope
**Corpus, in five authority levels.** Higher levels govern lower ones, with one exception
noted below. The order is pending confirmation by a practising consultant.
| Level | Source | Examples |
| --- | --- | --- |
| Act | Justice Laws consolidated XML | Immigration and Refugee Protection Act (IRPA); Citizenship Act |
| Regulations | Justice Laws consolidated XML | Immigration and Refugee Protection Regulations (IRPR); Citizenship Regulations |
| Ministerial instructions and public policies | Canada Gazette and IRCC | Express Entry and PGWP instructions |
| Officer instructions | IRCC program delivery instructions | Instructions officers follow when assessing files |
| Public guidance | IRCC applicant-facing pages | Program eligibility and how-to-apply pages |

A ministerial instruction or public policy can lawfully depart from the Regulations, so a
conflict between those two is shown with both sides and no governing side is named.

**What enters the corpus**
| Target | Action |
| --- | --- |
| Law: IRPA, IRPR, the Citizenship Act and Regulations | In; links resolve to the exact clause |
| Ministerial instructions and public policies | In, at their own authority level |
| Officer instructions | Always in: every program section, plus any the corpus links to |
| IRCC public pages | In, by scope rules |
| IRCC lists: DLI list, eligible fields of study, fee schedule | In, as lookup tables |
| IRCC interactive tools, such as the language calculator | Never ingested; answers link to them |
| Federal–provincial agreements, such as Canada–Quebec | Recorded, not ingested |
| Provincial and outside sites | Never ingested; answers flag them as outside our sources |

**Programs:** every program under IRPA, and citizenship. Passports are excluded. Quebec
selection programs are an open question. Programs are defined in a taxonomy held in the
repository.

**Readiness.** Each program is at one of three levels, shown on every answer:
- *indexed*: its sources are ingested.
- *evaluated*: its own eval cases meet the targets.
- *structured*: a requirement catalog and knowledge graph exist for it.

PGWP, study permits and Express Entry go first, because they are high-volume and
interlock: study permits lead to PGWPs, which lead to the Canadian Experience Class. User
demand decides the order of the rest.

**Language:** English. The data model must not assume English, so French can be added
without restructuring.

## Capabilities and acceptance criteria
1. **Cited question answering.** A plain-language question returns an answer in which
   every factual claim cites at least one specific clause, with its authority level,
   title and date.
   *Accepted when:* no claim lacks a citation, and every cited clause supports its claim.
2. **Authority-aware retrieval and conflict surfacing.** Questions touching several
   levels retrieve from all of them. Where levels diverge, the answer presents both and
   marks the higher level as governing, except where a ministerial instruction or public
   policy is involved.
   *Accepted when:* every seeded cross-level conflict in the eval set is detected, and
   each one that has a governing side is resolved in its favour.
3. **Calibrated refusal and scope control.** Unsupported questions are refused with a
   statement of what was searched. Questions asking whether a person qualifies are
   answered with the applicable rules, never a verdict. Questions outside immigration and
   citizenship are identified as out of scope.
   *Accepted when:* refusals are correct at the target rate, and answerable questions are
   rarely refused.
4. **Program detection.** A question need not name its program. The product works out
   which programs it concerns, and searches everything when it is not confident.
   *Accepted when:* detection meets its accuracy target, and a low-confidence question is
   never narrowed to the wrong program.
5. **Readiness shown.** Every answer states the readiness level of the programs it drew
   on. Questions in high-stakes areas (refugee claims, removals, inadmissibility) carry a
   notice recommending a lawyer or licensed consultant.
   *Accepted when:* no answer is returned without its readiness level, and every
   high-stakes answer carries the notice.
6. **Gap notices.** When a cited source points to an in-scope page or list the corpus
   does not hold, the answer says so and gives the official link.
   *Accepted when:* partial-coverage eval cases return an answer that is correct as far
   as it goes, with the right gap notice.
7. **Exact answers from lists.** Questions answered by one row of an official list, such
   as an eligible field of study or a designated learning institution, are answered by an
   exact lookup and cite the row with the list's date.
   *Accepted when:* list questions return the right row or a clear "not on the list".
8. **Research mode.** Questions that chain several rules are answered as a sequence of
   cited steps. For structured programs it follows the pathways in the graph.
   *Accepted when:* multi-step eval cases score higher than the single-pass answer.
9. **Scenario checklist.** For structured programs, a scenario returns the requirements
   and documents that apply, read from the graph. It asks for any missing fact that
   changes the result. Each item is cited. For other programs it says the checklist is
   not available and offers research mode.
   *Accepted when:* reference scenarios return the expected items, all cited, none
   invented, and none missing.
10. **"As of" dates.** Every response lists the capture or amendment dates of its sources.
    *Accepted when:* no response is returned without them.
11. **Source view.** Any cited clause opens in context with its authority level, dates
    and official link.
    *Accepted when:* every citation in every response resolves to a viewable clause.

## Success metrics
Targets are fixed before the build so they cannot drift to match results. Every metric is
reported per program, with confidence intervals.
| Metric | Target |
| --- | --- |
| Expected segments in the top 5 retrieved | ≥ 90% of eval cases |
| Cited clauses that support their claims | ≥ 95% |
| Seeded cross-level conflicts detected | 100% |
| Correct refusals | ≥ 90% |
| Program detection accuracy | Target to be set before the classifier is built |
| Partial-coverage answers carrying the right gap notice | Target to be set with the first cases |
| Coverage: in-scope links whose target is held | Reported per program |
| Extraction precision | Reported per requirement catalog; target to be set |
| Cost and latency per answer | Reported (p50 and p95); no fixed budget in the MVP |

The eval set grows from 25 human-written questions to about 120. Its categories are
lookup, numeric, conditional, multi-hop, conflict, refusal, partial coverage, program
detection and high-stakes.

## Risks and mitigations
| Risk | Mitigation |
| --- | --- |
| Being mistaken for immigration advice | Practitioner positioning, refusal of verdicts, a disclaimer and transparency note |
| Silent blending of sources | Authority level is a first-class field; conflict cases in the eval set |
| Plausible but unsupported claims | Schema-enforced citations plus a code-level post-check |
| Stale answers | Source dates on every response; versions are kept; nightly ingestion |
| Uneven quality across programs | Readiness level on every answer; quality claimed only where measured; a CI check on claimed readiness |
| High-stakes questions | A standing notice recommending a lawyer or licensed consultant |
| Wrong program detected | Search with no program filter below a confidence threshold; detection is an eval category |
| Partial answers that look complete | Gap notices; a coverage metric per program; a partial-coverage eval category |
| Bad pages entering automatically | Scope policy changed only by pull request; unknown pages quarantined; quality checks; per-run limits; rollback |
| Licence problems if commercialised | No government page text committed; law under the Open Government Licence; non-affiliation statement |
| Eval leakage | Questions written by a human, before retrieval is built, plus a held-out set |

## Delivery
The phases give the intended order. When each item is built is decided as the work
proceeds, and nothing here is a date.

**Phase 1, core.** Skeleton · schema · law ingestion (IRPA, IRPR) with XML
cross-references · first 25 eval cases · baseline retrieval · hybrid search and reference
router · cited answers.

**Phase 2, full corpus.**
- Automated ingestion across all programs: taxonomy, program detection, the Citizenship
  Act and Regulations, authority levels, links, officer instructions, gap notices. Every
  program starts as *indexed*.
- Then lookup tables, the reranker, about 120 eval cases, per-program reporting and
  corpus snapshots. PGWP, study permits and Express Entry become *evaluated*.

**Phase 3, ship.** Research mode · deployment, demo and launch blockers · public launch.

**Phase 4, structure.**
- Ontology and knowledge graph with the PGWP catalog; PGWP becomes *structured*.
- The checklist, on the graph.
- Catalogs and eval cases for further programs by demand, cross-program pathways, and
  change impact.

## Future direction
- A practitioner-facing product (working name IRCC Compass) on top of the same API.
