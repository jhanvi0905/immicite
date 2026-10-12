# 0002 · No RAG framework for retrieval and validation
Status: accepted (scope narrowed by 0006)

## Context
Retrieval, authority ranking and citation validation are the core of the system and must
be readable, testable and measurable step by step.

## Decision
Retrieval, ranking, generation and validation are plain Python with Pydantic and small
provider ports. LangChain retrievers, vector stores and loaders, and LlamaIndex, are not
used anywhere, enforced by import-linter. Multi-step workflows are covered by 0006.

## Alternatives considered
- LangChain or LlamaIndex for the whole pipeline: faster to start, but they hide the logic
  under review and make ablations harder.
- Semantic Kernel: fits Azure, but carries the same abstraction cost for this scope.

## Consequences
More code is written by hand. Each step is a function that is unit-tested with fakes and
can be switched on or off in evals.