# 0008 · Evals run against pinned corpus snapshots
Status: accepted (snapshot cadence amended by 0013: weekly and automatic)

## Context
Government page text cannot be committed, so CI has no corpus of its own. The corpus also
changes over time, which silently changes eval results even when no code changed.

## Decision
- A snapshot is a database dump of the corpus tables (sources, versions, segments with
  embeddings), stored in a private Azure Blob container and identified by id.
- The eval job restores a snapshot into a Postgres service container and runs evals with
  Azure models through OIDC.
- Each eval run records the snapshot id, git SHA, configuration and model versions.
- Cutting a new snapshot is a deliberate step. Eval cases whose expected refs no longer
  exist are flagged for human review.
- Pull request CI without the eval job uses fixtures only.

## Alternatives considered
- Evaluating against the deployed database: not reproducible, since the corpus drifts.
- Committing the corpus: conflicts with source licensing.
- Recorded embeddings alone: retrieval still needs the corpus.

## Consequences
- Eval results are reproducible and comparable across code changes.
- Published numbers cite a snapshot id.
- Storage cost is negligible, but snapshots need occasional refreshing.