"""Import a very large dataset (CSV or JSON, also over 1 GB) straight into the database, without the browser upload.

The file is read as a stream and cut into parts of --part-size records. Each part is imported with the same code as the
admin Dataset page (validate, skip duplicates, embed with Sentence-BERT, add to FAISS), then deleted. Memory use stays small.

Run from the backend folder, with the backend server STOPPED (it keeps its own copy of the FAISS index in memory):

    python scripts/import_dataset.py "C:\\path\\to\\hr_interview_questions_dataset.json" --limit 100000   # enough for all distinct questions
    python scripts/import_dataset.py "C:\\path\\to\\hr_interview_questions_dataset.json"               # everything

Then start the backend again. It is safe to run the script again: records that already exist are skipped.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

READ_BYTES = 8 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024 * 1024


def _iter_objects(f, buf):
    """Yield the JSON objects of an array (or of JSON lines) one by one. `buf` holds the text already read."""
    dec = json.JSONDecoder()
    pos = 0
    eof = False
    while True:
        while True:  # skip whitespace and commas between records
            while pos < len(buf) and buf[pos] in " \t\r\n,":
                pos += 1
            if pos < len(buf) or eof:
                break
            more = f.read(READ_BYTES)
            if more:
                buf, pos = buf[pos:] + more, 0
            else:
                eof = True
        if pos >= len(buf) or buf[pos] == "]":
            return
        while True:
            try:
                obj, end = dec.raw_decode(buf, pos)
                break
            except json.JSONDecodeError:  # the record is cut at the end of what we have read: read more
                if len(buf) - pos > MAX_RECORD_BYTES:
                    raise ValueError("A record is larger than 64 MB, or the JSON file is damaged")
                more = f.read(READ_BYTES)
                if not more:
                    raise ValueError("The JSON file ends in the middle of a record. Is the file complete?")
                buf, pos = buf[pos:] + more, 0
        yield obj
        pos = end


def iter_json_records(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        head = f.read(READ_BYTES)
        s = head.lstrip()
        if not s:
            raise ValueError("The file is empty")
        if s[0] == "[":
            yield from _iter_objects(f, s[1:])
        elif s[0] == "{":
            try:
                obj, end = json.JSONDecoder().raw_decode(s)
            except json.JSONDecodeError:
                obj, end = None, 0
            if obj is None:  # a big object that wraps the list: stream the first list inside it
                i = s.find("[")
                if i < 0:
                    raise ValueError("No list of questions found at the start of the file")
                yield from _iter_objects(f, s[i + 1:])
            elif s[end:].lstrip().startswith("{"):  # JSON lines: one object per line
                yield obj
                yield from _iter_objects(f, s[end:])
            else:  # a small object that wraps the list
                items = next((v for v in obj.values() if isinstance(v, list)), None)
                if items is None:
                    raise ValueError("No list of questions found in the file")
                yield from items
        else:
            raise ValueError("The JSON file must start with [ or {")


def split_file(path, out_dir, part_size, limit=0):
    """Write the records to small part files, one at a time. Yields each part's path after it is written."""
    path = Path(path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    if path.suffix.lower() == ".csv":
        import pandas as pd
        for n, df in enumerate(pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=part_size), 1):
            if limit:
                df = df.head(limit - total)
            if df.empty:
                break
            part = out_dir / f"part_{n:04d}.csv"
            df.to_csv(part, index=False)
            total += len(df)
            yield part, len(df)
            if limit and total >= limit:
                break
        return
    batch, n = [], 0
    for rec in iter_json_records(path):
        batch.append(rec)
        total += 1
        if len(batch) >= part_size or (limit and total >= limit):
            n += 1
            part = out_dir / f"part_{n:04d}.json"
            with open(part, "w", encoding="utf-8") as fp:
                json.dump(batch, fp, ensure_ascii=False)
            yield part, len(batch)
            batch = []
            if limit and total >= limit:
                return
    if batch:
        n += 1
        part = out_dir / f"part_{n:04d}.json"
        with open(part, "w", encoding="utf-8") as fp:
            json.dump(batch, fp, ensure_ascii=False)
        yield part, len(batch)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="the .json or .csv dataset file")
    ap.add_argument("--part-size", type=int, default=20000, help="records per part (default 20000)")
    ap.add_argument("--limit", type=int, default=0, help="import only the first N records (quick test)")
    ap.add_argument("--keep-parts", action="store_true", help="do not delete the part files")
    args = ap.parse_args()

    from app.config import UPLOAD_DIR
    from app.database import Base, engine, SessionLocal
    from app.models import Dataset
    from app.services.importer import run_import

    Base.metadata.create_all(engine)
    src = Path(args.file)
    if not src.exists():
        sys.exit(f"File not found: {src}")
    parts_dir = Path(UPLOAD_DIR) / f"parts_{int(time.time())}"
    started = time.time()
    done = imported = dups = 0
    print(f"Reading {src.name} ({src.stat().st_size / 1e6:,.0f} MB) in parts of {args.part_size} records ...")
    for n, (part, count) in enumerate(split_file(src, parts_dir, args.part_size, args.limit), 1):
        db = SessionLocal()
        ds = Dataset(filename=f"{src.name} (part {n})", status="pending")
        db.add(ds)
        db.commit()
        ds_id = ds.id
        db.close()
        run_import(ds_id, str(part))
        db = SessionLocal()
        ds = db.get(Dataset, ds_id)
        status, err, imp, dup = ds.status, ds.error, ds.imported, ds.duplicates
        db.close()
        if status != "completed":
            sys.exit(f"Part {n} failed: {err}")
        done += count
        imported += imp
        dups += dup
        mins = (time.time() - started) / 60
        print(f"part {n}: {count} records read, {imp} new, {dup} duplicates. Total {done} read, {imported} imported ({mins:.1f} min)")
        if not args.keep_parts:
            part.unlink(missing_ok=True)
    if not args.keep_parts:
        try:
            parts_dir.rmdir()
        except OSError:
            pass
    print(f"Finished: {imported} questions imported, {dups} duplicates skipped, {(time.time() - started) / 60:.1f} minutes.")
    print("Start the backend again and open the admin Dataset page to see the result.")


if __name__ == "__main__":
    main()
