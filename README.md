# floodclaim

**Flood-depth triage for motor-insurance flood claims, built on Gemini + Gemma + Google Cloud.**

During the monsoon, insurers in Mumbai get a spike of flood-damage car claims. Surveyors judge
water depth by eye, one photo at a time: slow, inconsistent, and open to exaggerated claims.

floodclaim reads each claim photo and:
- **Grades the water level on the car** (L0–L4: tyre → chassis → door → window), or says **"can't tell"** instead of guessing
- **Shows the visual evidence** behind every grade
- **Compares the claimant's own words** with the photo and flags **possible exaggeration** or **under-reporting**
- **Flags duplicate photos** reused across claims
- **Won't accuse a claimant** whose photo was taken after the water receded: it asks the surveyor to check photo timing instead
- Gets a **second opinion from Gemma** and marks claims where the two models disagree for human review
- **Ranks the queue worst-first** and writes a short **surveyor note in English and Hindi**
- **Logs every decision to BigQuery** for audit, analytics (Conversational Analytics agent) and retraining

It is decision support: the surveyor always makes the final call. Demo data is synthetic.

## Architecture
```
Claim photo + claimant text
      │  EXIF/location stripped (Pillow)
      ▼
Gemini + few-shot examples (structured JSON) ──► level, evidence, claimant's level, EN/HI note
Gemma (second opinion)   ──► independent level → "models disagree" flag
Rules (SKILL.md)          ──► exaggeration / under-reported, priority score
Perceptual hash           ──► duplicate photos
      │
      ├──► FastAPI + dashboard on Cloud Run
      └──► BigQuery audit log ──► Conversational Analytics agent for claims managers
```
Built in Google Antigravity with a project skill: `.agents/skills/flood-grading/SKILL.md`.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then paste your Gemini API key into .env
python scripts/fetch_data.py --wikimedia   # STURM data, few-shot examples, demo photos
python scripts/make_claims.py # builds synthetic demo claims
python scripts/grade_all.py   # grades them with Gemini + Gemma
uvicorn app.main:app --reload --port 8080
# open http://localhost:8080
```

## Deploy to Cloud Run
```bash
gcloud run deploy floodclaim --source . --region asia-south1 --allow-unauthenticated \
  --max-instances 1 \
  --set-env-vars GEMINI_API_KEY=YOUR_KEY,GEMINI_MODEL=gemini-flash-latest,BQ_TABLE=PROJECT.floodclaim.grades
```
(Run `grade_all.py` before deploying so the demo opens with results already in `data/results.json`.
`--max-instances 1` keeps one copy of the app, so a claim uploaded in the demo is still there after a refresh.)

## Accuracy
```bash
python scripts/eval_sturm.py --images <test_images_dir> --labels <labels.csv> --gemma
```
Reports macro-F1, accuracy, big misses (off by 2+ levels) and abstain rate.

## Roadmap
1. Fine-tune Gemma vision on STURM-FloodDepth + Indian monsoon photos; serve on Vertex AI.
2. Insurer API + claim-system integration.
3. Pilot with a survey firm in the next monsoon season.
