"""Build a SYNTHETIC demo claims list (data/claims.csv) from the photos in data/photos/.

Usage:  python scripts/make_claims.py
- Put 20-40 flood photos with a car visible into data/photos/ first.
- Creates 2 duplicate claims (same photo re-saved, different claimant) to show duplicate detection.
- Claimant texts state a range of depths, so some will disagree with the photo (exaggeration demo).
All names are fictional. Label the demo as synthetic.
"""
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, pipeline  # noqa: E402

random.seed(7)

FIRST = ["Rohan", "Priya", "Imran", "Sneha", "Vikram", "Ananya", "Farhan", "Kavita", "Aditya", "Meera",
         "Sahil", "Pooja", "Nikhil", "Zoya", "Rahul", "Divya", "Arjun", "Neha", "Kunal", "Ritu"]
LAST = ["Demo-Shah", "Demo-Patil", "Demo-Khan", "Demo-Iyer", "Demo-Desai", "Demo-Rao", "Demo-Mehta",
        "Demo-Joshi", "Demo-Pillai", "Demo-Kulkarni"]
AREAS = ["Andheri", "Kurla", "Sion", "Dadar", "Chembur", "Malad", "Borivali", "Ghatkopar", "Hindmata", "Bandra"]
VEHICLES = ["Maruti Swift (hatchback)", "Hyundai i20 (hatchback)", "Honda City (sedan)", "Tata Nexon (SUV)",
            "Mahindra XUV (SUV)", "Maruti Dzire (sedan)", "Toyota Innova (MPV)", "Tata Punch (micro-SUV)"]

TEXTS = [
    # no depth stated
    "Car was parked in our lane overnight during heavy rain. Next morning it would not start.",
    "Got stuck near the subway in the evening rain. Had to leave the car and walk home.",
    # L1-ish
    "Water was ankle deep around the car, only touched the tyres. Some noise from the brakes now.",
    # L2-ish
    "Water came up to the top of the tyres, roughly knee deep. Engine stalled while driving.",
    "Knee-deep water near the station, tyres fully under water, car stopped and I pushed it out.",
    # L3-ish
    "Water entered inside the car up to the seats. Carpets and seats soaked, electricals not working.",
    "Water came inside the cabin, mats floating. Car stuck for 6 hours.",
    # L4-ish
    "Water rose up to the windows, car was almost fully under water. Total loss, engine seized.",
    "Car was completely submerged up to the roof in the basement parking. Please process total loss.",
    "Water reached the windows, I had to climb out. Engine, gearbox and all electronics damaged.",
]


def main():
    photos = sorted(p for p in config.PHOTOS_DIR.iterdir()
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and not p.name.startswith("CLM-DUP"))
    if not photos:
        print("No photos found in data/photos/. Add flood photos with a car visible, then run again.")
        return
    claims = []
    start = date(2026, 7, 14)
    for i, p in enumerate(photos, 1):
        claims.append({
            "claim_id": f"CLM-{i:04d}",
            "policy_holder": f"{random.choice(FIRST)} {random.choice(LAST)}",
            "area": random.choice(AREAS),
            "date": (start + timedelta(days=random.randint(0, 6))).isoformat(),
            "vehicle": random.choice(VEHICLES),
            "photo": p.name,
            "claimant_text": random.choice(TEXTS),
        })

    # Two duplicate claims: same photo re-saved smaller, filed by a different person later
    for k, src in enumerate(random.sample(photos, k=min(2, len(photos))), 1):
        img = Image.open(src).convert("RGB")
        img = img.resize((int(img.width * 0.85), int(img.height * 0.85)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        name = f"CLM-DUP{k}.jpg"
        (config.PHOTOS_DIR / name).write_bytes(buf.getvalue())
        claims.append({
            "claim_id": f"CLM-{len(claims) + 1:04d}",
            "policy_holder": f"{random.choice(FIRST)} {random.choice(LAST)}",
            "area": random.choice(AREAS),
            "date": (start + timedelta(days=random.randint(5, 9))).isoformat(),
            "vehicle": random.choice(VEHICLES),
            "photo": name,
            "claimant_text": TEXTS[-2],  # strong total-loss claim on a reused photo
        })

    pipeline.save_claims(claims)
    print(f"Wrote {len(claims)} synthetic claims to {config.CLAIMS_CSV}")


if __name__ == "__main__":
    main()
