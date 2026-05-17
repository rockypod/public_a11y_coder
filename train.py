#!/usr/bin/env python3
"""
a11y-public-coder — training pipeline
4B path: Qwen3-4B base, demo-weighted dataset
14B path: Qwen3-Coder-14B base, full dataset

Stages: consolidate → train (Unsloth LoRA SFT) → merge → GGUF (f16) → Modelfile

Usage:
    # Full pipeline for the 4B
    python train.py --size 4b

    # Full pipeline for the 14B
    python train.py --size 14b

    # Just consolidate + reweight (no training)
    python train.py --size 4b --consolidate-only

    # Just GGUF conversion + Modelfile (after a manual training run)
    python train.py --size 4b --gguf-only

    # Resume from checkpoint
    python train.py --size 14b --resume

Outputs:
    training/consolidated/train_<size>.jsonl    — formatted training data
    training/checkpoints/<size>/                — Unsloth checkpoints during training
    training/merged/<size>/                     — merged 16-bit HF model
    training/gguf/a11y-public-coder-<size>-f16.gguf
    training/modelfiles/Modelfile.<size>         — Ollama Modelfile

Privacy-first model card snippets are written alongside the merged model.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

# ─── Configuration ────────────────────────────────────────────────────────────

CORRECTED_DIR    = Path("corrected")
TRAINING_DIR     = Path("training")
CONSOLIDATED_DIR = TRAINING_DIR / "consolidated"
CHECKPOINTS_DIR  = TRAINING_DIR / "checkpoints"
MERGED_DIR       = TRAINING_DIR / "merged"
GGUF_DIR         = TRAINING_DIR / "gguf"
MODELFILES_DIR   = TRAINING_DIR / "modelfiles"

# Pinned llama.cpp commit per project standard
LLAMA_CPP_PATH   = Path(os.environ.get("LLAMA_CPP_PATH", "../llama.cpp"))
LLAMA_CPP_COMMIT = "57819b8d4"

# Reweighting thresholds for 4B
DEMO_WEIGHT      = 1.5
LONG_THRESHOLD   = 1800   # chars in `assistant` field
LONG_WEIGHT      = 0.7

RANDOM_SEED      = 42

# ─── Per-size config ──────────────────────────────────────────────────────────

SIZE_CONFIG: dict[str, dict[str, Any]] = {
    "4b": {
        "base_model":  "Qwen/Qwen3-4B",
        "max_seq":     4096,
        "load_4bit":   True,
        "per_device":  2,
        "grad_accum":  4,
        "epochs":      4,
        "lr":          2e-4,
        "reweight":    True,
    },
    "14b": {
        "base_model":  "Qwen/Qwen3-Coder-14B",
        "max_seq":     4096,
        "load_4bit":   True,
        "per_device":  1,
        "grad_accum":  8,
        "epochs":      4,
        "lr":          2e-4,
        "reweight":    False,
    },
}

# LoRA hyperparams shared across sizes (matches SvelteCoder v1.5 settings)
LORA_R         = 16
LORA_ALPHA     = 16
LORA_DROPOUT   = 0.0
LORA_TARGETS   = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]

# ─── ChatML template (matches Modelfile output for serving consistency) ──────

CHATML_TEMPLATE = (
    "<|im_start|>system\n{system}<|im_end|>\n"
    "<|im_start|>user\n{user}<|im_end|>\n"
    "<|im_start|>assistant\n{assistant}<|im_end|>"
)

DEFAULT_SYSTEM = (
    "You are a11y-public-coder, an accessibility-focused coding assistant for "
    "Drupal 11, PHP 8.3, Drush 12, Python 3.12, and Playwright with axe-core "
    "and Siteimprove Alfa. You write code that meets WCAG 2.2 Level AA. "
    "You cite WCAG success criteria by number when relevant. "
    "You explain accessibility in plain language when the audience is non-technical."
)

# ─── Modelfile template (Ollama serving) ─────────────────────────────────────

MODELFILE_TEMPLATE = """\
# a11y-public-coder {size} — Ollama Modelfile
# WCAG 2.2 AA accessibility coder for Drupal 11 / PHP 8.3 / Drush 12 / Python 3.12 / Playwright
# Privacy-first training: no PII, no real agency URLs, no scraped production content.
# License: MIT.  Self-hosted recommended; agency security/privacy is the operator's responsibility.

