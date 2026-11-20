"""ONE command to get all data ready (works on Windows/Mac/Linux, needs internet):

    python scripts/fetch_data.py              # STURM data + few-shot examples + 30 demo photos
    python scripts/fetch_data.py --wikimedia  # also add real Indian monsoon photos from Wikimedia Commons
    python scripts/fetch_data.py --no-sturm --wikimedia   # FALLBACK if the STURM download is too slow/fails
      (then: no few-shot examples and no accuracy test, but the demo still works)

What it does
1. Downloads STURM-FloodDepth "Flooded Cars" (Notarangelo 2025, CC BY 4.0, doi:10.5281/zenodo.14833532)
2. Writes data/sturm/test_labels.csv  -> for scripts/eval_sturm.py (accuracy numbers)
3. Copies one TRAIN image per level to data/fewshot/L0..L4.jpg -> reference examples for Gemini
   (taken only from source photos that are NOT in val/test, so the test score stays fair)
4. Copies 30 TEST images (6 per level, different source photos) to data/photos/ for the demo queue
   and writes data/demo_truth.csv so you can check grades by eye
5. Writes data/ATTRIBUTION.md (credit the dataset / photo authors on your slides)
"""
import csv
import hashlib
import random
import re
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, imaging  # noqa: E402

ZENODO = "https://zenodo.org/records/14833532/files"
ZIP_MD5 = "d1e4de73145e807dd691718aea136508"
STURM = config.DATA_DIR / "sturm"
IMAGES = STURM / "upscaled_images"
UA = {"User-Agent": "floodclaim-buildathon/1.0 (educational demo)"}

# Real Indian monsoon photos (Wikimedia Commons). Verify each licence on its page before using in slides.
WIKIMEDIA = [
    ("Bombay_flooded_street.jpg", "CC BY 2.0"),
    ("Flooding_in_Mumbai,_India_2017.jpg", "CC BY-SA 4.0 (Paasikivi)"),
    ("Chennai-floods-2015-dec-3.jpg", "CC BY-SA 4.0 (Destination8infinity)"),
    ('A_Santro_that_went_"off_road"_(35520266).jpg', "CC BY-SA 2.0 (Rakesh from Bangalore)"),
    ("2020_Hyderabad_floods.jpg", "CC BY-SA 4.0 (Strike Eagle)"),
    ("Car_after_flood.jpg", "CC BY-SA 4.0 (Sreerag S J)"),
]


