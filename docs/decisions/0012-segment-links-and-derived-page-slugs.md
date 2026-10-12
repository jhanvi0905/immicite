# 0012 · Links between segments are recorded; page slugs are derived
Status: accepted

## Context
Officer instructions cite the clause they implement, and pages cite each other. Ingest
kept the words of a link and dropped its target. That lost the connection between an
instruction and its governing clause, and left no way to see which cited pages the
corpus lacks. On the first ten pages, 130 of 137 links to other Canada.ca pages pointed
at pages not in the corpus.

## Decision
- **Every link in a segment's own text is a row in `segment_links`**: its position, its
  origin, its words, the normalised target address, the fragment, a target class and the
  ref it names. Menus, breadcrumbs and "On this page" lists are not recorded.
- **Origins.** `html_link` for page hyperlinks. `xml_xref` for the cross-reference tags
  in the law XML. `text_mention` is reserved for refs written in plain text, which are
  not extracted yet; most references inside the law are of this kind.
- **A link names its target by ref and address, never by row.** There is no foreign key
  on the target. A target gets a new row with every version, and most targets are not
  held at all; those unresolved links are the coverage data.
- **A page's slug is derived from its address**, not chosen: `pdi-` for officer
  instructions, `ircc-` for other IRCC pages, `canada-` for the rest, followed by the
  path. A link to a page that is not in the corpus therefore already names the refs that
  page will have.
- **Heading text stays the identity of a page section; the publisher's anchor is stored
  beside it.** A link to `page.html#s12` resolves by matching the page's slug and the
  anchor. Anchors are not used as refs: on the first ten pages 53 of 125 were positional
  (`s1`, `s2`), and a positional anchor moves to different text when a section is added.
- **A law link names the most specific clause it can.** The address gives the section;
  when the link's words name a clause of that section, the ref includes it
  (`R205(c)(ii)`). The ref is what the link claims. Whether it exists is a join against
  current segments, not something ingest checks.
- **Target class comes from the address alone**: same page, law in the corpus, other
  law, officer instructions, IRCC page, Canada Gazette, other government, external.
- Links are written with their version and never changed. A changed link makes a new
  version of the source and does not cause re-embedding.

## Alternatives considered
- A JSON column on the segment: the main questions run backwards ("what cites R205?",
  "which missing pages are cited most?"), which a table with indexes answers directly.
- A foreign key to the target segment: breaks on every new version of the target and
  cannot represent a target that is not held.
- Anchor ids as refs: simpler matching, but a renumbered anchor silently repoints
  stored citations and eval cases.
- Hand-written slugs: a link could not name a page before someone had named it.
- Resolving links at ingest: the result would depend on the order sources were ingested.

## Consequences
- Derived slugs are long, and so are page refs. They are identifiers; people see titles.
- Classes that need more than the address (a list, a tool, an agreement) are not
  distinguished yet. They come with the scope policy.
- Retrieval can follow a link from an instruction to its clause, and conflict detection
  gets its candidate pairs. Neither is built; the data now exists for them.
- A page whose address changes gets a new slug and new refs.

## Amendment · planned additions
Not yet built.
- **Target classes** become: same page, law, ministerial instruction, officer
  instruction, public page, list, tool, federal–provincial agreement, provincial or
  outside site. Today's classes come from the address alone and cannot tell a list or a
  tool from any other page; the finer classes need the scope policy (0013).
- **Plain-text mentions** such as "subsection 205(c) of the Regulations" are extracted as
  the third origin. Most references inside the law are of this kind: only 104 section
  references are tagged across IRPA and IRPR.
- **How links are used** when answering is in 0017.
- **Considered and not adopted: anchor ids as page refs.** It was proposed so that
  incoming links resolve to the exact section. The stored anchor already does that, and
  heading-based refs stay stable when a publisher renumbers positional anchors.
