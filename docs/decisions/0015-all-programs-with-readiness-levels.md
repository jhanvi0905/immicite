# 0015 · All programs are covered, each at a stated readiness level
Status: accepted, not yet built

## Context
The product was scoped to three programs. Practitioners handle every program, and a tool
that answers three is one they must leave for most files. Covering everything at once
means quality will be uneven, and uneven quality that is not disclosed is worse than
narrow coverage.

## Decision
- **Coverage:** every program under IRPA, and citizenship. Passports are excluded.
- **Programs are defined in a taxonomy file in the repo**, as a tree: for example
  permanent residence → Express Entry → Canadian Experience Class.
- **Every program has a readiness level, shown on every answer:**
  - *indexed*: its sources are ingested.
  - *evaluated*: its own eval cases meet the targets.
  - *structured*: a requirement catalog and knowledge graph exist for it, and extraction
    precision meets its target (0016).
- PGWP, study permits and Express Entry go first. User demand decides the rest.
- **Program detection.** `program` is optional in a request. When it is missing, a small
  model classifies the question. Below a confidence threshold, search runs with no
  program filter. The response reports the programs used and their readiness.
- **High-stakes areas** (refugee claims, removals, inadmissibility) always carry a notice
  recommending a lawyer or licensed consultant.
- **Evals** are reported per program with confidence intervals, and add "program
  detection" and "high-stakes" categories. A CI check fails if the taxonomy file claims a
  readiness level the latest results do not support.

## Alternatives considered
- Staying at three programs until each is excellent: the product stays unusable for most
  of a practitioner's work.
- Covering everything with no readiness label: quality differences would be invisible.
- Asking the user to pick a program every time: friction, and users often do not know.

## Consequences
- Quality is claimed only for programs that have been measured.
- The classifier is a new model role and a new way to be wrong: a misdetected program
  filters out the right sources. Falling back to no filter bounds the damage.
- The eval set grows and is partitioned by program.

## Open
- The confidence threshold for program detection.
- Quebec selection programs: in or out.
- Ref prefixes for the Citizenship Act and Regulations. `A` and `R` mean IRPA and IRPR
  today, so new prefixes are needed before either is ingested.
