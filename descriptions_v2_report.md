# Auto-fill descriptions — v2 upgrade report

This report documents the upgrade of `real_estate/claude_descriptions.py` from
its v1 implementation (Haiku 4.5, no web search) to v2 (Sonnet 4.6 with
Anthropic's built-in `web_search` server tool and an `INSUFFICIENT_INFO`
fallback).

## 1. Decisions

### 1.1 Search method — built-in `web_search` server tool

Two paths were considered:

1. **Anthropic-hosted `web_search` server tool** — Claude performs the
   search and gives us back the final response with citations. We pay
   per search request, no infrastructure on our side.
2. **Client-side tool** — we declare a `search` tool, run it ourselves
   (e.g. via DuckDuckGo, Brave, Tavily), and feed results back to Claude
   in a multi-turn loop.

**Chosen: option 1, the built-in tool.** Reasons:

- Single API call instead of an in-process tool-loop. Less code, fewer
  failure modes, no extra dependency in `requirements.txt`.
- Citations are tracked by the API itself (`web_search_result_location`
  blocks) without us having to thread URLs through the loop.
- Domain filtering, max-uses, and IL geographic locale are first-class
  configuration on the tool block; no need to re-implement them.
- The client-side path would force us to pick a specific search provider
  with its own API key and quota, expanding the operations surface for
  a single appraiser.

Source consulted:
<https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool>
— "Web search tool" page, accessed 2026-05-07. The tool block used is
`{"type": "web_search_20250305", "name": "web_search"}`. We deliberately
did **not** use the newer `web_search_20260209` tool variant because it
requires the code-execution tool to be enabled and the dynamic-filtering
benefit is small for a 3-4 sentence Hebrew paragraph; pricing is the
same.

### 1.2 Model — `claude-sonnet-4-6`

Verified against
<https://platform.claude.com/docs/en/about-claude/models/overview>
(Models overview, accessed 2026-05-07). Sonnet 4.6 is the latest
generally-available Sonnet (`claude-sonnet-4-6`) at \$3 input / \$15
output per MTok. Haiku 4.5 produced unacceptable Hebrew quality in
practice — that is the reason for upgrade.

Opus 4.7 was considered and rejected: ~5× the input cost and 1.7× the
output cost for a paragraph-length task whose quality bar Sonnet
already meets.

### 1.3 INSUFFICIENT_INFO sentinel

The system prompt instructs the model to return only the literal string
`INSUFFICIENT_INFO` when web search did not surface information specific
to the requested place. The wrapper `try_describe_*` functions detect
this string and return `None`, which preserves the existing
"יש להשלים — תיאור השכונה" placeholder in `web.py`. Per CLAUDE.md A.3
("a placeholder is better than a wrong description"), this is the
correct degradation path for unknown neighborhoods.

The web.py handler did not need code changes — it already treats
`None` as "use the placeholder", and the new wrappers map both API
failure and INSUFFICIENT_INFO to `None`.

## 2. Implementation summary

| File | Change |
|---|---|
| `real_estate/claude_descriptions.py` | Rewritten: model → Sonnet 4.6; `web_search_20250305` tool added with IL locale and `max_uses=5`; system prompt rewritten with Hebrew-only language constraint and INSUFFICIENT_INFO contract; new `_extract_text` helper to skip server-tool blocks. |
| `tests/test_claude_descriptions.py` | New tests: Hebrew-only language check (rejects Arabic / CJK / Cyrillic), known-neighborhood specificity check (output mentions "פלורנטין"), unknown-neighborhood graceful fallback (returns `None`). Existing footnote test retained. |
| `CLAUDE.md` | Part B.11 rewritten to describe the new behaviour, model, search tool, INSUFFICIENT_INFO contract, and rough cost. |
| `real_estate/web.py` | **No change required.** Existing `try_describe_*` → `if generated:` flow already handles `None` correctly. |

## 3. Live example outputs

**Status: not produced in this run.**

The local environment in which this branch was developed does not have
`ANTHROPIC_API_KEY` set (verified via `env`). Without the key the
integration tests skip (the existing project convention) and live
descriptions cannot be produced on demand.

To collect the requested examples, run on a host with
`ANTHROPIC_API_KEY` set:

```bash
pip install -q -r requirements.txt
python - <<'PY'
from real_estate import claude_descriptions as cd
print("=== תל אביב ===")
print(cd.describe_city("תל אביב"))
print("=== פלורנטין, תל אביב ===")
print(cd.describe_neighborhood("תל אביב", "פלורנטין"))
print("=== ירושלים ===")
print(cd.describe_city("ירושלים"))
print("=== רחביה, ירושלים ===")
print(cd.describe_neighborhood("ירושלים", "רחביה"))
print("=== רמת גן ===")
print(cd.describe_city("רמת גן"))
print("=== נווה גן, רמת גן ===")
print(cd.describe_neighborhood("רמת גן", "נווה גן"))
print("=== unknown (must be INSUFFICIENT_INFO or None via wrapper) ===")
print(repr(cd.try_describe_neighborhood("תל אביב", "שכונה דמיונית 12345")))
PY
```

The integration test suite at `tests/test_claude_descriptions.py`
exercises the same six places plus the unknown-neighborhood case and
the Hebrew-only constraint; it is the canonical place to validate the
upgrade once a key is available.

## 4. Cost estimate per call

Pricing (verified against
<https://platform.claude.com/docs/en/about-claude/models/overview> and
the web-search-tool page):

- Sonnet 4.6: **\$3 / 1M input tokens**, **\$15 / 1M output tokens**.
- Web search: **\$10 / 1,000 searches** on top of token usage.

Worked estimate per `describe_neighborhood` call (typical):

| Cost component | Amount | Subtotal |
|---|---:|---:|
| Web searches (1-2 calls) | ≈ 1.5 × \$0.01 | \$0.015 |
| System prompt + user prompt (input) | ≈ 700 tokens | \$0.0021 |
| Search-result content fetched into context (input) | ≈ 4,000 tokens | \$0.012 |
| Final paragraph (output) | ≈ 150 tokens | \$0.00225 |
| Tool-use / scratchpad output (output) | ≈ 200 tokens | \$0.003 |
| **Per call (rough)** | | **≈ \$0.034** |

`describe_city` is in the same range (slightly cheaper because city
pages are usually well-indexed and one search suffices).

For a single appraiser producing a few reports per day with one
city + one neighborhood call each, this is on the order of a few US
cents per report — negligible relative to the appraisal fee, and the
Web handler's graceful-degradation path means an outage or quota event
falls back to "יש להשלים" rather than blocking the report.

The bulk of the cost is the search-result tokens flowing into the
input window, not the output paragraph. If volume grows, prompt
caching of the system prompt (\$0.30 / MTok cache reads) would cut a
small additional amount; not worth the complexity for current scale.

## 5. Verification done locally

- Module imports cleanly with model `claude-sonnet-4-6`, sentinel
  `INSUFFICIENT_INFO`, tool `web_search_20250305`.
- `pytest tests/` passes: 6 golden-report assertions pass; 12
  integration tests skip cleanly without the API key.
- `web.py` wiring inspected — `try_describe_*` continues to return
  `None` on INSUFFICIENT_INFO, falling back to the existing placeholder.

## 6. Open follow-ups (not part of this branch)

- Run the integration tests on a host with `ANTHROPIC_API_KEY` and
  paste a sample of three city descriptions and three neighborhood
  descriptions back into this report.
- Consider adding prompt caching once volume is high enough to matter.
- The pre-existing `payload.address` bug (CLAUDE.md C.1) is unrelated
  to this branch and is left for a separate fix.
