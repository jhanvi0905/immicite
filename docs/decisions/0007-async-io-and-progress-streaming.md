# 0007 · Async I/O and progress streaming
Status: accepted

## Context
A frontend with real users means concurrent requests, each waiting several seconds on
model calls. FastAPI recommends `async def` when the libraries in use support `await`.
The model SDK, psycopg 3, SQLAlchemy, httpx and LangGraph all do. Answers are validated
only after generation completes (0003).

## Decision
- Request handling, database access, model calls and workflows are async end to end:
  async FastAPI handlers, SQLAlchemy asyncio on psycopg 3, the async OpenAI client and
  LangGraph's async checkpointer.
- Answer endpoints offer server-sent events: progress `stage` events, then one validated
  `result` event.

## Alternatives considered
- Synchronous handlers in FastAPI's threadpool: workable at low load, but streaming
  becomes awkward, and switching later would touch every layer.
- Streaming generated tokens: feels faster, but shows users sentences that validation may
  then remove.

## Consequences
- Tests run under an async test runner.
- Blocking work (XML parsing) stays in the ingest job or is moved off the event loop.
- Users see progress within a second and the full validated answer at the end.