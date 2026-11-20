"""Optional BigQuery audit log. Active only when BQ_TABLE is set.

Logging runs in a background thread, so a slow or failing BigQuery call never slows the demo
or marks a claim as failed. The last error is shown at /api/health.
"""
from concurrent.futures import ThreadPoolExecutor

from . import config

_bq = None
_pool = ThreadPoolExecutor(max_workers=1)
last_error = ""

SCHEMA = [
    ("claim_id", "STRING"), ("policy_holder", "STRING"), ("area", "STRING"), ("claim_date", "STRING"),
    ("vehicle", "STRING"), ("level", "STRING"), ("level_num", "INTEGER"), ("confidence", "FLOAT"),
    ("claimant_level", "STRING"), ("mismatch", "STRING"), ("gemma_level", "STRING"),
    ("needs_review", "BOOLEAN"), ("duplicate_of", "STRING"), ("priority_score", "FLOAT"),
    ("evidence", "STRING"), ("surveyor_note_en", "STRING"), ("model", "STRING"), ("graded_at", "TIMESTAMP"),
]


def enabled() -> bool:
    return bool(config.BQ_TABLE)


def _client():
    global _bq
    if _bq is None:
        from google.cloud import bigquery
        project = config.BQ_TABLE.split(".")[0] if config.BQ_TABLE.count(".") == 2 else None
        _bq = bigquery.Client(project=project)
    return _bq


def to_row(claim: dict, result: dict) -> dict:
    level = result.get("level")
    return {
        "claim_id": result.get("claim_id"),
        "policy_holder": claim.get("policy_holder", ""),
        "area": claim.get("area", ""),
        "claim_date": claim.get("date", ""),
        "vehicle": claim.get("vehicle", ""),
        "level": level,
        "level_num": int(level[1]) if level and level.startswith("L") else None,
        "confidence": result.get("confidence"),
        "claimant_level": result.get("claimant_level"),
        "mismatch": result.get("mismatch"),
        "gemma_level": result.get("gemma_level"),
        "needs_review": result.get("needs_review"),
        "duplicate_of": result.get("duplicate_of"),
        "priority_score": result.get("priority_score"),
        "evidence": result.get("evidence"),
        "surveyor_note_en": result.get("surveyor_note_en"),
        "model": result.get("model"),
        "graded_at": result.get("graded_at"),
    }


def load_rows(rows: list[dict], table: str | None = None) -> None:
    """Append rows with a LOAD job (works in the BigQuery free sandbox; streaming inserts do not)."""
    from google.cloud import bigquery
    job_config = bigquery.LoadJobConfig(
        schema=[bigquery.SchemaField(n, t) for n, t in SCHEMA],
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    _client().load_table_from_json(rows, table or config.BQ_TABLE, job_config=job_config).result()


def _log_now(row: dict) -> None:
    global last_error
    try:
        load_rows([row])
        last_error = ""
    except Exception as exc:  # BigQuery is optional; the demo must keep working
        last_error = f"bigquery: {exc}"
        print(last_error)


def log(claim: dict, result: dict) -> None:
    """Queue one row for BigQuery in the background. Never blocks or crashes the app."""
    if enabled():
        _pool.submit(_log_now, to_row(claim, result))


def wait() -> None:
    """Block until queued rows are written (used by scripts before they exit)."""
    _pool.shutdown(wait=True)
