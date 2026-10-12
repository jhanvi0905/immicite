# 0014 · Lists that need exact matching are lookup tables
Status: accepted, not yet built

## Context
"Is this program eligible?" and "Is this school a designated learning institution?" are
answered by one row of a long official list. Similarity search over a long table is
unreliable: it returns near neighbours, and a near neighbour is a wrong answer.

## Decision
- A list that needs exact matching is ingested as **versioned rows with a key**, not as
  text segments, and is checked by exact lookup.
- Code runs the lookup and passes the row in as evidence. The model does not call it.
  It is available to the single-pass answer as well as to research mode.
- **Row refs** are `<table-slug>#<row-key>`. An answer cites the row with the list's date.
- Tables are versioned like any other source, so a citation can show the row as cited.
- **A list loads automatically only when a parser for it exists in the repo.** A list
  without one is recorded as a link, and answers link out to it. A parser is code and
  arrives by pull request.
- First lists, in order: eligible fields of study, the DLI list, the fee schedule. More
  are added per program.

## Alternatives considered
- Tables as ordinary text segments: retrieval cannot guarantee the right row.
- Letting the model call a lookup tool: breaks the rule that models take no actions.
- A generic table parser: unknown layouts cannot be parsed safely.

## Consequences
- A second kind of evidence exists beside segments, and validation must accept a row ref
  when that row was looked up for the request.
- A missing or stale table is a visible gap (0017), not a silently wrong answer.

## Open
- Whether each list is in the page or loaded by script. The DLI list is unverified.
- What the row key is for each list, and how a question is matched to a key.
