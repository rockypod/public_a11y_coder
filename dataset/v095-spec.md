# a11y-public-coder v0.9.5 — Dataset Specification

**Status:** specification only. No generation yet. Run after neotoi-coder v3.2 training completes and rockypod GPU is free.

**Scope:** ~110 new training pairs across 8 existing tiers + 1 new tier (19). Combined with the existing 1,930 v0.9.0 entries, v0.9.5 dataset target is **~2,040 entries**.

**Driving signals:**
1. Per-question failure analysis from the v0.9.0 30Q exam (both 4B and 14B)
2. New companion product — `a11y-public-agent` — needs training data for the model to understand how to discuss, use, and extend it

---

## Part 1 — Exam-driven additions to existing tiers

### Tier 7 — drush-cli (+15 entries)

Highest ROI. Both models weak. Root cause: 30B teacher fabricated flags during v1.0 generation, default-accept CRAFTED℠ missed them.

| Sub-topic | Entries | Pattern |
|---|---|---|
| Command order (Q11) | 3 | `drush updb -y && drush cr` — explicit rationale for ordering: enable → updb → cr |
| Config export flags (Q12) | 3 | `drush cget`, `drush cex --partial`, `drush config:status` — verified against `drush help` |
| Common agency workflows | 5 | Site deploy sequence, module enable + updb + cr, content type update, user role audit, watchdog inspection |
| Negative: fabricated flags | 4 | "`drush config:export --target` does not exist" / "`drush cr --exclude` is not a valid flag" — explicit refutation pairs |

**Validation requirement:** every flag mentioned in generated entries must be verified against `drush help <command>` output. Add a `--validate-drush` pre-flight pass to the RAFT pipeline before CRAFTED℠.

### Tier 8 — drush-commands (+5 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| `accessCheck()` in custom commands (Q13) | 3 | Entity query inside DrushCommands must call `->accessCheck(FALSE)` or `->accessCheck(TRUE)` explicitly since Drupal 9.2 |
| Service injection in custom Drush commands | 2 | DrushCommands with `LoggerInterface` + `EntityTypeManagerInterface` via constructor promotion |

### Tier 1 — drupal-core (+5 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| Preprocess hook complete bodies (Q01) | 3 | `hook_preprocess_node()` with full body — variable assignment, conditional, attached library; not just signature |
| `accessCheck()` on entity queries (Q13) | 2 | Drupal 11 entity queries require explicit `accessCheck(TRUE\|FALSE)` since D9.2 |

### Tier 6 — php-drupal (+3 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| Multi-dependency DI (Q10) | 3 | `services.yml` with `LoggerInterface`, `EntityTypeManagerInterface`, `ConfigFactoryInterface` injected together via constructor promotion |

### Tier 13 — playwright-axe (+3 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| Full WCAG tag set (Q19) | 2 | `.withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'])` — explicit per-version tags |
| Tag set rationale | 1 | Explain that WCAG 2.2 tags are *additive*, not a superset — `wcag22aa` alone misses 2.1-introduced criteria |

### Tier 15 — wcag-general (+8 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| SC discrimination — div-as-button (Q23) | 3 | `<div onclick>` violates **both** 2.1.1 (Keyboard) and 4.1.2 (Name/Role/Value), not one |
| Contrast boundary examples (Q25) | 5 | Hex-pair pairs with computed ratios: `#767676` on white = 4.48:1 (fails), `#757575` = 4.51:1 (passes), `#747474` = 4.59:1 (passes), `#787878` = 4.41:1 (fails), `#000000` = 21:1 (passes AAA). Each entry shows the boundary and the math. |

### Tier 16 — wcag22-new (+15 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| SC 2.5.8 exceptions (Q28) | 5 | One entry per exception: **Spacing** (offset), **Equivalent** (24×24 control elsewhere), **Inline** (link in body text), **User-agent-controlled** (native form widgets), **Essential** (drawing/CAD tools) |
| SC 3.3.7 exceptions (Q29) | 5 | Essential re-entry (password confirm), security requirement, no-longer-valid info, user changes context, equivalent autocomplete available |
| SC 3.3.8 exceptions deep coverage | 5 | Object recognition, alternative provided, no cognitive test, copy/paste/autofill allowed, biometric/possession factor |

