from conftest import auth


def test_question_crud_and_filters(client, admin, dataset):
    body = {"question": "How do you document a deployment runbook?", "category": "Communication", "role": "DevOps Engineer",
            "experience": "Senior", "difficulty": "Medium", "source_type": "Open-Ended",
            "ideal_answer": "Keep it short and versioned.", "keywords": ["runbook", "documentation"]}
    r = client.post("/questions", headers=admin, json=body)
    assert r.status_code == 200
    qid = r.json()["id"]
    assert client.post("/questions", headers=admin, json=body).status_code == 400   # duplicate

    found = client.get("/questions", headers=admin, params={"search": "runbook", "category": "Communication",
                                                           "source_type": "open-ended", "experience": "Senior"}).json()
    assert found["total"] == 1 and found["items"][0]["keywords"] == ["runbook", "documentation"]

    r = client.put(f"/questions/{qid}", headers=admin, json={"ideal_answer": "Use a wiki.", "question": "How do you write a deployment runbook?"})
    assert r.status_code == 200 and r.json()["ideal_answer"] == "Use a wiki."
    assert client.get("/questions/semantic", headers=admin, params={"q": "write a deployment runbook"}).json()["items"][0]["id"] == qid

    assert client.delete(f"/questions/{qid}", headers=admin).status_code == 200
    assert client.get("/questions", headers=admin, params={"search": "runbook"}).json()["total"] == 0
    assert client.delete(f"/questions/{qid}", headers=admin).status_code == 404


def test_category_and_role_management(client, admin, dataset):
    cats = {c["name"]: c for c in client.get("/categories", headers=admin).json()}
    assert "Adaptability" in cats and cats["Adaptability"]["questions"] > 0
    assert client.delete(f"/categories/{cats['Adaptability']['id']}", headers=admin).status_code == 400   # still in use

    new = client.post("/categories", headers=admin, json={"name": "Ethics"}).json()
    assert client.post("/categories", headers=admin, json={"name": "ethics"}).status_code == 400
    assert client.put(f"/categories/{new['id']}", headers=admin, json={"name": "Integrity"}).status_code == 200
    assert client.delete(f"/categories/{new['id']}", headers=admin).status_code == 200

    # renaming keeps the questions in sync
    cid = cats["Motivation"]["id"]
    try:
        client.put(f"/categories/{cid}", headers=admin, json={"name": "Drive"})
        assert "Drive" in client.get("/options", headers=admin).json()["categories"]
        assert client.get("/questions", headers=admin, params={"category": "Drive"}).json()["total"] > 0
    finally:
        client.put(f"/categories/{cid}", headers=admin, json={"name": "Motivation"})
    assert "Motivation" in client.get("/options", headers=admin).json()["categories"]

    assert client.get("/roles", headers=admin).status_code == 200
    r = client.post("/roles", headers=admin, json={"name": "Site Reliability Engineer"})
    assert r.status_code == 200 and client.delete(f"/roles/{r.json()['id']}", headers=admin).status_code == 200


def test_user_management(client, admin):
    t = client.post("/register", json={"name": "Managed User", "email": "managed@example.com", "password": "secret1"}).json()
    uid = t["user"]["id"]
    users = client.get("/users", headers=admin, params={"search": "managed"}).json()
    assert users["total"] == 1 and users["items"][0]["email"] == "managed@example.com"

    assert client.put(f"/users/{uid}", headers=admin, json={"name": "Renamed User", "role": "admin"}).json()["role"] == "admin"
    assert client.put(f"/users/{uid}", headers=admin, json={"role": "boss"}).status_code == 400
    client.put(f"/users/{uid}", headers=admin, json={"role": "candidate"})

    assert client.put(f"/users/{uid}", headers=admin, json={"is_active": False}).json()["is_active"] is False
    assert client.post("/login", json={"email": "managed@example.com", "password": "secret1"}).status_code == 403
    assert client.get("/profile", headers=auth(t["access_token"])).status_code == 401       # existing token stops working
    client.put(f"/users/{uid}", headers=admin, json={"is_active": True})
    assert client.post("/login", json={"email": "managed@example.com", "password": "secret1"}).status_code == 200

    me = client.get("/profile", headers=admin).json()["id"]
    assert client.delete(f"/users/{me}", headers=admin).status_code == 400                   # cannot delete yourself
    assert client.put(f"/users/{me}", headers=admin, json={"is_active": False}).status_code == 400
    assert client.delete(f"/users/{uid}", headers=admin).status_code == 200


def test_analytics_and_export(client, admin, candidate, dataset):
    cfg = {"role": "DevOps Engineer", "experience": "Fresher", "difficulty": "Easy", "categories": ["Leadership"], "num_questions": 1}
    iv_id = client.post("/interview/start", headers=candidate, json=cfg).json()["interview"]["id"]
    client.post("/interview/finish", headers=candidate, json={"interview_id": iv_id})

    a = client.get("/analytics", headers=admin).json()
    assert a["total_users"] >= 2 and a["total_questions"] >= 96 and a["total_categories"] >= 4
    assert a["total_interviews"] >= 1 and a["top_roles"] and a["top_categories"]
    assert len(a["daily"]) == 30 and a["monthly"]
    assert {"by_difficulty", "by_experience", "by_category", "by_role"} <= set(a["dataset"])

    r = client.get("/analytics/export", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("interview_id,user,email") and len(lines) >= 2


def test_delete_account_removes_history(client):
    t = client.post("/register", json={"name": "Gone Soon", "email": "gone@example.com", "password": "secret1"}).json()["access_token"]
    assert client.delete("/profile", headers=auth(t)).status_code == 200
    assert client.post("/login", json={"email": "gone@example.com", "password": "secret1"}).status_code == 401
