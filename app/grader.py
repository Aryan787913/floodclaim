"""Gemini grades the photo; Gemma gives an independent second opinion."""
import re
import time

from . import config
from .schemas import GeminiGrade, LEVEL_RANK

LEVEL_RULES = """
Water level is judged AGAINST THE VEHICLE in the photo (STURM-FloodDepth scale):
- L0: not flooded - dry or only wet road surface.
- L1: water below half of the tyre height, below the chassis.
- L2: water between half and the whole tyre height (between the chassis and the front marker lights / trunk).
- L3: water between the top of the tyre and the side window (between the marker lights and the windscreen).
- L4: water above the bottom of the side window, or above the front/rear windscreen.
- cant_tell: no vehicle visible, photo too dark/blurry/occluded, or the waterline on the vehicle cannot be seen.
How to judge: find the car, find the line where flood water touches its wheels or body, and grade by the
highest car part that line reaches. Shiny reflections, wet bodywork and puddles on the road do not count as water level.
A clearly visible vehicle with no water on it is L0, not cant_tell.
If unsure between two adjacent levels choose the LOWER one and lower the confidence.
"cant_tell" is a correct, respected answer - never guess.
If the water has already gone down, grade only standing water touching the car NOW, and separately report
whether mud/silt lines or debris on the car show where the water reached earlier (receded_water_marks),
describing the highest such mark in the evidence.
"""

FEWSHOT_INTRO = ("Below are five sample photos with known levels, L0 to L4, so you can see where each level "
                 "starts on a real car. After them comes the CLAIM photo to grade.")

GEMINI_PROMPT = """You assist a motor-insurance flood surveyor in India.
Look at the claim photo and grade the flood water level on the vehicle.
{rules}
Then read the claimant's description below and map ONLY their stated depth to the same scale
("ankle deep" / "touched the tyres" ~ L1; "up to the top of the tyres" / "knee deep" ~ L2;
"up to the doors" / "water inside the car / up to the seats" ~ L3; "up to the windows / roof / submerged" ~ L4).
If they state no depth, claimant_level = cant_tell.

Write surveyor_note_en: 2-3 short sentences: the grade, the visual evidence, and what the surveyor
should check next (e.g. engine hydrostatic lock check for L3+, ask for a clearer photo if cant_tell,
verify if the claimant's depth disagrees with the photo). Neutral tone, never accuse the claimant.
Write surveyor_note_hi: the same note in simple Hindi (Devanagari).

Claimant description:
\"\"\"{claimant_text}\"\"\"
"""

GEMMA_PROMPT = """Look at this flood photo. Grade how high the flood water reaches on the vehicle.
{rules}
Answer with exactly one token from: L0, L1, L2, L3, L4, CANT_TELL. No other words."""

_client = None


def client():
    """AI Studio key client (used for Gemma, and for Gemini unless USE_VERTEX=1)."""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Put it in the .env file.")
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


_vertex = None


def gemini_client():
    """Gemini on Vertex AI when USE_VERTEX=1 (needs billing + gcloud auth), else the AI Studio key."""
    global _vertex
    if not config.USE_VERTEX:
        return client()
    if _vertex is None:
        from google import genai
        _vertex = genai.Client(vertexai=True, project=config.GCP_PROJECT, location=config.GCP_LOCATION)
    return _vertex


def _with_retry(fn, tries: int = 3):
    for attempt in range(tries):
        try:
            return fn()
        except Exception:  # rate limits / transient network errors
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


_fewshot_cache = None


def fewshot_parts():
    """Reference images data/fewshot/L0.jpg ... L4.jpg (from the STURM train split), if present."""
    global _fewshot_cache
    if _fewshot_cache is None:
        from google.genai import types
        parts = []
        if config.USE_FEWSHOT:
            for lv in range(5):
                p = config.FEWSHOT_DIR / f"L{lv}.jpg"
                if p.exists():
                    parts += [f"Reference example - level L{lv}:", types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg")]
        _fewshot_cache = ([FEWSHOT_INTRO] + parts) if parts else []
    return _fewshot_cache


def gemini_grade(jpeg: bytes, claimant_text: str) -> GeminiGrade:
    from google.genai import types

    def call():
        resp = gemini_client().models.generate_content(
            model=config.GEMINI_MODEL,
            contents=fewshot_parts() + [
                "CLAIM photo:",
                types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
                GEMINI_PROMPT.format(rules=LEVEL_RULES, claimant_text=claimant_text or "(no description given)"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiGrade,
                temperature=0,
            ),
        )
        if resp.parsed is not None:
            return resp.parsed
        return GeminiGrade.model_validate_json(resp.text)

    grade = _with_retry(call)
    grade.confidence = max(0.0, min(1.0, float(grade.confidence)))
    if not grade.vehicle_visible:
        grade.level = "cant_tell"
    return grade


def gemma_level(jpeg: bytes) -> str | None:
    """Second opinion from Gemma. Returns a level string or None if it fails."""
    if not config.USE_GEMMA:
        return None
    from google.genai import types

    def call():
        resp = client().models.generate_content(
            model=config.GEMMA_MODEL,
            contents=[
                types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
                GEMMA_PROMPT.format(rules=LEVEL_RULES),
            ],
            config=types.GenerateContentConfig(temperature=0),
        )
        return resp.text or ""

    try:
        text = _with_retry(call).upper()
    except Exception:
        return None
    if "CANT" in text or "CAN'T" in text:
        return "cant_tell"
    m = re.search(r"\bL([0-4])\b", text)
    return f"L{m.group(1)}" if m else None


def compare_claim(photo_level: str, claimant_level: str, standing_water: bool = True) -> tuple[str, str]:
    """Deterministic mismatch rule (see SKILL.md)."""
    if photo_level not in LEVEL_RANK or claimant_level not in LEVEL_RANK:
        return "none", ""
    diff = LEVEL_RANK[claimant_level] - LEVEL_RANK[photo_level]
    if diff >= 2 and not standing_water:
        # Photo probably taken after the water went down: never call that exaggeration.
        return "check_timing", (
            f"Claimant describes {claimant_level}, but no standing water is visible in the photo, so it may have been "
            "taken after the water receded. Check for silt lines inside and outside the car, or ask for a photo "
            "taken during the flood.")
    if diff >= 2:
        return "possible_exaggeration", (
            f"Claimant describes {claimant_level} but the photo shows {photo_level}. Verify before settlement.")
    if diff <= -2:
        return "under_reported", (
            f"Photo shows {photo_level}, deeper than the claimant's {claimant_level}. Damage may be worse than reported.")
    return "none", ""


def models_disagree(a: str | None, b: str | None) -> bool:
    if a in LEVEL_RANK and b in LEVEL_RANK:
        return abs(LEVEL_RANK[a] - LEVEL_RANK[b]) >= 2
    return False
