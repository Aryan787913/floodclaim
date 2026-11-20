"""Claims store + grading pipeline + triage ranking."""
import csv
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import bq, config, grader, imaging
from .schemas import ClaimResult, LEVEL_RANK

DUP_THRESHOLD = 6  # max differing bits (of 64) to call two photos duplicates

_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=4)
CLAIM_FIELDS = ["claim_id", "policy_holder", "area", "date", "vehicle", "photo", "claimant_text"]


def load_claims() -> list[dict]:
    if not config.CLAIMS_CSV.exists():
        return []
    with config.CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("claim_id")]


def save_claims(claims: list[dict]) -> None:
    with config.CLAIMS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        for c in claims:
            w.writerow({k: c.get(k, "") for k in CLAIM_FIELDS})


def load_results() -> dict:
    if config.RESULTS_JSON.exists():
        return json.loads(config.RESULTS_JSON.read_text(encoding="utf-8"))
    return {}


def save_results(results: dict) -> None:
    config.RESULTS_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_path(claim_id: str):
    return config.CLEAN_DIR / f"{claim_id}.jpg"


def ensure_clean(claim: dict) -> bytes:
    """EXIF-stripped copy of the claim photo (created once)."""
    dst = clean_path(claim["claim_id"])
    if dst.exists():
        return dst.read_bytes()
    src = config.PHOTOS_DIR / claim["photo"]
    return imaging.clean_file(src, dst)


def duplicate_map(claims: list[dict]) -> dict:
    """claim_id -> earlier claim_id whose photo is (near) identical."""
    seen: list[tuple[str, int]] = []
    dups = {}
    for c in claims:
        try:
            h = imaging.dhash(ensure_clean(c))
        except Exception:
            continue
        ones = bin(h).count("1")
        if ones <= 4 or ones >= 60:
            continue  # near-blank / very dark photo: its fingerprint is meaningless, never call it a duplicate
        for other_id, other_h in seen:
            if imaging.hamming(h, other_h) <= DUP_THRESHOLD:
                dups[c["claim_id"]] = other_id
                break
        seen.append((c["claim_id"], h))
    return dups


def priority(r: dict) -> float:
    if r.get("error"):
        return 0.0
    if r.get("level") == "cant_tell":
        score = 5.0
    else:
        score = LEVEL_RANK.get(r.get("level"), 0) * 20 + float(r.get("confidence") or 0) * 5
    if r.get("mismatch") == "possible_exaggeration":
        score += 25
    elif r.get("mismatch") == "under_reported":
        score += 15
    elif r.get("mismatch") == "check_timing":
        score += 10
    if r.get("duplicate_of"):
        score += 30
    if r.get("needs_review"):
        score += 10
    return round(score, 1)


def grade_claim(claim: dict, dup_of: str | None = None) -> dict:
    jpeg = ensure_clean(claim)
    now = datetime.now(timezone.utc).isoformat()
    gemma_future = _pool.submit(grader.gemma_level, jpeg)  # second opinion runs in parallel with Gemini
    try:
        g = grader.gemini_grade(jpeg, claim.get("claimant_text", ""))
    except Exception as exc:
        r = ClaimResult(claim_id=claim["claim_id"], level="cant_tell", confidence=0, evidence="",
                        error=f"Grading failed: {exc}", graded_at=now, model=config.GEMINI_MODEL)
        return r.model_dump()

    mismatch, reason = grader.compare_claim(g.level, g.claimant_level, g.standing_water_visible)
    try:
        gemma = gemma_future.result(timeout=60)
    except Exception:
        gemma = None
    if g.level == "cant_tell":
        gemma = None
    r = ClaimResult(
        claim_id=claim["claim_id"],
        level=g.level,
        confidence=g.confidence,
        evidence=g.evidence,
        photo_quality_issue=g.photo_quality_issue,
        claimant_level=g.claimant_level,
        claimant_depth_quote=g.claimant_depth_quote,
        mismatch=mismatch,
        mismatch_reason=reason,
        standing_water_visible=g.standing_water_visible,
        receded_water_marks=g.receded_water_marks,
        gemma_level=gemma,
        needs_review=grader.models_disagree(g.level, gemma),
        duplicate_of=dup_of,
        surveyor_note_en=g.surveyor_note_en,
        surveyor_note_hi=g.surveyor_note_hi,
        model=config.GEMINI_MODEL + (f" + {config.GEMMA_MODEL}" if gemma else ""),
        graded_at=now,
    ).model_dump()
    r["priority_score"] = priority(r)
    bq.log(claim, r)  # background; a BigQuery problem never marks the claim as failed
    return r


