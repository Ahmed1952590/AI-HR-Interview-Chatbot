import json

from conftest import upload, SAMPLE


def test_import_sample_dataset(client, admin, dataset):
    ds = dataset["datasets"][0]
    assert ds["imported"] == 96 and ds["duplicates"] == 0
    assert dataset["total_questions"] >= 96
    opts = client.get("/options", headers=admin).json()
    assert "DevOps Engineer" in opts["roles"] and "Leadership" in opts["categories"]
    assert set(opts["difficulties"]) >= {"Easy", "Medium", "Hard"}


def test_duplicates_are_ignored(client, admin, dataset):
    before = client.get("/dataset/status", headers=admin).json()["total_questions"]
    assert upload(client, admin, SAMPLE).status_code == 200
    st = client.get("/dataset/status", headers=admin).json()
    newest = st["datasets"][0]
    assert newest["status"] == "completed" and newest["imported"] == 0 and newest["duplicates"] == 96
    assert st["total_questions"] == before
    assert client.delete(f"/dataset/{newest['id']}", headers=admin).status_code == 200


def test_invalid_files_are_rejected(client, admin, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")
    r = upload(client, admin, bad)
    assert r.status_code == 400 and "Missing required columns" in r.json()["detail"]
    txt = tmp_path / "data.txt"
    txt.write_text("hello")
    assert upload(client, admin, txt).status_code == 400


def test_json_import_with_keywords_and_delete(client, admin, dataset, tmp_path):
    records = [
        {"question": "Describe how you stay calm under pressure as a Cloud Architect.", "category": "Resilience",
         "role": "Cloud Architect", "experience": "Senior", "difficulty": "hard", "source_type": "Behavioral",
         "ideal_answer": "Stay structured.", "keywords": ["calm", "prioritise"]},
        {"question": "Why do you want to be a Cloud Architect?", "category": "Motivation", "role": "Cloud Architect",
         "experience": "Senior", "difficulty": "Easy", "source_type": "Open-Ended", "ideal_answer": "Show passion.", "keywords": []},
    ]
    f = tmp_path / "extra.json"
    f.write_text(json.dumps(records))
    before = client.get("/dataset/status", headers=admin).json()["total_questions"]
    assert upload(client, admin, f).status_code == 200
    st = client.get("/dataset/status", headers=admin).json()
    d = st["datasets"][0]
    assert d["status"] == "completed" and d["imported"] == 2
    assert st["total_questions"] == before + 2

    r = client.get("/questions", headers=admin, params={"role": "Cloud Architect", "difficulty": "Hard"}).json()
    assert r["total"] == 1 and r["items"][0]["keywords"] == ["calm", "prioritise"]  # difficulty normalised to Title case

    assert client.delete(f"/dataset/{d['id']}", headers=admin).status_code == 200
    assert client.get("/dataset/status", headers=admin).json()["total_questions"] == before


def test_vectors_are_stored_in_faiss(client, admin, dataset):
    from app.database import SessionLocal
    from app.models import Question
    from app.services.nlp import store
    db = SessionLocal()
    try:
        assert store.total >= db.query(Question).filter(Question.vec_idx >= 0).count() > 0
        q = db.query(Question).filter(Question.vec_idx >= 0).first()
        vec = store.vectors([q.vec_idx])[0]
        assert abs(float((vec @ store.embed([q.question])[0])) - 1.0) < 1e-4  # stored vector == embedding of the question
    finally:
        db.close()


def test_semantic_search_endpoint(client, admin, dataset):
    r = client.get("/questions/semantic", headers=admin, params={"q": "lead a team through a difficult project", "limit": 5}).json()
    assert 0 < len(r["items"]) <= 5
    scores = [i["score"] for i in r["items"]]
    assert scores == sorted(scores, reverse=True)
    top3 = " ".join(i["question"].lower() for i in r["items"][:3])
    assert "led a team" in top3 or "lead" in top3


def test_retrieval_respects_filters(dataset):
    from app.database import SessionLocal
    from app.models import Interview
    from app.services.retrieval import select_question
    db = SessionLocal()
    try:
        iv = Interview(user_id=1, role="Data Analyst", experience="Mid-Level", difficulty="Medium",
                       categories=["Teamwork"], num_questions=3)
        db.add(iv); db.commit(); db.refresh(iv)
        q = select_question(db, iv)
        assert (q.role, q.experience, q.difficulty, q.category) == ("Data Analyst", "Mid-Level", "Medium", "Teamwork")
    finally:
        db.close()


def test_same_text_for_different_roles_is_kept(client, admin, dataset, tmp_path):
    """A duplicate is the same question AND the same role, level, difficulty and category."""
    base = {"question": "Tell me about a time you led a project under pressure.", "category": "Leadership",
            "experience": "Senior", "difficulty": "Hard", "source_type": "Behavioral", "ideal_answer": "Stay calm.", "keywords": []}
    records = [dict(base, role="Role Alpha"), dict(base, role="Role Beta"), dict(base, role="Role Alpha")]
    f = tmp_path / "same_text.json"
    f.write_text(json.dumps(records))
    assert upload(client, admin, f).status_code == 200
    d = client.get("/dataset/status", headers=admin).json()["datasets"][0]
    assert d["status"] == "completed" and d["imported"] == 2 and d["duplicates"] == 1
    assert client.delete(f"/dataset/{d['id']}", headers=admin).status_code == 200
