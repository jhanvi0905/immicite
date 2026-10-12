# 0017 · Links are used for gap notices and coverage first
Status: accepted, not yet built

## Context
Links are recorded (0012). An answer drawn from a section that defers a key condition to
a page the corpus lacks is correct as far as it goes and looks complete. Nothing told
the reader otherwise.

## Decision
- **Gap notices.** When a cited segment links to an in-scope page or list that is not
  held, the answer says so and gives the official link. The answer response gains a
  `gaps` field.
- **Coverage metric.** Per program: the share of in-scope outbound links whose target is
  held, and a report ranking missing targets by how often they are cited.
- **Whether a target is held is computed when reading**, never stored, because it goes
  stale the moment the target is ingested.
- **Following links during retrieval comes later, and only if evals show it helps.** It
  would fill the slots reserved for law by following links one hop, and only upwards in
  authority, instead of choosing law by similarity. It is built behind a flag and both
  settings are compared in evals.
- A "partial coverage" eval category is added: the answer must be correct as far as it
  goes and carry the right gap notice.

## Alternatives considered
- Using links in ranking from the start: a guess until evals exist to judge it.
- Refusing whenever a cited section has an unheld link: most sections have one, so most
  answers would be refusals.
- No notice: the partial answer is the failure this product exists to avoid.

## Consequences
- An answer can be complete in its claims and still carry a gap notice. The two are
  reported separately.
- The coverage report is the measure of how far ingestion (0013) has to go per program.
