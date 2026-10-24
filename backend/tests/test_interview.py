from conftest import auth

CFG = {"role": "DevOps Engineer", "experience": "Fresher", "difficulty": "Easy",
       "categories": ["Leadership", "Teamwork"], "num_questions": 4}


def next_q(client, h, iv_id):
    return client.get("/interview/question", headers=h, params={"interview_id": iv_id}).json()


def test_full_interview_flow(client, candidate, dataset):
    r = client.post("/interview/start", headers=candidate, json=CFG)
    assert r.status_code == 200
    body = r.json()
    assert body["greeting"] and body["rules"]
    iv_id = body["interview"]["id"]

    seen = []
    for step in range(CFG["num_questions"]):
        q = next_q(client, candidate, iv_id)
        assert q["done"] is False and q["total"] == 4
        assert q["question"] not in seen                       # FR-3: no duplicates within one interview
        seen.append(q["question"])
        item = q["interview_question_id"]
        # the same question is returned until it is answered or skipped
        assert next_q(client, candidate, iv_id)["interview_question_id"] == item
        if step == 1:
            assert client.post("/interview/skip", headers=candidate, json={"interview_id": iv_id, "interview_question_id": item}).status_code == 200
        else:
            r = client.post("/interview/answer", headers=candidate,
                            json={"interview_id": iv_id, "interview_question_id": item, "answer": f"My answer {step}"})
            assert r.status_code == 200
        if step == 0:
            ideal = client.get(f"/interview/ideal/{item}", headers=candidate).json()
            assert ideal["ideal_answer"] and ideal["keywords"] and ideal["tips"] and ideal["category"] and ideal["difficulty"]

    assert next_q(client, candidate, iv_id)["done"] is True

    s = client.post("/interview/finish", headers=candidate, json={"interview_id": iv_id}).json()
    assert s["finished"] is True and s["asked"] == 4 and s["answered"] == 3 and s["skipped"] == 1 and s["viewed_ideal"] == 1
    assert s["role"] == "DevOps Engineer" and s["difficulty"] == "Easy" and s["finished_at"]

    detail = client.get(f"/interview/{iv_id}", headers=candidate).json()
    assert len(detail["items"]) == 4
    assert [i["skipped"] for i in detail["items"]] == [False, True, False, False]
    assert detail["items"][0]["viewed_ideal"] is True and detail["items"][0]["answer"] == "My answer 0"

    hist = client.get("/interview/history", headers=candidate).json()
    assert any(h["id"] == iv_id for h in hist)
    assert client.get("/interview/stats", headers=candidate).json()["completed"] >= 1


def test_history_search_and_filters(client, candidate, dataset):
    assert client.get("/interview/history", headers=candidate, params={"role": "Nonexistent"}).json() == []
    assert client.get("/interview/history", headers=candidate, params={"role": "devops engineer"}).json()
    assert client.get("/interview/history", headers=candidate, params={"search": "My answer 2"}).json()
    assert client.get("/interview/history", headers=candidate, params={"date_from": "2100-01-01"}).json() == []
    assert client.get("/interview/history", headers=candidate, params={"date_from": "garbage"}).status_code == 400


def test_unknown_role_is_rejected(client, candidate, dataset):
    bad = dict(CFG, role="Astronaut")
    assert client.post("/interview/start", headers=candidate, json=bad).status_code == 400


def test_interviews_are_private(client, candidate, dataset):
    iv_id = client.post("/interview/start", headers=candidate, json=CFG).json()["interview"]["id"]
    other = client.post("/register", json={"name": "Other Person", "email": "other@example.com", "password": "secret1"}).json()["access_token"]
    assert client.get(f"/interview/{iv_id}", headers=auth(other)).status_code == 404
    assert client.get("/interview/question", headers=auth(other), params={"interview_id": iv_id}).status_code == 404


def test_unfinished_questions_count_as_skipped(client, candidate, dataset):
    iv_id = client.post("/interview/start", headers=candidate, json=dict(CFG, num_questions=2)).json()["interview"]["id"]
    next_q(client, candidate, iv_id)  # asked but never answered
    s = client.post("/interview/finish", headers=candidate, json={"interview_id": iv_id}).json()
    assert s["asked"] == 1 and s["skipped"] == 1 and s["answered"] == 0


def test_filters_relax_when_pool_is_small(client, candidate, dataset):
    # only 4 matching questions exist; asking for 8 must still work using relaxed filters, without repeats
    iv_id = client.post("/interview/start", headers=candidate, json=dict(CFG, num_questions=8)).json()["interview"]["id"]
    seen = []
    for _ in range(8):
        q = next_q(client, candidate, iv_id)
        assert q["done"] is False
        assert q["question"] not in seen
        seen.append(q["question"])
        client.post("/interview/answer", headers=candidate,
                    json={"interview_id": iv_id, "interview_question_id": q["interview_question_id"], "answer": "ok"})
    assert next_q(client, candidate, iv_id)["done"] is True
