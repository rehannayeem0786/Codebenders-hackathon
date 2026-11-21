# Corpus note for graphify

`corpus/` holds the raw source text that the curation pipeline extracts rules
from. Nothing in the running app reads these files: the app reads
`data/schemes.json`. The corpus exists so that every rule in that JSON can be
traced back to a document a human can open and re-verify.

## Why a corpus at all

Problem Statement 5 is explicit that the citizen must be able to see *which*
rule a match is based on, and that an unchecked claim is worse than no claim.
Two habits follow from that:

1. **Every rule cites a source.** `source_url`, `source_name` and `verified_on`
   travel with each scheme in the catalogue.
2. **Every rule carries a provenance tag**, the same vocabulary graphify uses
   for its edges:

   | tag | meaning |
   |---|---|
   | `EXTRACTED` | read directly off the official page / notification |
   | `INFERRED` | derived by us (cross-referencing a notification, press release or order) |
   | `AMBIGUOUS` | the rule or the amount changed recently and a human must re-check it |

## The extraction pipeline

```
corpus/*.md  ──►  graphify  ──►  graphify-out/graph.json  ──►  /api/graph
                  (LLM reads     (nodes + links, each link     (merged with the
                   the docs)      tagged with provenance)      curated graph)
```

`scripts/graphify_build.ps1` runs that middle step:

```powershell
pip install graphifyy
python scripts/graphify_build.ps1
```

The backend imports the result automatically on startup when
`GRAPHIFY_AUTO_IMPORT=1` (the default) and `graphify-out/graph.json` exists.
`/api/health` reports how many extracted nodes and tagged edges were merged, and
how many of them *bridge* into a curated scheme or rule. If the file is absent
the app still works: the curated graph is self-sufficient, and the status pill simply
reads `graphify: off - curated graph only`.

## Adding a document

1. Drop a markdown file here with the scheme's official text (copy/paste from
   the portal is fine, keep the URL at the top).
2. Run the script, then check `/api/graph` or the "Why it matched" tab.
3. Update `data/schemes.json` only if the corpus reveals a rule we got wrong -
   and change `verified_on` when you do.
