"""Settings, read from environment variables (or a .env file)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Check AI Studio for the newest model names and paste them into .env
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-3-27b-it")
USE_GEMMA = os.getenv("USE_GEMMA", "1") == "1"

# Optional: run Gemini on Vertex AI (needs billing + `gcloud auth application-default login`).
# Model names on Vertex can differ from AI Studio (no "-latest" aliases): use e.g. a dated Gemini Flash name.
USE_VERTEX = os.getenv("USE_VERTEX", "0") == "1"
GCP_PROJECT = os.getenv("GCP_PROJECT", "buildathon-2026-515217")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# Optional: "project.dataset.table" — if set, every grade is logged to BigQuery
BQ_TABLE = os.getenv("BQ_TABLE", "")

# Few-shot reference photos (data/fewshot/L0.jpg ... L4.jpg). Improved accuracy a lot in earlier tests.
USE_FEWSHOT = os.getenv("USE_FEWSHOT", "1") == "1"

DATA_DIR = ROOT / "data"
FEWSHOT_DIR = DATA_DIR / "fewshot"
PHOTOS_DIR = DATA_DIR / "photos"     # original demo photos
CLEAN_DIR = DATA_DIR / "clean"       # EXIF-stripped, resized copies (what we serve + send)
CLAIMS_CSV = DATA_DIR / "claims.csv"
RESULTS_JSON = DATA_DIR / "results.json"
