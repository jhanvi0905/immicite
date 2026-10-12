# immicite

> **Not immigration advice.** A research aid built for licensed practitioners, not
> affiliated with or endorsed by IRCC or the Government of Canada.
> Read the [disclaimer](DISCLAIMER.md).

Cited answers on Canadian immigration rules. Every claim links to the exact clause of the
Act, the Regulations or IRCC guidance that supports it, ranked by legal authority and
dated. When the evidence does not support an answer, it refuses.

**Status: early development.** Ingestion works: the Act, the Regulations and a starter
set of IRCC pages are pulled into Postgres as versioned, clause-level segments. Search
and answers are not built yet; see the milestones in the
[product brief](docs/product-brief.md).

## Why
Practitioners work from three layers of official sources that do not always agree: the
law, officer instructions and public guidance. General-purpose AI assistants blend them,
cite whole pages at best, and answer confidently when the evidence is thin.

immicite is designed around five commitments:

- **Clause-level citations.** A claim points to a specific paragraph, such as
  `R205(c)(ii)`, not to a page.
- **Authority ranking.** Law governs officer instructions, which govern public guidance.
  When levels disagree, the answer shows both and says which one governs.
- **Dated answers.** Every response states the dates of the sources it relied on.
- **Calibrated refusal.** No supporting clause, no claim. It states the rules that
  apply and never decides whether a person qualifies.
- **Measured quality.** Retrieval, citation support, conflict detection and refusal
  accuracy are evaluated against a human-written eval set.

## Quickstart
Requires [uv](https://docs.astral.sh/uv/) and a container runtime (Docker or OrbStack).

```sh
uv sync
cp .env.example .env
docker compose up -d             # Postgres 17 + pgvector
uv run alembic upgrade head      # create the schema
uv run immicite ingest           # pull every source in sources.yaml
uv run immicite status           # what the corpus holds
uv run pytest
```

## Repository layout
```
src/app/
  api/            request/response boundary
  domain/         business rules: authority levels, refs, links, citation validation
  services/       workflow orchestration
  integrations/   model and external-service clients
migrations/       database schema (Alembic)
sources.yaml      the documents that make up the corpus
tests/            unit and integration tests
evals/            human-written eval cases and the runner
docs/             product brief, architecture and decision records
```

## Documentation
- [Product brief](docs/product-brief.md): the problem, scope, targets and milestones.
- [Architecture](docs/architecture.md): components, flows, contracts and hard rules.
- [Decisions](docs/decisions/): the accepted architecture decision records.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
Found a wrong or outdated citation? Open a
[citation report](https://github.com/jhanvi0905/immicite/issues/new/choose).
Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Citing
Use the **Cite this repository** button on GitHub, or see [CITATION.cff](CITATION.cff).

## License
[Apache-2.0](LICENSE). Government of Canada content is not covered by this license; see
the [disclaimer](DISCLAIMER.md).
