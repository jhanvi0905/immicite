# 0003 · Model output is validated in code
Status: accepted (conflict resolution narrowed by 0011)

## Context
Practitioners rely on every citation. Prompt instructions cannot guarantee correct
citations, refusals or legal precedence.

## Decision
Models return structured output in which every claim carries refs. Code then:
- removes claims citing refs not retrieved for the request
- refuses when no claim survives
- resolves cross-tier conflicts by tier rank
- attaches source dates
Every endpoint and workflow passes through the same validation.

## Alternatives considered
- Trusting model citations: unverifiable, and fails silently.
- A runtime LLM verifier: adds cost and latency and is still probabilistic. It is kept for
  offline evals only.

## Consequences
- Some correct but uncited statements are dropped, which favours precision.
- Raw generated text is never streamed to users; progress is streamed instead (0007).
- Citation support is measured by evals, not assumed.