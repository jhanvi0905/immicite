# 0006 · LangGraph for multi-step workflows
Status: accepted (the checklist would move onto the graph under 0016, which is proposed)

## Context
Multi-hop questions and scenario checklists need loops, typed state, persistence across
requests and pauses for practitioner input. The single-pass /ask path needs none of these.

## Decision
- Use LangGraph for research mode and the checklist, in `services/workflows/` only.
- Graph nodes call existing domain functions and ports, and every graph ends in the
  shared validation (0003).
- Checkpoints use LangGraph's async Postgres checkpointer in the existing database.
- State holds refs and ids, not full objects.
- Interrupts sit in dedicated nodes with no side effects before them, because a resumed
  node re-runs from its start.
- Retrieval loops are capped at two rounds.

## Alternatives considered
- A hand-written state machine: checkpointing and resumable pauses would have to be
  rebuilt.
- LangChain chains for the whole system: hides the core logic (0002).
- An autonomous tool-using agent: unbounded loops and cost, in a domain that needs
  predictable, auditable steps.

## Consequences
- LangGraph is a dependency, confined to one package by import-linter.
- Checkpoint tables are created by the checkpointer's setup step during deployment.
- Multi-hop quality, cost and latency are compared against /ask in evals.