"""Measure Gemini (and optionally Gemma) on a labelled flood-depth test set, e.g. STURM-FloodDepth.

Usage:
  python scripts/eval_sturm.py --images path/to/test_images --labels path/to/labels.csv [--limit 100] [--gemma]

labels.csv needs two columns: image,label   (label = 0-4 or L0-L4; the image file name inside --images)
Writes results/eval.json and prints macro-F1, accuracy, big misses (off by 2+ levels) and abstain rate.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, grader, imaging  # noqa: E402

LV = ["L0", "L1", "L2", "L3", "L4"]


def norm(label: str) -> str:
    label = label.strip().upper()
    return label if label.startswith("L") else f"L{int(float(label))}"


def metrics(pairs):
    """pairs: list of (true, pred) where pred may be 'cant_tell'."""
    answered = [(t, p) for t, p in pairs if p in LV]
    f1s = []
    for lv in LV:
        tp = sum(1 for t, p in answered if t == lv and p == lv)
        fp = sum(1 for t, p in answered if t != lv and p == lv)
        fn = sum(1 for t, p in pairs if t == lv and p != lv)  # abstain counts as a miss
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        if tp + fn:  # only classes present in the test set
            f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    big = sum(1 for t, p in answered if abs(LV.index(t) - LV.index(p)) >= 2)
    confusion = {t: {p: 0 for p in LV + ["cant_tell"]} for t in LV}
    for t, p in pairs:
        confusion[t][p if p in LV else "cant_tell"] += 1
    return {
        "n": len(pairs),
        "macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else 0.0,
        "accuracy": round(sum(1 for t, p in pairs if t == p) / len(pairs), 3) if pairs else 0.0,
        "big_misses": big,
        "abstain_rate": round(1 - len(answered) / len(pairs), 3) if pairs else 0.0,
        "confusion": confusion,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gemma", action="store_true", help="also evaluate the Gemma checker")
    ap.add_argument("--sleep", type=float, default=0.5, help="pause between calls (rate limits)")
    args = ap.parse_args()

    with open(args.labels, newline="", encoding="utf-8") as f:
        items = [(r["image"], norm(r["label"])) for r in csv.DictReader(f)]
    if args.limit:
        items = items[: args.limit]

    gem, gma, rows = [], [], []
    for i, (name, truth) in enumerate(items, 1):
        jpeg = imaging.clean_image((Path(args.images) / name).read_bytes())
        try:
            pred = grader.gemini_grade(jpeg, "").level
        except Exception as exc:
            print(f"[{i}] {name}: error {exc}")
            pred = "cant_tell"
        gem.append((truth, pred))
        g2 = None
        if args.gemma:
            g2 = grader.gemma_level(jpeg) or "cant_tell"
            gma.append((truth, g2))
        rows.append({"image": name, "truth": truth, "gemini": pred, "gemma": g2})
        print(f"[{i}/{len(items)}] {name}: truth={truth} gemini={pred}" + (f" gemma={g2}" if g2 else ""))
        time.sleep(args.sleep)

    out = {"model": config.GEMINI_MODEL, "gemini": metrics(gem), "rows": rows}
    if args.gemma:
        out["gemma_model"] = config.GEMMA_MODEL
        out["gemma"] = metrics(gma)
    Path("results").mkdir(exist_ok=True)
    Path("results/eval.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    for name in ("gemini", "gemma"):
        if name in out:
            m = out[name]
            print(f"\n{name.upper()}: macro-F1 {m['macro_f1']} | accuracy {m['accuracy']} | "
                  f"big misses {m['big_misses']}/{m['n']} | abstain {m['abstain_rate']:.0%}")
    print("\nSaved results/eval.json")


if __name__ == "__main__":
    main()
