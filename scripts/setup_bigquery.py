"""Create the BigQuery dataset + table for the audit log, and upload existing results.

Usage:  python scripts/setup_bigquery.py buildathon-2026-515217
Location: US multi-region by default (widest support for BigQuery Gemini features / data agents).
          Override with BQ_LOCATION=asia-south1 in .env if you prefer.
Then put  BQ_TABLE=my-project-id.floodclaim.grades  in .env
Needs:  gcloud auth application-default login   (run once on your laptop)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import bq, pipeline  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_bigquery.py <gcp-project-id>")
        return
    from google.cloud import bigquery

    project = sys.argv[1]
    client = bigquery.Client(project=project)
    ds_id = f"{project}.floodclaim"
    ds = bigquery.Dataset(ds_id)
    import os
    ds.location = os.getenv("BQ_LOCATION", "US")
    client.create_dataset(ds, exists_ok=True)
    table_id = f"{ds_id}.grades"
    schema = [bigquery.SchemaField(name, typ) for name, typ in bq.SCHEMA]
    client.create_table(bigquery.Table(table_id, schema=schema), exists_ok=True)
    print(f"Ready: {table_id}")

    claims = {c["claim_id"]: c for c in pipeline.load_claims()}
    rows = [bq.to_row(claims.get(cid, {}), r) for cid, r in pipeline.load_results().items() if not r.get("error")]
    if rows:
        bq._bq = client
        bq.load_rows(rows, table_id)
        print(f"Uploaded {len(rows)} existing results.")
    print(f"\nNow add this line to .env:\nBQ_TABLE={table_id}")


if __name__ == "__main__":
    main()
