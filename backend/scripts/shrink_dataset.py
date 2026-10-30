"""Make a much smaller copy of a big dataset (CSV or JSON), for example to put it on GitHub or to send it by email.

It reads the big file as a stream and keeps every Nth record, so the small file still covers all roles, levels and
categories (taking only the first records would not, if the file is sorted). It can also zip the result.

Run from the backend folder (no need to activate anything special, it only uses the Python standard library for JSON files):

    python scripts/shrink_dataset.py "C:\\path\\to\\hr_interview_questions_dataset.json" --every 10 --zip

--every 10 keeps 1 record in 10 (one tenth of the file). Use --every 5 for about 50,000.
The result is written next to the big file, with "_small" in its name.
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_dataset import iter_json_records  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="the big .json dataset file")
    ap.add_argument("--every", type=int, default=10, help="keep one record in every N (default 10)")
    ap.add_argument("--max", type=int, default=0, help="stop after keeping this many records (0 = no limit)")
    ap.add_argument("--zip", action="store_true", help="also make a .zip of the small file")
    args = ap.parse_args()

    src = Path(args.file)
    if not src.exists():
        sys.exit(f"File not found: {src}")
    if src.suffix.lower() != ".json":
        sys.exit("This script is for .json files. (A CSV can be cut with any spreadsheet program.)")
    if args.every < 1:
        sys.exit("--every must be 1 or more")

    out = src.with_name(src.stem + "_small.json")
    kept = seen = 0
    with open(out, "w", encoding="utf-8") as f:
        f.write("[")
        for rec in iter_json_records(src):
            seen += 1
            if (seen - 1) % args.every:
                continue
            f.write(("," if kept else "") + json.dumps(rec, ensure_ascii=False))
            kept += 1
            if kept % 5000 == 0:
                print(f"{seen} records read, {kept} kept ...")
            if args.max and kept >= args.max:
                break
        f.write("]")
    print(f"Read {seen} records, kept {kept}. Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")

    if args.zip:
        zpath = out.with_suffix(".zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(out, out.name)
        print(f"Zipped to {zpath} ({zpath.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
