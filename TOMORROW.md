# TOMORROW — exact steps (solo)

You don't need to code. You'll copy the prompts below into the **Antigravity agent panel** (right side).
Allow it to run commands when it asks.

---

## TONIGHT (15 min, then SLEEP)
- [ ] Accept the RSVP invite email and **screenshot your QR code**
- [ ] Install **Antigravity IDE (standalone)** from antigravity.google/download and sign in
- [ ] Get a **Gemini API key**: aistudio.google.com → "Get API key" → copy it into your phone notes. Prefer a key on the **free tier** (a project with no billing), so grading keeps working if the event credits end at 10:45.
- [ ] Unzip `floodclaim.zip` somewhere easy (e.g. Desktop)
- [ ] Pack: ID, laptop, charger, power bank. Alarm 6:30.

---

## DAY 1

### 8:00–10:00 (venue)
- [ ] Scan QR. Ask for **Antigravity credits**. (You already have AI Pro, so skip the AI Pro form.)
- [ ] **FIRST QUESTION TO STAFF: "My Cloud credits expire at 10:45 AM today and there's no card. Are fresh Day-1 credits available?"**
      Without billing, Cloud Run and the BigQuery agent can stop working after 10:45. Grading (Gemini API key) still works.
- [ ] Use project **buildathon-2026-515217** (don't create a new one).
- [ ] Write down any **judging criteria / submission format** they announce.

### 10:00 — Prompt 1 (setup)
Open the `floodclaim` folder in Antigravity, then paste:
```
Read README.md, GEMINI.md and .agents/skills/flood-grading/SKILL.md.
Create a Python virtual environment, install requirements.txt, and create .env from .env.example.
I will paste my Gemini API key into .env myself. Then tell me exactly where to paste it.
```
→ Paste your key into `.env` (the line `GEMINI_API_KEY=`).

### Prompt 2 (get data + grade)
```
Run: python scripts/fetch_data.py --wikimedia
Then: python scripts/make_claims.py
Then: python scripts/grade_all.py
Show me any errors and fix them. If the model name fails, list the available Gemini and Gemma
models for my key and set the best Gemini Flash model and a Gemma vision model in .env.
```
This downloads the STURM flood-car photos (+ 6 real Indian monsoon photos), picks few-shot examples,
builds 32 synthetic claims and grades them. `data/demo_truth.csv` has the true level of each demo photo.
**If the download is very slow on venue Wi-Fi (more than 10 minutes):** switch to your phone hotspot, or press Ctrl+C.
The script then continues without STURM. Run `python scripts/fetch_data.py --no-sturm --wikimedia` for a demo-only setup
(no few-shot examples and no accuracy slide, but the demo works). Retry STURM later on better Wi-Fi.

### Prompt 3 (run it)
```
Start the app with uvicorn on port 8080 and open it in the browser.
```
→ You should see the claims queue. **Commit to GitHub now** (ask Antigravity: "commit and push to a new GitHub repo named floodclaim").

### ⚠️ Prompt 4 (BigQuery + Cloud Run): do it RIGHT AFTER Prompt 3, before 10:30 AM, unless staff gave fresh credits
```
Using Google Cloud project buildathon-2026-515217: run gcloud auth login and gcloud auth application-default login,
enable the BigQuery, Cloud Run, Cloud Build and Artifact Registry APIs,
run scripts/setup_bigquery.py buildathon-2026-515217, add the BQ_TABLE line it prints to .env,
then deploy to Cloud Run in asia-south1 using the README command with my .env values as env vars.
Ask me before running anything that costs money. Give me the public URL.
```
→ **Open the URL on your phone** to check it works. This is your live demo link.
If billing ends at 10:45 and the URL stops working: **demo on localhost**. It's fine, and you can say so honestly.

### 11:30 — Mentor round
Show: the queue → click a red "Possible exaggeration" claim → the Hindi note → "+ New claim" upload.
Ask: **"If you were judging, what's the weakest part?"** Write it down.

### 12:00–1:30 — Fix what the mentor said + check grades
Click through every claim. If a grade looks wrong, tell Antigravity:
```
Claim CLM-00XX is graded L1 but the water is clearly at the door (L3). Improve the grading prompt in
app/grader.py following SKILL.md, then re-run scripts/grade_all.py --force.
```

### 1:30–2:30 — LUNCH (don't skip)

### 2:30 — Re-deploy (only if billing is still active)
```
Re-run scripts/grade_all.py, then redeploy to Cloud Run with the same settings.
```

### 3:30 — Conversational Analytics agent (in the browser, ~20 min)
console.cloud.google.com → BigQuery → **Agents** → **New agent**
- Needs billing. First, in IAM, give yourself **Gemini Data Analytics Data Agent Owner**, and enable the Data Analytics API with Gemini, the Gemini in BigQuery API and the Gemini for Google Cloud API.
- Name: `Flood Claims Analyst`. Knowledge source: table `floodclaim.grades`
- Instructions: paste the contents of `GEMINI.md`
- On each table click **Customize** → accept suggested descriptions → **Apply to all** → Save → Publish
- Test: *"How many L3 or L4 claims per area?"* and *"Which claims have possible exaggeration?"*

### 4:00–6:00 — Accuracy numbers (strong slide)
```
Run the accuracy command that scripts/fetch_data.py printed at the end (eval_sturm.py with --limit 150 --gemma).
Show me macro-F1, big misses and abstain rate for Gemini and Gemma.
```
→ Compare with your old numbers (CLIP baseline 0.580 grouped / 0.619 official; best old hybrid 0.647).
Put the numbers on one slide. Be honest if Gemini is lower; "says can't tell instead of guessing" is a strength.
**If you didn't run the eval, delete the two "floodclaim" rows from the accuracy slide. Never leave [__] on a slide you present.**

### 6:00 — FEATURE FREEZE. Nothing new after this.

---

## NIGHT
- [ ] Deck is already made: https://claude.ai/artifact/DekUQLiQcZVGv4svQmKt5u. First make the **5 slide edits** listed at the top of the project doc "pitch-prep-and-outreach". Then fill every [__] (accuracy, price, surveyor quote) and put a dashboard screenshot on slide 4. If their PPT template is required, copy the text into it. The pitch script is in the speaker notes.
- [ ] Record a **2-min backup demo video** (phone screen-record is fine)
- [ ] Practise the pitch out loud 3–4 times, timed
- [ ] **11:00 PM: SUBMIT** (repo link + live URL + deck + video)
- [ ] Sleep by 11:30

## DAY 2
- 7:30 check submission went through · 10–1 mentor evaluation · 2–5:30 showcase · 6:00 results
- Lead with the **exaggeration catch**: "Claimant says water up to the windows, photo shows tyre level."

## If something breaks
- Stuck 20 min on one thing → **drop it**, move on.
- App broken after a change → ask Antigravity: "revert to the last git commit".
- Wi-Fi dies → show the backup video.

## Pitch answers to keep ready
- **"Isn't this just a Gemini prompt?"** → The product is the claims workflow: evidence, mismatch catch, duplicates, second-model check, audit log, measured accuracy on flood photos.
- **"Seasonal?"** → Multiple monsoons across India + other countries, then cyclone/hail claims.
- **"Who pays?"** → Survey firms and insurers, per photo checked, monsoon plan. Survey firms first (faster buyers).
- **"Different from your earlier hackathon?"** → That was a research prototype on another model. This is the insurer product, rebuilt on Gemini + Gemma with a claims workflow.
- **"Solo?"** → Built solo in a day; looking for a co-founder from insurance.
