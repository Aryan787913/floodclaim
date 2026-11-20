"""Data shapes shared across the app."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Level = Literal["L0", "L1", "L2", "L3", "L4", "cant_tell"]
LEVELS = ["L0", "L1", "L2", "L3", "L4"]
LEVEL_RANK = {lv: i for i, lv in enumerate(LEVELS)}

LEVEL_LABEL = {
    "L0": "Not flooded",
    "L1": "Below half tyre",
    "L2": "Half to full tyre",
    "L3": "Tyre top to window",
    "L4": "Window or above",
    "cant_tell": "Can't tell - need a better photo",
}


class GeminiGrade(BaseModel):
    """Structured output requested from Gemini."""
    vehicle_visible: bool = Field(description="True if a car/vehicle is clearly visible")
    standing_water_visible: bool = Field(description="True if standing flood water is visible in the photo right now")
    receded_water_marks: bool = Field(description="True if mud/silt lines or debris on the vehicle show where water reached earlier")
    level: Level = Field(description="Water level against the vehicle, or cant_tell")
    confidence: float = Field(description="0 to 1")
    evidence: str = Field(description="Which vehicle part the water reaches and what in the photo shows it. One or two sentences.")
    photo_quality_issue: str = Field(description="Empty string if photo is fine, else what is wrong (dark, blurry, no vehicle...)")
    claimant_level: Level = Field(description="Level implied by the claimant's own words, or cant_tell if they gave no depth")
    claimant_depth_quote: str = Field(description="The words in the claimant text that describe depth, or empty string")
    surveyor_note_en: str = Field(description="2-3 sentence note for the surveyor in plain English")
    surveyor_note_hi: str = Field(description="The same note in simple Hindi (Devanagari)")


class ClaimResult(BaseModel):
    claim_id: str
    level: Level
    confidence: float
    evidence: str
    photo_quality_issue: str = ""
    claimant_level: Level = "cant_tell"
    claimant_depth_quote: str = ""
    mismatch: Literal["none", "possible_exaggeration", "under_reported", "check_timing"] = "none"
    standing_water_visible: bool = True
    receded_water_marks: bool = False
    mismatch_reason: str = ""
    gemma_level: Optional[Level] = None
    needs_review: bool = False
    duplicate_of: Optional[str] = None
    priority_score: float = 0.0
    surveyor_note_en: str = ""
    surveyor_note_hi: str = ""
    model: str = ""
    graded_at: str = ""
    error: str = ""
