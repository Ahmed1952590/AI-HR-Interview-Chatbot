"""Create a small sample dataset (CSV) so you can test the system before using the real 250k-row file.
Usage: python scripts/make_sample_dataset.py  ->  writes ../data/sample_dataset.csv
"""
import csv
import itertools
import pathlib

roles = ["DevOps Engineer", "Software Engineer", "Data Analyst", "Project Manager"]
levels = [("Fresher", "Easy"), ("Mid-Level", "Medium"), ("Senior", "Hard")]
templates = {
    "Adaptability": [
        ("Tell me about a time you had to learn something completely new quickly as a {role}.", "Behavioral", ["flexible", "change", "learning"]),
        ("How do you react when priorities change suddenly in your {role} work?", "Open-Ended", ["flexible", "priorities", "communication"]),
    ],
    "Leadership": [
        ("Describe a situation where you led a team through a difficult {role} project.", "Behavioral", ["leadership", "team", "result"]),
        ("How would you motivate a struggling colleague on your {role} team?", "Open-Ended", ["motivation", "support", "feedback"]),
    ],
    "Motivation": [
        ("Why did you choose a career as a {role}?", "Open-Ended", ["passion", "growth", "goals"]),
        ("What keeps you motivated during repetitive {role} tasks?", "Open-Ended", ["discipline", "purpose", "improvement"]),
    ],
    "Teamwork": [
        ("Tell me about a conflict with a teammate while working as a {role} and how you solved it.", "Behavioral", ["conflict", "communication", "compromise"]),
        ("What does good collaboration look like for a {role}?", "Open-Ended", ["collaboration", "trust", "sharing"]),
    ],
}
rows = []
for role, (lvl, diff), (cat, items) in itertools.product(roles, levels, templates.items()):
    for text, stype, kws in items:
        q = text.format(role=role)
        if lvl != "Fresher":
            q = q.replace("Tell me about", f"As a {lvl.lower()} {role}, tell me about", 1) if q.startswith("Tell me about") else q + f" ({lvl} perspective)"
        ideal = f"A strong answer uses a concrete {cat.lower()} example, explains your actions, and ends with a measurable result."
        rows.append([q, cat, role, lvl, diff, stype, ideal, str(kws).replace("'", '"')])

out = pathlib.Path(__file__).resolve().parents[2] / "data" / "sample_dataset.csv"
out.parent.mkdir(exist_ok=True)
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["question", "category", "role", "experience", "difficulty", "source_type", "ideal_answer", "keywords"])
    w.writerows(rows)
print(f"Wrote {len(rows)} rows to {out}")