### Tier 17 — negative-example (+10 entries)

| Sub-topic | Entries | Pattern |
|---|---|---|
| Preprocess hook no-body hallucination (Q01) | 3 | Negative pair: "function signature with repeated `use` imports but no implementation body" → identify the hallucination, show complete correct body |
| Wrong widget nesting depth (Q07) | 3 | Negative pair: `$form['field_image']['#element_validate']` (wrong) vs `$form['field_image']['widget'][0]['#element_validate']` (correct) — explain the widget array structure |
| Incomplete withTags scope (Q19) | 2 | Negative pair: `.withTags(['wcag2aa'])` alone misses 2.1 and 2.2 criteria; correct is full additive set |
| Fabricated Drush flags (Q12) | 2 | Negative pair: invented flags like `--exclude` or `--target` on commands where they don't exist |

---

## Part 2 — New tier 19: agent-usage

**Domain:** `agent-usage`
**Label:** Using and extending a11y-public-agent
**Target entries:** 50
**Demo-friendly ratio:** 0.5 (mixed audience — end users + developers)

The companion product `a11y-public-agent` is shipping alongside v0.9.x. Users will ask the coder model how to use the agent, how it works, how to extend it. v0.9.0 had no training data on this — the model can only describe agents in generic terms. v0.9.5 fixes that.

### Sub-topic distribution

| Sub-topic | Entries | Audience | Examples |
|---|---|---|---|
| Agent invocation patterns | 8 | End-user | "How do I audit my Drupal site?" → CLI usage with `--path`, `--task`, `--model` flags |
| Tool descriptions | 7 | End-user | "What tools does the agent have?" → list of `read_file`, `list_files`, `grep`, `wcag_lookup`, `finish` with use cases |
| Common audit workflows | 8 | End-user | "Find all images missing alt attributes" → expected agent workflow: `list_files` for templates → `grep` for `<img\\s` without `alt=` → report |
| Local vs Ollama cloud selection | 4 | End-user | "When should I use `qwen3-coder:480b-cloud` vs the local 14B?" — cost, latency, privacy, accuracy tradeoffs |
| Read-only safety boundaries | 4 | End-user | "Can the agent modify my files?" → v0.1 is strictly read-only; explain the design choice |
| Reading agent transcripts | 3 | Developer | `state/session-*.jsonl` format, `--replay` flag, debugging via `--verbose` |
| Extending the agent with new tools | 8 | Developer | `@tool` decorator pattern, JSON schema requirements, function signature, project_root injection |
| ReAct loop concept | 4 | Developer | Model → tool_calls → execute → results → model → ... — the four-step cycle |
| Agent + WCAG combined queries | 4 | Mixed | "Use the agent to check SC 2.5.8 compliance on my Drupal site" — workflow that combines agent capabilities with WCAG knowledge |

### Example entries (format guidance for the teacher model)

