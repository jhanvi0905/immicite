# 0004 · Local database, cloud models, fake providers in tests
Status: accepted

## Context
Development happens on an 8 GB laptop where local models are impractical. Published
numbers must come from the same models used in development.

## Decision
Postgres runs locally in a container. Development calls Azure Foundry models with Entra
sign-in. Unit and integration tests use deterministic fake providers and no network.

## Alternatives considered
- Local models through Ollama: too heavy for the hardware, and their scores would differ
  from the published ones.
- Developing against an Azure database: slow round trips, and it spends free-tier hours.

## Consequences
Development and published scores share one set of models. Tests are free and offline.
Any OpenAI-compatible endpoint can replace Azure through configuration. Development
needs network access and an Azure sign-in.