# 0011 · Named authority levels replace the three tiers
Status: accepted and built (narrows 0003). The order of the levels is proposed, pending
confirmation by a practising consultant.

## Context
Three numbered tiers (law, officer instructions, public guidance) did not fit the
sources. The Act governs the Regulations, so "law" was two levels in one. Officer
instructions also cite ministerial instructions and public policies, which are binding
and had no tier at all. Numbered tiers also make any new level a renumbering.

## Decision
- Five named levels, highest first: **Act** (IRPA, and the Citizenship Act when
  ingested), **Regulations** (IRPR, and the Citizenship Regulations), **ministerial
  instructions and public policies**, **officer instructions**, **public guidance**.
- **The order lives in one domain module.** If a practitioner corrects it, only that
  list changes.
- The API returns both the level's name and its rank.
- Levels are rows in an `authority_levels` table with a rank. A source refers to its
  level by name. The API and the manifest use the name, never a number.
- Rank orders the levels and decides most conflicts: the higher level governs.
- **Rank does not decide a conflict between the Regulations and a ministerial instruction
  or public policy.** Such an instrument can lawfully set rules the Regulations do not,
  or exempt people from one. Those conflicts are shown with both sides and no governing
  side is named. This narrows 0003, which resolved every conflict by rank.

## Alternatives considered
- Keeping three tiers and filing ministerial instructions under "law": hides that they
  rank below the Act and behave differently from the Regulations.
- A strict five-step ladder: would name the Regulation as governing in exactly the cases
  a public policy exists to change.
- A numeric column with gaps (10, 20, 30): still ties meaning to numbers in every query.

## Consequences
- The schema, manifest, CLI and API contract say `authority`, not `tier`.
- No ministerial instruction or public policy is in the corpus yet. The level exists so
  that adding them needs no further schema change.
- **Open, needs a practitioner:** the exact precedence between the Regulations and each
  kind of level-three instrument. Until it is settled the system shows, and does not
  resolve, those conflicts.
- Eval cases for conflicts must say which pairs have a governing side and which do not.
- The order is currently held twice: in the domain module and in the `authority_levels`
  table seeded from it. A change needs both until the table is derived from the module.