```json
{
  "tier": 19,
  "domain": "agent-usage",
  "user": "How do I run a11y-public-agent to audit a Drupal site?",
  "assistant": "Use the CLI with `--path` pointing at your Drupal project root:\n\n```bash\npython agent.py --path ~/sites/gov-example-org \\\n  --task \"Audit the project for WCAG 2.2 AA accessibility issues\" \\\n  --verbose\n```\n\nThe agent uses `a11y-public-coder:14b` by default (set via Ollama). The `--verbose` flag shows each tool call and its result, which is useful for understanding the agent's reasoning. The transcript is saved to `state/session-<timestamp>.jsonl` for replay.\n\nFor harder reasoning, use an Ollama cloud model:\n```bash\nexport OLLAMA_API_KEY=...\npython agent.py --path ~/sites/gov-example-org \\\n  --model qwen3-coder:480b-cloud \\\n  --task \"Find all Twig templates with images missing alt attributes\"\n```",
  "wcag_sc": [],
  "demo_friendly": true,
  "contamination_target": null
}
```

```json
{
  "tier": 19,
  "domain": "agent-usage",
  "user": "How do I add a new tool to a11y-public-agent?",
  "assistant": "Tools are Python functions registered via the `@tool` decorator. Add a new tool by:\n\n1. **Define the function** in the tools section of `agent.py`:\n\n```python\n@tool(\n    name=\"playwright_audit\",\n    description=\"Run an accessibility audit on a URL using Playwright + axe-core.\",\n    parameters={\n        \"type\": \"object\",\n        \"properties\": {\n            \"url\": {\"type\": \"string\", \"description\": \"URL to audit\"},\n            \"engine\": {\"type\": \"string\", \"enum\": [\"axe\", \"alfa\", \"both\"]}\n        },\n        \"required\": [\"url\"]\n    }\n)\ndef playwright_audit(url: str, engine: str = \"axe\") -> str:\n    # implementation — return a string the model can read\n    return audit_results_as_text\n```\n\n2. **Update the loop runner** if the tool needs project_root injected (file-touching tools do — pure functions don't).\n\n3. **No restart of the model needed** — the new tool schema is sent to the model on the next request.\n\nThe model sees only the `name`, `description`, and `parameters` JSON schema. The Python function is invoked by the loop runner when the model emits a `tool_calls` entry with the matching name.",
  "wcag_sc": [],
  "demo_friendly": false,
  "contamination_target": null
}
```

### Source materials for tier 19 generation

The teacher model needs the actual `agent.py` source as context. Add to `TIERS[19]["sources"]`:

```python
"sources": [
    "file://agent.py",  # local file inclusion — pipeline needs to read this
    "https://github.com/rockypod/a11y-public-agent/blob/main/README.md",
    "https://github.com/rockypod/a11y-public-agent/blob/main/docs/extending.md",
    "https://ollama.com/docs/cloud",
],
```

**Note:** the RAFT pipeline currently fetches URLs only. To support `file://` local sources for tier 19, add a small case in `fetch_url()`:

```python
def fetch_url(url: str, client: httpx.Client) -> str:
    if url.startswith("file://"):
        path = Path(url[7:])
        if path.exists():
            return f"[Source: {url}]\n\n{path.read_text(encoding='utf-8')}"
        return ""
    # ... existing logic
```

---

## Part 3 — raft_pipeline.py patch

Add to the `TIERS` dictionary:

```python
19: {
    "domain": "agent-usage",
    "label": "Using and extending a11y-public-agent",
    "target": 50,
    "demo_ratio": 0.5,
    "sources": [
        "file://agent.py",
        "https://github.com/rockypod/a11y-public-agent",
        "https://ollama.com/blog/cloud",
    ],
    "instruction": (
        "Generate training pairs about a11y-public-agent — a read-only accessibility audit "
        "agent built on a11y-public-coder.\n"
        "Coverage:\n"
        "- CLI usage: --path, --task, --model, --verbose, --replay flags\n"
        "- Tool descriptions: read_file, list_files, grep, wcag_lookup, finish\n"
        "- Common audit workflows: find images missing alt, find low-contrast risks, "
        "find form fields without labels\n"
        "- Local model (a11y-public-coder:14b) vs Ollama cloud model selection\n"
        "- Read-only safety: agent cannot modify files in v0.1\n"
        "- Transcript format: state/session-*.jsonl, --replay flag\n"
        "- Extending with new tools: @tool decorator, JSON schema, project_root injection\n"
        "- ReAct loop concept: model → tool_calls → results → model\n"
        "Strict:\n"
        "- All CLI examples use 'python agent.py' (not 'agent' or 'a11y-public-agent' as bare command)\n"
        "- All --path values are placeholder paths: ~/sites/gov-example-org, /tmp/audit-target\n"
        "- Model names: a11y-public-coder:14b for default local, qwen3-coder:480b-cloud for cloud\n"
        "- Never invent tool names that don't exist in the agent source"
    ),
},
```

Update existing tiers' target counts for the v0.9.5 additions. The pipeline already supports running specific tier numbers via `--tier`, so additions can be generated incrementally:

```bash
# Generate the new tier 19 from scratch
python raft_pipeline.py --tier 19 --backend mlx --review

# Generate just the additional entries for existing tiers
# (target count increase triggers resume behavior to fill the gap)
python raft_pipeline.py --tier 7  --backend ollama --resume --review
python raft_pipeline.py --tier 8  --backend ollama --resume --review
python raft_pipeline.py --tier 1  --backend ollama --resume --review
python raft_pipeline.py --tier 6  --backend ollama --resume --review
python raft_pipeline.py --tier 13 --backend ollama --resume --review
python raft_pipeline.py --tier 15 --backend ollama --resume --review
python raft_pipeline.py --tier 16 --backend mlx    --resume --review  # 80B for SC nuance
python raft_pipeline.py --tier 17 --backend mlx    --resume --review  # 80B for negative pairs
```

For the updated targets, change each tier's `target` field:

| Tier | v0.9.0 target | v0.9.5 target | Delta |
|---|---|---|---|
| 1 | 100 | 105 | +5 |
| 6 | 100 | 103 | +3 |
| 7 | 100 | 115 | +15 |
| 8 | 100 | 105 | +5 |
| 13 | 140 | 143 | +3 |
| 15 | 80 | 88 | +8 |
| 16 | 140 | 155 | +15 |
| 17 | 140 | 150 | +10 |
| 19 | — | 50 | **new** |
| **Total** | **1,930** | **2,044** | **+114** |

---

## Part 4 — CRAFTED℠ review burden estimate

| Tier | New entries | Expected accept rate | Review minutes (manual portion) |
|---|---|---|---|
| 7, 8 (Drush) | 20 | 80% — flag fabrication risk | 25 |
| 1 (Drupal core) | 5 | 90% | 5 |
| 6 (PHP) | 3 | 95% | 3 |
| 13 (Playwright + axe) | 3 | 90% | 3 |
| 15 (WCAG general) | 8 | 85% — contrast math accuracy | 12 |
| 16 (WCAG 2.2-new) | 15 | 80% — exception coverage nuance | 25 |
| 17 (negative-example) | 10 | 75% — must verify correction matches reality | 20 |
| **19 (agent-usage) — new** | 50 | 60% — invented tool names risk; CLI flag accuracy | 80 |
| **Total** | **114** | — | **~3 hours** |

Tier 19 has the highest expected reject rate because the teacher will be tempted to invent plausible-sounding tool names that don't exist in `agent.py`. The filter to add: any `tool` name mentioned in tier 19 entries must match a name registered in `agent.py`'s `TOOLS` dict.

---

## Part 5 — Order of operations when GPU is free

1. **Apply raft_pipeline.py patch** (TIERS dict updates, `file://` source support)
2. **Run targeted-tier generations** (sequence above)
3. **Run new tier 19 generation** with strict tool-name validation filter
4. **CRAFTED℠ review** (~3 hours interactive on rockymac in second terminal)
5. **Run validate_drupal_tiers.py** on all corrected tiers (catch any D7 leakage in new entries)
6. **Train v0.9.5 4B and 14B** using existing `train.py` (no changes needed — dataset path is the same)
7. **30Q exam** — same exam, expect ≥80% on 14B at minimum for ship gate
8. **Update MODEL_CARD.md** with v0.9.5 numbers, ship

Estimated total elapsed time: 2 days generation + review + training (4B + 14B sequential on rockypod).

---

## Part 6 — Notes deliberately deferred

Things mentioned in v0.9.0 limitations that are *not* in v0.9.5 scope:

- **Dataset expansion to 3,000–4,000 entries** — that's v1.0 territory, requires new tier creation (Drupal frontend libraries, JavaScript a11y, more Twig depth)
- **Expanded 60-question exam** — v1.0
- **Playwright execution tool in agent** — that's `a11y-public-agent v0.2`, not coder dataset scope
- **Apply-patch agent tool** — `a11y-public-agent v0.2`, gated behind explicit safety design

v0.9.5 is intentionally narrow: fix what the exam flagged, add the missing agent-usage coverage. Big-picture restructure waits for v1.0.