def queue() -> list[dict]:
    """All claims merged with results, worst first."""
    claims = load_claims()
    results = load_results()
    dups = duplicate_map(claims)
    rows = []
    for c in claims:
        r = dict(results.get(c["claim_id"], {}))
        if r:
            r["duplicate_of"] = dups.get(c["claim_id"])  # always fresh
            r["priority_score"] = priority(r)
        rows.append({**c, "result": r or None, "duplicate_of": dups.get(c["claim_id"])})
    rows.sort(key=lambda x: (x["result"] is not None, (x["result"] or {}).get("priority_score", 0)), reverse=True)
    return rows


def grade_pending(force: bool = False) -> int:
    claims = load_claims()
    dups = duplicate_map(claims)
    count = 0
    for c in claims:
        with _lock:
            results = load_results()
            if c["claim_id"] in results and not force and not results[c["claim_id"]].get("error"):
                continue
        r = grade_claim(c, dups.get(c["claim_id"]))
        with _lock:
            results = load_results()
            results[c["claim_id"]] = r
            save_results(results)
        count += 1
        print(f"  {c['claim_id']}: {r['level']} (mismatch={r['mismatch']}) {r.get('error', '')}")
    return count


def add_claim(photo_bytes: bytes, policy_holder: str, area: str, vehicle: str, claimant_text: str) -> dict:
    with _lock:
        claims = load_claims()
        n = 1 + max([int(c["claim_id"].split("-")[-1]) for c in claims if c["claim_id"].split("-")[-1].isdigit()] or [0])
        claim_id = f"CLM-{n:04d}"
        fname = f"{claim_id}.jpg"
        (config.PHOTOS_DIR / fname).write_bytes(imaging.clean_image(photo_bytes))
        claim = {
            "claim_id": claim_id, "policy_holder": policy_holder or "Walk-in claimant", "area": area or "Mumbai",
            "date": datetime.now().strftime("%Y-%m-%d"), "vehicle": vehicle or "Car", "photo": fname,
            "claimant_text": claimant_text,
        }
        claims.append(claim)
        save_claims(claims)
    dups = duplicate_map(load_claims())
    r = grade_claim(claim, dups.get(claim_id))
    with _lock:
        results = load_results()
        results[claim_id] = r
        save_results(results)
    return {**claim, "result": r, "duplicate_of": dups.get(claim_id)}


def stats() -> dict:
    rows = queue()
    graded = [r["result"] for r in rows if r["result"]]
    by_level = {lv: 0 for lv in ["L0", "L1", "L2", "L3", "L4", "cant_tell"]}
    for g in graded:
        by_level[g["level"]] = by_level.get(g["level"], 0) + 1
    return {
        "total": len(rows),
        "graded": len(graded),
        "severe": sum(1 for g in graded if g["level"] in ("L3", "L4")),
        "exaggeration": sum(1 for g in graded if g["mismatch"] == "possible_exaggeration"),
        "under_reported": sum(1 for g in graded if g["mismatch"] == "under_reported"),
        "duplicates": sum(1 for r in rows if r["duplicate_of"]),
        "cant_tell": sum(1 for g in graded if g["level"] == "cant_tell" and not g.get("error")),
        "check_timing": sum(1 for g in graded if g["mismatch"] == "check_timing"),
        "needs_review": sum(1 for g in graded if g.get("needs_review")),
        "by_level": by_level,
        "bigquery": bq.enabled(),
        "bigquery_error": bq.last_error,
        "model": config.GEMINI_MODEL,
    }
