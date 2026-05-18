---
license: mit
language:
  - en
library_name: transformers
pipeline_tag: text-generation
tags:
  - accessibility
  - wcag
  - wcag-2.2
  - drupal
  - drupal-11
  - php
  - drush
  - python
  - playwright
  - axe-core
  - siteimprove-alfa
  - government
  - public-sector
  - code
base_model:
  - Qwen/Qwen3-4B
  - Qwen/Qwen3-14B
datasets:
  - rockypod/a11y-public-coder-dataset
model-index:
  - name: a11y-public-coder
    results:
      - task:
          type: text-generation
          name: WCAG 2.2 AA Accessibility Coding Exam
        metrics:
          - type: accuracy
            name: 30-question exam (4B)
            value: 73.3
          - type: accuracy
            name: 30-question exam (14B)
            value: 76.7
---

# a11y-public-coder

**Open-source accessibility coding assistant for the public sector.** WCAG 2.2 Level AA conformance, Drupal 11, PHP 8.3, Drush 12, Python 3.12, and Playwright (TypeScript) with both axe-core and Siteimprove Alfa.

> Version **0.9.0** · License **MIT** · Released 2026-05-17

**[HuggingFace — weights](https://huggingface.co/rockypod/a11y-public-coder-4b)** ·
**[Install via Ollama](https://ollama.com/rockypod/public-a11y-coder)** — `ollama pull rockypod/public-a11y-coder` ·
**[GitHub — exam, dataset, training pipeline](https://github.com/rockypod/public_a11y_coder)**

## Quick reference

| | 4B | 14B |
|---|---|---|
| **Base model** | `Qwen/Qwen3-4B` | `Qwen/Qwen3-14B` |
| **Quantization** | Q4_K_M GGUF (~2.5 GB) | Q4_K_M GGUF (~9 GB) |
| **Recommended use** | Demo, non-technical explanation, portable inference | Daily-driver technical work, OpenWebUI deployment |
| **Exam score** | **73.3%** (22.0/30) | **76.7%** (23.0/30) |
| **Lift vs base** | **+28.3%** (from 45.0% baseline) | **+23.4%** (from 53.3% baseline) |
| **Ollama tag** | `rockypod/public-a11y-coder:4b` | `rockypod/public-a11y-coder:14b` |

## What's in this repo

| Path | Description |
|---|---|
| `exam/a11y-30q.md` | Full 30-question evaluation exam with rubric |
| `exam/run_exam.py` | Exam runner — collects responses and scores |
| `exam/baselines/` | Pre-training baseline grades (qwen3:4b, 8b, 14b) |
| `exam/trained/` | Post-training grades per model size |
| `dataset/tier*.jsonl` | Full training corpus — 1,930 pairs across 18 tiers |
| `train.py` | Full training pipeline (consolidate → LoRA → merge → GGUF) |
| `Modelfile` | Ollama Modelfile (4B production ChatML template) |

Large artifacts (checkpoints, merged HF weights, GGUF) are not in this repo — download GGUFs from the HuggingFace model page or pull via Ollama.

## Intended use

`a11y-public-coder` is designed for use by government agencies, public-sector developers, accessibility professionals, and any developer maintaining Drupal 11 sites that must meet WCAG 2.2 Level AA. The model produces:

- Drupal 11 module, theme, and Twig code that follows accessibility best practices
- Drush 12 CLI commands and custom command authoring
- Python 3.12 utility scripts for accessibility-aware file operations (PDF text layer detection, alt audit, heading hierarchy)
- Playwright (TypeScript) test scaffolds using `@axe-core/playwright` and `@siteimprove/alfa-playwright`
- WCAG 2.2 AA explanations cited by success criterion number, suitable for both developers and non-technical content editors

The 4B variant is optimized for portable demonstrations (runs comfortably in a Windows 11 VM with 8 GB allocation) and explanation-first responses. The 14B variant is the primary daily-driver, targeted at OpenWebUI deployment on agency or homelab hardware.

## Privacy-first training

This model was trained under explicit privacy constraints documented in the dataset card and verifiable in the public training corpus:

- **No PII** in any training entry — no real names, addresses, emails, phone numbers, case numbers, or social security numbers
- **No real URLs, hostnames, or production domain names** — all examples use `example.gov`, `gov.example.org`, or `agency.example` placeholders
- **No scraped production agency content** — every training example was authored from publicly available official documentation: drupal.org, php.net, docs.python.org, playwright.dev, alfa.siteimprove.com, w3.org/WAI/WCAG22/, drush.org
- **Full dataset, exam questions, and per-question grading results are public** — see the [`a11y-public-coder-dataset`](https://huggingface.co/datasets/rockypod/a11y-public-coder-dataset) repository

The privacy-first training approach minimizes the risk of memorized PII surfacing in outputs, but does not eliminate standard LLM safety considerations.

## Security and compliance — agency responsibility

`a11y-public-coder` is designed for self-hosted deployment. Deploying organizations remain responsible for their own security and privacy posture:

- **Self-host**: run via Ollama, vLLM, llama.cpp, or similar so that no prompts leave your network
- **No certifications**: this model has not been independently certified against NIST 800-53, FedRAMP, CJIS, HIPAA, FERPA, or state-specific frameworks. Agencies must independently validate fitness for their compliance context
- **No sensitive data in prompts**: do not paste citizen PII, case numbers, or other sensitive content. The model is a code/audit assistant, not a data-handling system
- **Output review**: model output is a suggestion, not authoritative. Human review is required before deployment
- **Access controls and audit logging** are the operator's responsibility

## Training methodology

`a11y-public-coder` was trained using a **RAFT (Retrieval-Augmented Fine-Tuning) + CRAFTER (Continuous RAFT + Correction Stream)** pipeline:

1. **Source corpus assembly** — 1,930 training pairs generated from official documentation (drupal.org, drush.org, playwright.dev, alfa.siteimprove.com, w3.org/WAI/WCAG22/, php.net, docs.python.org) by a local teacher model (`qwen3:30b` via Ollama)

2. **CRAFTER correction stream** — Every generated entry was reviewed against domain-specific failure-mode filters (e.g. the WCAG 2.5.8 = 24×24 vs 2.5.5 = 44×44 contamination check, the Drupal 7/8/9 → Drupal 11 API leakage check, the Python-vs-TypeScript Playwright fallback check). 1,925 of 1,930 entries passed auto-acceptance with rule-based filters; 5 were manually corrected; 2 additional issues were flagged by a Drupal-specific D7/D8 API validator and corrected. Final corrected entries: 1,930/1,930.

3. **Fine-tuning** — Unsloth + LoRA (r=16, alpha=16, no dropout) on NVIDIA RTX 3090 Ti, 4 epochs at learning rate 2e-4 with cosine schedule. The 4B run reweights `demo_friendly` entries by 1.5× and downsamples entries with `len(assistant) > 1800 chars` by 0.7× to favor explanation-leaning content; the 14B run uses the full distribution without reweighting.

4. **Conversion** — GGUF via pinned `llama.cpp` commit `57819b8d4` with `--outtype f16`, quantized to Q4_K_M for serving. Modelfile uses ChatML template override for tokenizer consistency.

The full pipeline is reproducible from the [training scripts](https://github.com/rockypod/public_a11y_coder) in this repository.

## Dataset

The training corpus is **1,930 high-quality instruction-response pairs across 18 tiers**, fully open and downloadable from the [dataset repository](https://huggingface.co/datasets/rockypod/a11y-public-coder-dataset) or from `dataset/` in this repo:

| Tier | Domain | Entries |
|---|---|---|
| 1 | Drupal 11 core fundamentals | 100 |
| 2 | Drupal 11 contrib stack (Webform, Paragraphs, Views, Pathauto, Metatag) | 100 |
| 3 | Drupal 11 Twig 3 templating | 100 |
| 4 | Drupal 11 custom modules | 100 |
| 5 | Drupal 11 accessibility patterns | 100 |
| 6 | Drupal-flavored PHP 8.3 | 100 |
| 7 | Drush 12 CLI usage | 100 |
| 8 | Drush 12 custom command authoring | 100 |
| 9 | Python 3.12 folder/file utilities | 100 |
| 10 | Python 3.12 file conversion | 100 |
| 11 | Python 3.12 accessibility-aware utilities | 100 |
| 12 | Playwright (TypeScript) fundamentals | 100 |
| 13 | Playwright + `@axe-core/playwright` | 140 |
| 14 | Playwright + `@siteimprove/alfa-playwright` | 130 |
| 15 | WCAG 2.2 AA — pre-2.2 carryover SCs | 80 |
| 16 | WCAG 2.2-new success criteria (9 new SCs) | 140 |
| 17 | Negative-example / contamination correction pairs | 140 |
| 18 | End-to-end multi-domain scenarios | 100 |
| **Total** | | **1,930** |

## Evaluation

Models are evaluated against a 30-question exam covering all training domains, scored **Full (1.0) / Partial (0.5) / Fail (0.0)** per question, max 30.0 points. The exam is **published in full**, including grading rubrics: see [`exam/a11y-30q.md`](exam/a11y-30q.md).

**Pre-training baselines and post-training results** are published in `exam/`, with per-question grades:

### Summary

| Model | Total | Percentage |
|---|---|---|
| `qwen3:4b` baseline | 13.5/30 | 45.0% |
| `qwen3:8b` baseline | 17.0/30 | 56.7% |
| `qwen3:14b` baseline | 16.0/30 | 53.3% |
| **`a11y-public-coder:4b` (trained)** | **22.0/30** | **73.3%** |
| **`a11y-public-coder:14b` (trained)** | **23.0/30** | **76.7%** |

### Per-domain results — 4B trained vs baseline `qwen3:4b`

| Domain | Baseline | Trained 4B | Lift |
|---|---|---|---|
| Drupal 11 | 2.0/8 (25%) | 6.0/8 (75%) | **+4.0** ⬆ |
| PHP 8.3 | 0.5/2 (25%) | 1.0/2 (50%) | +0.5 |
| Drush 12 | 2.0/3 (67%) | 1.5/3 (50%) | -0.5 ⬇ |
| Python 3.12 | 2.5/4 (63%) | 4.0/4 (100%) | **+1.5** ✓ |
| Playwright + axe-core | 0.5/3 (17%) | 2.0/3 (67%) | **+1.5** ⬆ |
| Playwright + Alfa | 0.5/2 (25%) | 1.5/2 (75%) | **+1.0** ⬆ |
| WCAG 2.2 AA (carryover) | 3.0/4 (75%) | 3.0/4 (75%) | 0 |
| WCAG 2.2-new ⭐ | 1.5/3 (50%) | 2.0/3 (67%) | +0.5 |
| Negative/contamination gate | 1.0/1 (100%) | 1.0/1 (100%) | 0 ✓ |
| **Total** | **13.5/30 (45.0%)** | **22.0/30 (73.3%)** | **+8.5 (+28.3%)** |

### Per-domain results — 14B trained vs baseline `qwen3:14b`

| Domain | Baseline | Trained 14B | Lift |
|---|---|---|---|
| Drupal 11 | 3.0/8 (37.5%) | 6.5/8 (81.3%) | **+3.5** ⬆ |
| PHP 8.3 | 1.5/2 (75.0%) | 1.5/2 (75.0%) | 0 |
| Drush 12 | 1.5/3 (50.0%) | 1.0/3 (33.3%) | -0.5 ⬇ |
| Python 3.12 | 2.5/4 (62.5%) | 3.5/4 (87.5%) | **+1.0** ⬆ |
| Playwright + axe-core | 1.0/3 (33.3%) | 2.5/3 (83.3%) | **+1.5** ⬆ |
| Playwright + Alfa | 1.0/2 (50.0%) | 2.0/2 (100%) | **+1.0** ✓ |
| WCAG 2.2 AA (carryover) | 3.0/4 (75.0%) | 3.0/4 (75.0%) | 0 |
| WCAG 2.2-new ⭐ | 1.5/3 (50.0%) | 2.0/3 (66.7%) | +0.5 |
| Negative/contamination gate | 1.0/1 (100%) | 1.0/1 (100%) | 0 ✓ |
| **Total** | **16.0/30 (53.3%)** | **23.0/30 (76.7%)** | **+7.0 (+23.4%)** |

## Running the exam yourself

```bash
# Against a trained model already loaded in Ollama
python exam/run_exam.py --model rockypod/public-a11y-coder:4b --output exam/trained/4b

# Score after filling grades.json
python exam/run_exam.py --score exam/trained/4b
```

Grading is manual (Full/Partial/Fail per rubric in `exam/a11y-30q.md`).

## Reproducing training

```bash
# On a CUDA GPU server with the Unsloth venv installed
nohup env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TORCHDYNAMO_DISABLE=1 \
  python train.py --size 4b > logs/train_4b.log 2>&1 &
```

`TORCHDYNAMO_DISABLE=1` is required — Qwen3 + Unsloth triggers Triton JIT compilation which fails on CUDA driver/toolkit version mismatches common on Rocky Linux GPU hosts.

## Usage

### Ollama (local)

```bash
ollama run rockypod/public-a11y-coder:14b
# or for the portable demo model:
ollama run rockypod/public-a11y-coder:4b
```

### OpenWebUI

Add the model under Settings → Models → Ollama, point to your Ollama endpoint (default `http://localhost:11434`), select `rockypod/public-a11y-coder:14b` from the model list.

### HuggingFace Transformers

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "rockypod/a11y-public-coder-4b"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="auto", device_map="auto")

messages = [
    {"role": "user", "content": "Write a Drupal 11 Twig snippet for an accessible image field with a skip-link-friendly heading structure."}
]
inputs = tokenizer.apply_chat_template(messages, return_tensors="pt").to(model.device)
outputs = model.generate(inputs, max_new_tokens=512)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

## Known limitations

The v0.9.0 release ships with documented gaps to be addressed in v1.0:

1. **Drush flag accuracy** — The 4B variant occasionally fabricates non-existent command flags (e.g. inventing `--target` or `--exclude` on commands where those flags do not exist). This is a training data quality issue traced to tier 7 generation; v1.0 will include a Drush command-reference validator before retraining.

2. **Contrast ratio computation** — Small models cannot reliably compute color contrast ratios from arbitrary hex pairs. The model correctly identifies SC 1.4.3 (Contrast — Minimum) and can recall specific examples that appear in training (`#767676` on white = 4.48:1), but does not generalize to compute ratios for novel inputs. Recommend pairing with a deterministic contrast checker.

3. **WCAG 2.2-new exception coverage** — SC 2.5.8 (Target Size — Minimum) has five distinct exception cases (offset, essential, inline, user-agent-controlled, equivalent). The 4B reliably outputs the headline `24×24 CSS pixels` AA threshold but covers only one of the five exception cases consistently. v1.0 will expand tier 16 with dedicated entries per exception type.

4. **SC-to-SC discrimination** — The 4B occasionally confuses related success criteria (e.g. cites SC 2.1.1 + 2.1.2 for a missing button role where 4.1.2 is the primary criterion). v1.0 will add SC-discrimination pair entries to tier 17.

5. **Drupal 11 vs Drupal 10 distinction** — While the dataset targets Drupal 11 exclusively, the underlying base model has substantial Drupal 7/8/9 pretraining priors. The contamination gate (tier 17 negative examples) holds at 100% on the exam, but in long-form generation some D7-era patterns may surface. Always validate generated Drupal code against the actual D11 API.

## Recommended use cases

**Strong fit:**
- Generating Drupal 11 module scaffolds with accessibility baked in
- Writing Playwright + axe-core / Alfa test files for agency sites
- Drafting Python utility scripts for accessibility audits (PDF text layer detection, alt text auditing, heading hierarchy)
- Explaining WCAG 2.2 success criteria to non-technical content editors
- Drush 12 natural-language to command translation (with verification)

**Use with caution:**
- Contrast ratio calculations (verify with a deterministic checker)
- Drush command flags (verify against `drush help <command>`)
- Drupal 8/9 maintenance (this model is Drupal 11-targeted)

**Not designed for:**
- General-purpose coding outside the trained domains
- Production-critical accessibility certification without human review
- Handling sensitive citizen data in prompts

## Roadmap

| Version | Target | Focus |
|---|---|---|
| **v0.9.0** | **shipped** | Initial release, baselines published, ship gate intentionally below 80% with documented limitations |
| v0.9.5 | ~6 weeks | Drush flag validation pass, contrast hex-pair expansion, SC 2.5.8 exception coverage |
| v1.0.0 | ~10 weeks | All v0.9.0 limitations addressed, ≥85% on the 30Q exam |

The CRAFTER methodology means each version uses real-world exam failures and user-reported issues as the correction stream for the next training cycle. The v1.0 release will include an expanded 60-question exam.

## Reproducibility

This release is reproducible end-to-end from the public artifacts:

- **Dataset:** [`rockypod/a11y-public-coder-dataset`](https://huggingface.co/datasets/rockypod/a11y-public-coder-dataset) or `dataset/` in this repo
- **Training pipeline:** [`train.py`](train.py) in this repo
- **Evaluation exam:** [`exam/a11y-30q.md`](exam/a11y-30q.md)
- **Exam runner:** [`exam/run_exam.py`](exam/run_exam.py)
- **Per-question grading results:** [`exam/baselines/`](exam/baselines/) and [`exam/trained/`](exam/trained/)

## Citation

```bibtex
@misc{a11y-public-coder-v0.9.0,
  author       = {RockyPod},
  title        = {a11y-public-coder: An open-source accessibility coding assistant for the public sector},
  year         = {2026},
  publisher    = {Hugging Face},
  howpublished = {\url{https://huggingface.co/rockypod/a11y-public-coder-4b}},
}
```

## Acknowledgments

- Base models: [Qwen team](https://github.com/QwenLM) — `Qwen3-4B` and `Qwen3-14B` are MIT-licensed open weights
- Accessibility tooling: [Deque axe-core](https://github.com/dequelabs/axe-core), [Siteimprove Alfa](https://github.com/Siteimprove/alfa)
- Web standards: [W3C WAI](https://www.w3.org/WAI/) for the WCAG 2.2 specification and Understanding documents
- Training infrastructure: [Unsloth](https://github.com/unslothai/unsloth), [llama.cpp](https://github.com/ggerganov/llama.cpp), [Ollama](https://ollama.com/)

## License

MIT. See [LICENSE](LICENSE) for full text. Free for any use including commercial, including by government agencies.