FROM ./a11y-public-coder-{size}-f16.gguf

TEMPLATE \"\"\"<|im_start|>system
{{{{ if .System }}}}{{{{ .System }}}}{{{{ else }}}}{system}{{{{ end }}}}<|im_end|>
<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
<|im_start|>assistant
\"\"\"

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.05

SYSTEM \"\"\"{system}\"\"\"
"""

# ─── Stage 1: Consolidate + reweight ─────────────────────────────────────────

def load_all_corrected() -> list[dict]:
    """Read every corrected/tier*.jsonl file into a single list."""
    entries: list[dict] = []
    files = sorted(CORRECTED_DIR.glob("tier*.jsonl"))
    if not files:
        sys.exit(f"No corrected/tier*.jsonl files found in {CORRECTED_DIR.absolute()}")
    for path in files:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def reweight_for_4b(entries: list[dict], rng: random.Random) -> list[dict]:
    """
    Apply 4B-specific reweighting:
    - demo_friendly entries: 1.5× (oversample)
    - assistant length > 1800 chars: 0.7× (downsample long code-dense entries)
    Both can stack — a long demo entry weights to 1.5 × 0.7 = 1.05.
    """
    out: list[dict] = []
    for entry in entries:
        weight = 1.0
        if entry.get("demo_friendly"):
            weight *= DEMO_WEIGHT
        if len(entry.get("assistant", "")) > LONG_THRESHOLD:
            weight *= LONG_WEIGHT

        full = int(weight)
        frac = weight - full
        for _ in range(full):
            out.append(entry)
        if rng.random() < frac:
            out.append(entry)
    return out


def format_chatml(entry: dict, system: str = DEFAULT_SYSTEM) -> dict:
    """Convert a dataset entry into a ChatML-formatted text record for SFT."""
    text = CHATML_TEMPLATE.format(
        system=system,
        user=entry["user"],
        assistant=entry["assistant"],
    )
    return {"text": text}


def consolidate(size: str) -> Path:
    """Write training/consolidated/train_<size>.jsonl with formatted ChatML entries."""
    cfg = SIZE_CONFIG[size]
    rng = random.Random(RANDOM_SEED)

    print(f"\n{'='*70}\nConsolidating dataset for {size.upper()}\n{'='*70}")

    entries = load_all_corrected()
    print(f"  Loaded {len(entries):,} corrected entries from {CORRECTED_DIR}/")

    if cfg["reweight"]:
        before = len(entries)
        entries = reweight_for_4b(entries, rng)
        demo_frac = sum(1 for e in entries if e.get("demo_friendly")) / len(entries)
        print(f"  Reweighted for 4B: {before:,} → {len(entries):,} entries")
        print(f"  demo_friendly fraction in training set: {demo_frac:.1%}")

    rng.shuffle(entries)

    CONSOLIDATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CONSOLIDATED_DIR / f"train_{size}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(format_chatml(entry), ensure_ascii=False) + "\n")

    print(f"  Wrote {len(entries):,} formatted records → {out_path}")
    return out_path


# ─── Stage 2: Train (Unsloth LoRA SFT) ────────────────────────────────────────

def train(size: str, train_path: Path, resume: bool) -> Path:
    """Run Unsloth LoRA SFT. Returns the path to the merged 16-bit model."""
    # Imports here — Unsloth has side effects on import (CUDA init), so defer
    print(f"\n{'='*70}\nTraining {size.upper()}\n{'='*70}")
    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import load_dataset
        import torch
    except ImportError as exc:
        sys.exit(f"Missing dependency: {exc}\nInstall: pip install unsloth trl transformers datasets")

    cfg = SIZE_CONFIG[size]
    ckpt_dir   = CHECKPOINTS_DIR / size
    merged_dir = MERGED_DIR / size

    # Load base model
    print(f"  Loading base: {cfg['base_model']}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name      = cfg["base_model"],
        max_seq_length  = cfg["max_seq"],
        dtype           = None,                 # auto bf16/fp16
        load_in_4bit    = cfg["load_4bit"],
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r                          = LORA_R,
        target_modules             = LORA_TARGETS,
        lora_alpha                 = LORA_ALPHA,
        lora_dropout               = LORA_DROPOUT,
        bias                       = "none",
        use_gradient_checkpointing = "unsloth",
        random_state               = RANDOM_SEED,
        use_rslora                 = False,
        loftq_config               = None,
    )

    # Load formatted dataset
    print(f"  Loading training data: {train_path}")
    dataset = load_dataset("json", data_files=str(train_path), split="train")
    print(f"  Dataset records: {len(dataset):,}")

    bf16 = torch.cuda.is_bf16_supported()
    args = TrainingArguments(
        per_device_train_batch_size = cfg["per_device"],
        gradient_accumulation_steps = cfg["grad_accum"],
        warmup_steps                = 10,
        num_train_epochs            = cfg["epochs"],
        learning_rate               = cfg["lr"],
        fp16                        = not bf16,
        bf16                        = bf16,
        logging_steps               = 10,
        optim                       = "adamw_8bit",
        weight_decay                = 0.01,
        lr_scheduler_type           = "cosine",
        seed                        = RANDOM_SEED,
        output_dir                  = str(ckpt_dir),
        save_strategy               = "epoch",
        save_total_limit            = 2,
        report_to                   = "none",
    )

    trainer = SFTTrainer(
        model            = model,
        tokenizer        = tokenizer,
        train_dataset    = dataset,
        dataset_text_field = "text",
        max_seq_length   = cfg["max_seq"],
        packing          = False,
        args             = args,
    )

    print(f"  Starting training: {cfg['epochs']} epochs, "
          f"effective batch {cfg['per_device'] * cfg['grad_accum']}, "
          f"lr {cfg['lr']}")

    if resume and any(ckpt_dir.glob("checkpoint-*")):
        print(f"  Resuming from latest checkpoint in {ckpt_dir}")
        trainer.train(resume_from_checkpoint=True)
    else:
        trainer.train()

    # Merge LoRA into base, save 16-bit
    print(f"  Merging adapter and saving 16-bit model → {merged_dir}")
    merged_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained_merged(
        str(merged_dir),
        tokenizer,
        save_method = "merged_16bit",
    )

    print(f"  Training complete. Merged model: {merged_dir}")
    return merged_dir


# ─── Stage 3: GGUF conversion (pinned llama.cpp) ─────────────────────────────

def convert_to_gguf(size: str, merged_path: Path) -> Path:
    """Convert merged HF model to GGUF f16 using pinned llama.cpp commit."""
    print(f"\n{'='*70}\nGGUF conversion ({size.upper()}, --outtype f16)\n{'='*70}")

    GGUF_DIR.mkdir(parents=True, exist_ok=True)
    gguf_out = GGUF_DIR / f"a11y-public-coder-{size}-f16.gguf"

    if not LLAMA_CPP_PATH.exists():
        sys.exit(f"llama.cpp not found at {LLAMA_CPP_PATH}\n"
                 f"Set LLAMA_CPP_PATH env var or symlink to your pinned checkout (commit {LLAMA_CPP_COMMIT})")

    # Verify commit (warn only — don't block)
    try:
        head = subprocess.check_output(
            ["git", "-C", str(LLAMA_CPP_PATH), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if not LLAMA_CPP_COMMIT.startswith(head) and not head.startswith(LLAMA_CPP_COMMIT):
            print(f"  WARN: llama.cpp at commit {head}, expected {LLAMA_CPP_COMMIT}")
    except subprocess.CalledProcessError:
        print("  WARN: could not verify llama.cpp commit")

    convert_script = LLAMA_CPP_PATH / "convert_hf_to_gguf.py"
    if not convert_script.exists():
        sys.exit(f"Conversion script not found: {convert_script}")

    cmd = [
        sys.executable, str(convert_script),
        str(merged_path),
        "--outtype", "f16",
        "--outfile", str(gguf_out),
    ]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    print(f"  GGUF written: {gguf_out}  ({gguf_out.stat().st_size / 1e9:.2f} GB)")
    return gguf_out


# ─── Stage 4: Modelfile generation ───────────────────────────────────────────

def write_modelfile(size: str, gguf_path: Path) -> Path:
    """Write Ollama Modelfile with ChatML template override."""
    MODELFILES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODELFILES_DIR / f"Modelfile.{size}"

    content = MODELFILE_TEMPLATE.format(size=size, system=DEFAULT_SYSTEM)
    out_path.write_text(content, encoding="utf-8")

    print(f"\n{'='*70}\nModelfile written: {out_path}\n{'='*70}")
    print(f"  Register with Ollama:")
    print(f"    cd {gguf_path.parent}")
    print(f"    ollama create a11y-public-coder:{size} -f ../modelfiles/Modelfile.{size}")
    return out_path


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--size", choices=["4b", "14b"], required=True, help="Model size")
    p.add_argument("--consolidate-only", action="store_true", help="Stop after dataset consolidation")
    p.add_argument("--train-only",       action="store_true", help="Train (and merge) but skip GGUF/Modelfile")
    p.add_argument("--gguf-only",        action="store_true", help="Run GGUF + Modelfile only (assumes merged model exists)")
    p.add_argument("--resume",           action="store_true", help="Resume from latest checkpoint")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    size = args.size
    cfg  = SIZE_CONFIG[size]

    print(f"a11y-public-coder training pipeline")
    print(f"Size: {size}  |  Base: {cfg['base_model']}")
    print(f"Reweight: {cfg['reweight']}  |  Epochs: {cfg['epochs']}  |  LR: {cfg['lr']}")

    # ── GGUF-only shortcut ────────────────────────────────────────────────────
    if args.gguf_only:
        merged = MERGED_DIR / size
        if not merged.exists():
            sys.exit(f"Merged model not found at {merged}. Run training first.")
        gguf = convert_to_gguf(size, merged)
        write_modelfile(size, gguf)
        print("\nDone (gguf-only).")
        return

    # ── Stage 1: consolidate ──────────────────────────────────────────────────
    train_path = consolidate(size)
    if args.consolidate_only:
        print("\nDone (consolidate-only).")
        return

    # ── Stage 2: train ────────────────────────────────────────────────────────
    merged = train(size, train_path, resume=args.resume)
    if args.train_only:
        print("\nDone (train-only). Run --gguf-only to produce GGUF.")
        return

    # ── Stage 3: GGUF conversion ──────────────────────────────────────────────
    gguf = convert_to_gguf(size, merged)

    # ── Stage 4: Modelfile ────────────────────────────────────────────────────
    write_modelfile(size, gguf)

    print(f"\n{'='*70}")
    print(f"Pipeline complete for {size.upper()}.")
    print(f"  Merged HF:  {merged}")
    print(f"  GGUF:       {gguf}")
    print(f"  Modelfile:  {MODELFILES_DIR / f'Modelfile.{size}'}")
    print(f"\nNext steps:")
    print(f"  1. scp the GGUF to rockymac for the 30Q exam run")
    print(f"  2. Register with Ollama on rockypod:")
    print(f"       ollama create a11y-public-coder:{size} -f training/modelfiles/Modelfile.{size}")
    print(f"  3. Compare exam scores against the baseline run")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