def download(url: str, dst: Path) -> None:
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  already have {dst.name}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {dst.name} ...")
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done >> 20} / {total >> 20} MB", end="")
    print()
    tmp.rename(dst)


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_split(name: str) -> list[tuple[str, int]]:
    out = []
    for line in (STURM / "splits" / f"{name}.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip().replace("\\", "/")
        if line:
            out.append((line, int(re.search(r"Level(\d)", line).group(1))))
    return out


def source_id(relpath: str) -> str:
    """Crops of the same source photo share 'car-N' / 'car2-N'."""
    m = re.match(r"(car\d*-\d+)-Level", Path(relpath).name)
    return m.group(1) if m else Path(relpath).stem


def get_sturm() -> None:
    print("1/5 STURM-FloodDepth")
    zpath = STURM / "flooded_cars.zip"
    download(f"{ZENODO}/flooded_cars.zip?download=1", zpath)
    got = md5(zpath)
    if got != ZIP_MD5:
        print(f"  WARNING: checksum {got} != expected {ZIP_MD5}. If unzip fails, delete the zip and rerun.")
    if not IMAGES.exists():
        print("  unzipping ...")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(STURM)
    for s in ("train", "val", "test"):
        download(f"{ZENODO}/{s}.txt?download=1", STURM / "splits" / f"{s}.txt")


def write_test_labels(test) -> None:
    print("2/5 test labels")
    out = STURM / "test_labels.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "label"])
        for rel, lv in test:
            w.writerow([rel, lv])
    print(f"  {len(test)} test images -> {out}")


def pick_fewshot(train, banned: set) -> None:
    print("3/5 few-shot reference examples")
    rng = random.Random(0)
    config.FEWSHOT_DIR.mkdir(parents=True, exist_ok=True)
    pool = [(r, lv) for r, lv in train if source_id(r) not in banned]
    rng.shuffle(pool)
    for lv in range(5):
        cands = [r for r, l in pool if l == lv][:40]
        if not cands:
            print(f"  no train image for L{lv}")
            continue
        from PIL import Image
        best = max(cands, key=lambda r: (lambda im: im.width * im.height)(Image.open(IMAGES / r)))
        imaging.clean_file(IMAGES / best, config.FEWSHOT_DIR / f"L{lv}.jpg")
        print(f"  L{lv}: {best}")


def pick_demo(test, per_level: int = 6) -> None:
    print("4/5 demo photos")
    existing = [p for p in config.PHOTOS_DIR.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if existing and "--force" not in sys.argv:
        print(f"  data/photos already has {len(existing)} photos - skipping (use --force to replace)")
        return
    rng = random.Random(3)
    chosen = []
    seen = set()  # one crop per source photo across ALL levels, so no accidental "duplicates"
    for lv in range(5):
        items = [(r, l) for r, l in test if l == lv]
        rng.shuffle(items)
        n = 0
        for r, l in items:
            if source_id(r) in seen:
                continue
            seen.add(source_id(r))
            chosen.append((r, l))
            n += 1
            if n == per_level:
                break
    rng.shuffle(chosen)
    config.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    with (config.DATA_DIR / "demo_truth.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["photo", "true_level", "sturm_file"])
        for i, (r, l) in enumerate(chosen, 1):
            name = f"demo_{i:02d}.jpg"
            shutil.copyfile(IMAGES / r, config.PHOTOS_DIR / name)
            w.writerow([name, f"L{l}", r])
    print(f"  {len(chosen)} photos -> data/photos/ (true levels in data/demo_truth.csv)")


def get_wikimedia() -> list[str]:
    print("   Wikimedia Commons photos")
    credits = []
    for i, (fname, lic) in enumerate(WIKIMEDIA, 1):
        url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fname) + "?width=1280"
        dst = config.PHOTOS_DIR / f"india_{i:02d}.jpg"
        try:
            download(url, dst)
            credits.append(f"- {dst.name}: https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(fname)} — {lic}")
        except Exception as exc:
            print(f"  skipped {fname}: {exc}")
    return credits


def main():
    sturm_ok = False
    if "--no-sturm" not in sys.argv:
        try:
            get_sturm()
            train, val, test = read_split("train"), read_split("val"), read_split("test")
            banned = {source_id(r) for r, _ in val + test}
            write_test_labels(test)
            pick_fewshot(train, banned)
            pick_demo(test)
            sturm_ok = True
        except (Exception, KeyboardInterrupt) as exc:
            print(f"\n  STURM step failed or was stopped ({exc!r}). Continuing without it.")
            print("  Demo still works; few-shot examples and the accuracy test need STURM later.")
    credits = get_wikimedia() if "--wikimedia" in sys.argv else []
    print("5/5 attribution")
    (config.DATA_DIR / "ATTRIBUTION.md").write_text(
        "# Data credits\n\n"
        + ("- STURM-FloodDepth Flooded Cars — Notarangelo et al., 2025, CC BY 4.0, doi:10.5281/zenodo.14833532\n" if sturm_ok else "")
        + "\n".join(credits) + "\n\nDemo claims (names, areas, texts) are synthetic.\n",
        encoding="utf-8")
    print("\nAll set. Next: python scripts/make_claims.py  then  python scripts/grade_all.py")
    if sturm_ok:
        print(f"Accuracy later: python scripts/eval_sturm.py --images {IMAGES} --labels {STURM / 'test_labels.csv'} --limit 150 --gemma")


if __name__ == "__main__":
    main()
