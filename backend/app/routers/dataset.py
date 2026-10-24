import os
import re
import shutil
import time
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Dataset, Keyword, Question, User
from ..security import require_admin
from ..services.importer import run_import, read_dataframe

router = APIRouter(prefix="/dataset", tags=["Dataset"])


def ds_out(d: Dataset) -> dict:
    return {
        "id": d.id, "filename": d.filename, "status": d.status, "total_rows": d.total_rows, "processed": d.processed,
        "imported": d.imported, "duplicates": d.duplicates, "error": d.error,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "finished_at": d.finished_at.isoformat() if d.finished_at else None,
    }


@router.post("/upload")
def upload(background: BackgroundTasks, file: UploadFile = File(...), limit: int = Form(0),
           _: User = Depends(require_admin), db: Session = Depends(get_db)):
    name = file.filename or "dataset"
    if not name.lower().endswith((".csv", ".json")):
        raise HTTPException(400, "Only CSV or JSON files are accepted")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    path = os.path.join(str(UPLOAD_DIR), f"{int(time.time())}_{safe}")
    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    try:  # validate structure before accepting the job
        read_dataframe(path)
    except Exception as e:
        os.remove(path)
        raise HTTPException(400, f"Invalid dataset: {e}")
    ds = Dataset(filename=name, status="pending")
    db.add(ds); db.commit(); db.refresh(ds)
    background.add_task(run_import, ds.id, path, limit)
    return ds_out(ds)


@router.get("/status")
def status(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Dataset).order_by(Dataset.id.desc()).all()
    return {"datasets": [ds_out(d) for d in rows], "total_questions": db.query(Question).count()}


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if ds.status == "processing":
        raise HTTPException(400, "Wait for the import to finish first")
    ids = db.query(Question.id).filter(Question.dataset_id == ds.id)
    db.query(Keyword).filter(Keyword.question_id.in_(ids)).delete(synchronize_session=False)
    db.query(Question).filter(Question.dataset_id == ds.id).delete(synchronize_session=False)
    db.delete(ds)
    db.commit()
    return {"message": "Dataset and its questions deleted"}
