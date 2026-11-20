---
name: flood-grading
description: Rules for grading flood water level on a vehicle from a claim photo (L0-L4 or cant_tell), and for comparing it with the claimant's stated depth. Use whenever writing or changing grading prompts, triage scoring, evaluation code, or surveyor notes in this project.
---

# Flood grading rules (floodclaim)

## The scale — official STURM-FloodDepth levels (Notarangelo et al., 2025), water vs. the vehicle
| Level | Meaning |
|---|---|
| L0 | Not flooded: dry or only wet road surface |
| L1 | Water below half of the tyre height, below the chassis |
| L2 | Water between half and the whole tyre height (chassis to front marker lights / trunk) |
| L3 | Water between the top of the tyre and the side window (marker lights to windscreen) |
| L4 | Water above the bottom of the side window, or above the front/rear windscreen |

Method: identify the vehicle and visible parts → locate the waterline where water meets wheels/body
(reflections, wet paint, road puddles are not a waterline) → name the highest part reached → map to a level.
A clearly visible vehicle with no water on it is L0, not cant_tell.
Keep these definitions identical everywhere (prompts, eval, UI) so accuracy numbers stay comparable.

## Abstain rules — return `cant_tell` when
- No vehicle is visible, or the vehicle is too small / cut off to judge.
- The photo is too dark, blurry, or the water line on the vehicle cannot be seen.
- Reflections or angle make two levels equally likely.
`cant_tell` is a correct answer, not a failure. The surveyor asks the claimant for a better photo.

## Never over-call
- If unsure between two adjacent levels, choose the LOWER one and lower the confidence.
- Grade the deepest point of water touching THE vehicle, not water elsewhere in the scene.
- Waves, splashes, and wet marks above the current water line do not count.

## Claimant comparison
- Map the claimant's words to a level using the same scale ("ankle deep"/"touched the tyres"≈L1, "top of the tyres"/"knee deep"≈L2, "up to the doors"/"water inside the car, up to seats"≈L3, "up to the windows / roof / submerged"≈L4).
- If the claimant gives no depth, their level is `cant_tell` and no mismatch is raised.
- Claimant level − photo level ≥ 2 → **possible exaggeration** (flag for surveyor review, never auto-reject).
- Photo level − claimant level ≥ 2 → **under-reported** (damage may be worse than claimed).
- **Photo taken after the water went down:** if no standing water is visible, a higher claimant level is
  NOT exaggeration → `check_timing` (look for silt lines, ask for a photo from during the flood).
  Grade only standing water touching the car now; report mud/silt lines separately as receded water marks.

## Safety
- This is decision support for a human surveyor. Never auto-approve or auto-reject a claim.
- Strip EXIF/location metadata before storing or sending a photo.
- Demo data is synthetic. Never present synthetic claims as real customers.
