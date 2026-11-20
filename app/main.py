"""floodclaim web app: claims queue for motor-insurance flood surveyors."""
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, pipeline

app = FastAPI(title="floodclaim", description="Flood-depth triage for motor insurance claims")
config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def home():
    return FileResponse(config.ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    from . import bq
    return {"ok": True, "model": config.GEMINI_MODEL, "api_key_set": bool(config.GEMINI_API_KEY),
            "vertex": config.USE_VERTEX, "bigquery": bq.enabled(), "bigquery_error": bq.last_error}


@app.get("/api/claims")
def claims():
    return pipeline.queue()


@app.get("/api/stats")
def stats():
    return pipeline.stats()


@app.get("/api/photo/{claim_id}")
def photo(claim_id: str):
    for c in pipeline.load_claims():
        if c["claim_id"] == claim_id:
            pipeline.ensure_clean(c)
            return FileResponse(pipeline.clean_path(claim_id), media_type="image/jpeg")
    raise HTTPException(404, "claim not found")


@app.post("/api/claims")
async def new_claim(
    photo: UploadFile = File(...),
    claimant_text: str = Form(""),
    policy_holder: str = Form(""),
    area: str = Form(""),
    vehicle: str = Form(""),
):
    data = await photo.read()
    if not data:
        raise HTTPException(400, "empty photo")
    return await run_in_threadpool(pipeline.add_claim, data, policy_holder, area, vehicle, claimant_text)


@app.post("/api/grade_pending")
async def grade_pending():
    n = await run_in_threadpool(pipeline.grade_pending)
    return {"graded": n}


app.mount("/static", StaticFiles(directory=config.ROOT / "static"), name="static")
