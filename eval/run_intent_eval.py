"""
Intent-classification eval for the debtor-reply NLP pipeline.

Scores two classifiers on eval/intent_testset.jsonl (80 hand-labelled
Hindi / Hinglish / English replies, 20 per intent):
  1. the Gemini pipeline (translate -> classify), via process_debtor_reply
  2. the keyword fallback alone, via _heuristic_classify on the raw text

Run from the project root:  python -m eval.run_intent_eval
"""
import asyncio
import json
import logging
import time
from collections import Counter
from pathlib import Path

from app.services import nlp_service

logging.disable(logging.CRITICAL)

LABELS = ["promise_to_pay", "dispute", "stall", "unknown"]
DATA = Path(__file__).with_name("intent_testset.jsonl")
OUT = Path(__file__).with_name("intent_eval_results.json")
DELAY_S = 4.0  # stay under the free-tier requests-per-minute limit


def report(name, gold, pred):
    n = len(gold)
    acc = sum(g == p for g, p in zip(gold, pred)) / n
    lines = [f"\n{name}: accuracy {acc:.1%} ({sum(g == p for g, p in zip(gold, pred))}/{n})"]
    f1s = []
    for lab in LABELS:
        tp = sum(g == lab and p == lab for g, p in zip(gold, pred))
        fp = sum(g != lab and p == lab for g, p in zip(gold, pred))
        fn = sum(g == lab and p != lab for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        lines.append(f"  {lab:15s} P {prec:.2f}  R {rec:.2f}  F1 {f1:.2f}")
    macro = sum(f1s) / len(f1s)
    lines.append(f"  macro-F1 {macro:.3f}")
    print("\n".join(lines))
    return {"accuracy": acc, "macro_f1": macro}


async def main():
    rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
    gold = [r["label"] for r in rows]

    heur = [nlp_service._heuristic_classify(r["text"])["intent"] for r in rows]

    llm, fell_back, records = [], 0, []
    for i, r in enumerate(rows):
        out = await nlp_service.process_debtor_reply(r["text"])
        if out.get("fallback_mode"):
            fell_back += 1
        llm.append(out["intent"])
        records.append({**r, "gemini": out["intent"], "keyword": heur[i],
                        "fallback": out.get("fallback_mode")})
        print(f"[{i + 1:2d}/{len(rows)}] gold={r['label']:15s} gemini={out['intent']:15s} keyword={heur[i]}")
        time.sleep(DELAY_S)

    print(f"\nGemini calls that fell back to keywords: {fell_back}/{len(rows)}")
    summary = {
        "n": len(rows),
        "per_label": dict(Counter(gold)),
        "gemini_fallbacks": fell_back,
        "gemini_pipeline": report("Gemini pipeline (gemini-3.5-flash-lite)", gold, llm),
        "keyword_fallback": report("Keyword fallback", gold, heur),
        "records": records,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
