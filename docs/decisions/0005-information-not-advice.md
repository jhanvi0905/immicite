# 0005 · Information, not advice
Status: accepted (replaces "Built for practitioners, not applicants")

## Context
First users will be applicants and students arriving from Reddit and similar communities.
Practitioners may become users later. Applicants ask "do I qualify?", share personal
details, and may act on answers without a professional. Whatever the audience, the
system must not act as an immigration advisor.

## Decision
- The system explains rules. It never gives a verdict on whether a person qualifies.
- A verdict-seeking question gets the applicable requirements as a cited checklist the
  person can check against their own situation, plus pointers to IRCC's official tools
  and to licensed representatives.
- Every claim is cited, and the system refuses when unsupported (0003).
- Answers are in plain language; legal refs appear as sources, not inside sentences.
- Personal details are not needed and are discouraged. Stored question text is redacted
  before storage and kept for a limited period, set before launch.
- The applicant-facing tool is free. Charging for anything that could read as advice
  needs a separate decision and a legal review first.
- This decision does not fix the audience; it applies to applicants and practitioners alike.

## Alternatives considered
- Practitioners only: no channel to reach them yet.
- Giving eligibility verdicts: the most engaging option, and the most likely to cause harm.
- Storing no questions: the safest option, but it removes real usage from evals and
  debugging.

## Consequences
- Less instant gratification than a yes/no bot. The checklist becomes a core feature.
- PII redaction becomes a launch requirement.
- The eval set adds applicant-style phrasing and verdict-seeking questions.