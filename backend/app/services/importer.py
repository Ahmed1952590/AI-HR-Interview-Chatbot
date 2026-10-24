"""Dataset import: validate -> deduplicate -> store -> embed -> index. Runs in a background task."""
import hashlib
import json
import re
import threading
import pandas as pd
from ..database import SessionLocal
from ..models import Dataset, Question, Keyword, Category, JobRole, utcnow
from .nlp import store

ALIASES = {
    "question": ["question", "questions", "text", "question_text"],
    "category": ["category", "question_category"],
    "role": ["role", "job_role", "jobrole", "job"],
    "experience": ["experience", "experience_level", "level"],
    "difficulty": ["difficulty", "difficulty_level"],
    "source_type": ["source_type", "sourcetype", "question_type", "type"],
    "ideal_answer": ["ideal_answer", "idealanswer", "answer", "recommended_answer"],
    "keywords": ["keywords", "keyword", "tags"],
}
REQUIRED = ["question", "category", "role", "experience", "difficulty"]
CHUNK = 2000
_import_lock = threading.Lock()


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()[:1000]


def dedupe_key(text, role="", experience="", difficulty="", category="") -> str:
    """Identifies one dataset record. Two rows are duplicates only when the question text AND its role, experience,
    difficulty and category all match, so the same generic question can still exist for different roles or levels."""
    raw = "|".join([norm_text(text)] + [str(v).strip().lower() for v in (role, experience, difficulty, category)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def parse_keywords(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        items = v
    else:
        s = str(v).strip()
        if not s or s.lower() == "nan":
            return []
        if s.startswith("["):
            try:
                items = json.loads(s)
            except Exception:
                items = re.split(r"[;,|]", s.strip("[]"))
        else:
            items = re.split(r"[;,|]", s)
    out = []
    for k in items:
        k = str(k).strip().strip("'\"")
        if k and k.lower() not in [o.lower() for o in out]:
            out.append(k[:120])
    return out[:12]


def read_dataframe(path: str) -> pd.DataFrame:
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = next((v for v in data.values() if isinstance(v, list)), [data])
            df = pd.DataFrame(data)
        except json.JSONDecodeError:  # JSON lines
            df = pd.DataFrame([json.loads(l) for l in text.splitlines() if l.strip()])
    elif path.lower().endswith(".csv"):
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")
    else:
        raise ValueError("Only .csv and .json files are supported")
    lower = {c: str(c).strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=lower)
    mapping = {}
    for target, names in ALIASES.items():
        for n in names:
            if n in df.columns:
                mapping[n] = target
                break
    df = df.rename(columns=mapping)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}. Found: {', '.join(map(str, df.columns))}")
    for c in ALIASES:
        if c not in df.columns:
            df[c] = ""
    return df


def run_import(dataset_id: int, path: str, limit: int = 0):
    db = SessionLocal()
    ds = db.get(Dataset, dataset_id)
    try:
        with _import_lock:  # one import at a time
            ds.status = "processing"
            db.commit()
            df = read_dataframe(path)
            if limit and limit > 0:
                df = df.head(limit)
            ds.total_rows = len(df)
            db.commit()

            existing = {n for (n,) in db.query(Question.norm)}
            cats = {n for (n,) in db.query(Category.name)}
            roles = {n for (n,) in db.query(JobRole.name)}
            chunks_done = 0

            for start in range(0, len(df), CHUNK):
                part = df.iloc[start:start + CHUNK]
                objs = []
                for rec in part.to_dict("records"):
                    text = str(rec["question"]).strip()
                    n = dedupe_key(text, rec["role"], rec["experience"], rec["difficulty"], rec["category"])
                    if not text or n in existing:
                        ds.duplicates += 1
                        continue
                    existing.add(n)
                    q = Question(
                        question=text, norm=n,
                        category=str(rec["category"]).strip(), role=str(rec["role"]).strip(),
                        experience=str(rec["experience"]).strip(), difficulty=str(rec["difficulty"]).strip().title(),
                        source_type=str(rec["source_type"]).strip(), ideal_answer=str(rec["ideal_answer"]).strip(),
                        dataset_id=ds.id,
                        keywords=[Keyword(keyword=k) for k in parse_keywords(rec["keywords"])],
                    )
                    objs.append(q)
                    if q.category and q.category not in cats:
                        cats.add(q.category); db.add(Category(name=q.category))
                    if q.role and q.role not in roles:
                        roles.add(q.role); db.add(JobRole(name=q.role))
                if objs:
                    vecs = store.embed([o.question for o in objs])
                    first = store.add(vecs)
                    for i, o in enumerate(objs):
                        o.vec_idx = first + i
                    db.add_all(objs)
                    ds.imported += len(objs)
                ds.processed = min(start + CHUNK, len(df))
                db.commit()
                chunks_done += 1
                if chunks_done % 20 == 0:
                    store.save()
            store.save()
            ds.status = "completed"
            ds.finished_at = utcnow()
            db.commit()
    except Exception as e:  # noqa
        db.rollback()
        ds = db.get(Dataset, dataset_id)
        ds.status = "failed"
        ds.error = str(e)[:1000]
        ds.finished_at = utcnow()
        db.commit()
    finally:
        db.close()
