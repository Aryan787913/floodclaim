## 1. Project Context
- Project ID: buildathon-2026-515217
- Domain: flood car-insurance claims; claim photos graded L0-L4 by flood water depth against the car
  (L0 not flooded, L1 below half tyre, L2 half to full tyre, L3 tyre top to window, L4 window or above),
  or "cant_tell" when the photo is unusable.
- Data: claims and grades are in BigQuery dataset `floodclaim`, table `grades`.
- Grading rules: .agents/skills/flood-grading/SKILL.md

## 2. Rules
- Always reference tables with the dataset ID, e.g. `floodclaim.grades`.
- `mismatch = 'possible_exaggeration'`: the claimant's stated level is 2 or more levels HIGHER than the photo grade.
- `mismatch = 'under_reported'`: the photo grade is 2 or more levels higher than the claimant's stated level.
- `mismatch = 'check_timing'`: the claimant's level is 2+ higher but no standing water is visible in the photo
  (likely taken after the water receded). This is NOT an exaggeration flag.
- A difference of 1 level is not flagged (normal disagreement).
- `level_num` is 0-4 for graded photos and NULL for cant_tell.
- Answer only from the tables; never invent claims, numbers or customers. Demo claims are synthetic.
- This is decision support: never recommend approving or rejecting a claim automatically.
