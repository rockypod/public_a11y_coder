# a11y-public-coder

Open-source **accessibility coding assistant for the public sector**.
WCAG 2.2 Level AA · Drupal 11 · PHP 8.3 · Drush 12 · Python 3.12 · Playwright (TypeScript) with axe-core and Siteimprove Alfa.

Trained under privacy-first constraints — no PII, no real agency URLs, no scraped production content.
Designed for self-hosted use by government agencies and public-sector developers.
Full dataset and exam rubric are public.

## Quickstart

```bash
# 14B — recommended default
ollama run rockypod/public-a11y-coder

# 4B — portable demo, runs in 8 GB RAM
ollama run rockypod/public-a11y-coder:4b
```

## Sizes

| Tag | Params | Disk | When to pick |
|---|---|---|---|
| `:latest` / `:14b` | 14B | ~9 GB | **Recommended.** OpenWebUI deployment, daily technical work. |
| `:4b` | 4B | ~2.5 GB | Portable demo, Windows 11 VM with 8 GB, explanation-first responses. |

## Exam results (30-question WCAG/Drupal/Playwright eval)

Each question scored Full (1.0) / Partial (0.5) / Fail (0.0). Rubric is public.

| Model | Score | vs baseline |
|---|---|---|
| qwen3:4b (baseline) | 13.5/30 (45.0%) | — |
| **a11y-public-coder:4b (trained)** | **22.0/30 (73.3%)** | **+8.5 (+28.3%)** |
| a11y-public-coder:14b (trained) | TBD | TBD |

Strong domains: Python 3.12 (100%), Drupal 11 (75%), Playwright + Alfa (75%).

## Privacy and self-hosting

All examples use `example.gov` / `gov.example.org` placeholder URLs.
No real agency names, no PII, no scraped production content.
Self-host via Ollama so prompts never leave your network.

## Links

- Full model card, weights, and GGUF downloads: https://huggingface.co/rockypod/a11y-public-coder
- Exam, dataset, and training pipeline: https://github.com/rockypod/public_a11y_coder
- Dataset on HuggingFace: https://huggingface.co/datasets/rockypod/a11y-public-coder-dataset
