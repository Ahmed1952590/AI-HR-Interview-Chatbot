"""Generate a large SYNTHETIC demo dataset (default 250,000 questions) in the same format as the course dataset.

This is NOT the university dataset. It is built from templates (24 job roles x 10 categories x 3 experience levels
x 3 difficulty levels) so the project can be demonstrated with realistic volume. When you have the official
dataset, import that file instead (admin panel > Dataset).

Usage (from the backend folder):
    python scripts/make_demo_dataset.py                 -> ../data/demo_dataset_250000.csv
    python scripts/make_demo_dataset.py --rows 50000    -> ../data/demo_dataset_50000.csv

The output is deterministic (fixed random seed), so every run produces the same file.
"""
import argparse
import csv
import json
import pathlib
import random

ROLES = {
    "DevOps Engineer": ["deploying a release", "fixing a failed CI/CD pipeline", "handling a production outage", "automating a manual process", "setting up monitoring and alerts", "managing cloud infrastructure costs"],
    "Software Engineer": ["reviewing a teammate's code", "fixing a critical bug", "designing a new feature", "paying down technical debt", "estimating a task", "working with unclear requirements"],
    "Data Analyst": ["cleaning a messy dataset", "building a dashboard", "presenting findings to managers", "answering an urgent data request", "validating a surprising result", "choosing the right metric"],
    "Project Manager": ["planning a project schedule", "managing a tight deadline", "handling scope changes", "reporting status to stakeholders", "coordinating several teams", "recovering a delayed project"],
    "Data Scientist": ["building a prediction model", "explaining a model to non-technical colleagues", "handling biased data", "choosing an evaluation metric", "deploying a model", "working with incomplete data"],
    "Product Manager": ["prioritising a feature backlog", "defining a product roadmap", "gathering customer feedback", "saying no to a stakeholder", "launching a new product", "measuring product success"],
    "QA Engineer": ["writing a test plan", "reporting a hard-to-reproduce bug", "testing under a tight release date", "automating regression tests", "disagreeing with a developer about a defect", "improving test coverage"],
    "UX Designer": ["running a user interview", "presenting a design to stakeholders", "handling critical design feedback", "balancing user needs and business goals", "improving an unusable screen", "working with developers on a handoff"],
    "Cybersecurity Analyst": ["investigating a security alert", "responding to a phishing incident", "running a vulnerability scan", "explaining a risk to management", "hardening a server", "training staff on security"],
    "Cloud Architect": ["designing a scalable architecture", "migrating a system to the cloud", "choosing between cloud services", "reducing cloud costs", "planning disaster recovery", "reviewing a team's design"],
    "Business Analyst": ["gathering requirements", "mapping a business process", "resolving conflicting requirements", "writing a clear specification", "presenting a business case", "validating a solution with users"],
    "HR Specialist": ["screening candidates", "handling an employee complaint", "running an onboarding programme", "explaining a policy change", "supporting a manager with a difficult conversation", "improving employee engagement"],
    "Marketing Specialist": ["planning a campaign", "analysing campaign results", "working with a small budget", "adjusting a message for a new audience", "coordinating with sales", "recovering from a failed campaign"],
    "Sales Representative": ["handling a customer objection", "closing a difficult deal", "missing a quarterly target", "building a client relationship", "qualifying new leads", "working with a demanding customer"],
    "Customer Support Agent": ["helping an angry customer", "handling a high volume of tickets", "escalating a complex issue", "explaining a technical problem simply", "learning a new product quickly", "following up after a complaint"],
    "Accountant": ["closing the month-end books", "finding an error in a report", "meeting a tax deadline", "explaining numbers to non-finance colleagues", "handling a confidential request", "improving a reporting process"],
    "Mechanical Engineer": ["designing a component", "troubleshooting a failed prototype", "meeting a safety standard", "working with a manufacturing team", "reducing the cost of a part", "documenting a design change"],
    "Electrical Engineer": ["debugging a circuit", "testing a new board", "following a safety regulation", "working with suppliers", "meeting a tight design deadline", "documenting a wiring change"],
    "Network Administrator": ["fixing a network outage", "upgrading network equipment", "securing the office network", "handling a slow connection complaint", "documenting a configuration", "planning maintenance downtime"],
    "Database Administrator": ["restoring a database from backup", "tuning a slow query", "planning a schema change", "protecting sensitive data", "handling a failed migration", "monitoring database health"],
    "Machine Learning Engineer": ["moving a model to production", "monitoring model drift", "improving training speed", "working with a data science team", "debugging poor predictions", "choosing between models"],
    "Mobile Developer": ["fixing an app crash", "supporting several devices", "handling an app store rejection", "improving app performance", "working with a designer", "releasing an urgent update"],
    "Technical Writer": ["documenting a complex feature", "interviewing a busy engineer", "updating outdated documentation", "simplifying technical language", "meeting a documentation deadline", "handling reviewer feedback"],
    "Operations Manager": ["improving a slow process", "managing a shift shortage", "reducing operating costs", "handling a supplier delay", "motivating a tired team", "introducing a new procedure"],
}

# (type, stem): B = Behavioral, S = Situational, O = Open-Ended
STEMS = {
    "Adaptability": [
        ("B", "Tell me about a time your plan changed suddenly while {task}."),
        ("B", "Describe a situation where you had to learn something new quickly while {task}."),
        ("B", "Give an example of how you adapted to a new tool or process when {task}."),
        ("S", "What would you do if the requirements changed halfway through {task}?"),
        ("S", "How would you react if your priorities changed completely while {task}?"),
        ("O", "How do you stay flexible when {task} does not go as expected?"),
        ("O", "What helps you adjust quickly to change when {task}?"),
        ("B", "Tell me about a time you worked outside your comfort zone while {task}."),
        ("S", "Imagine your manager asks you to switch approach while {task}. What do you do?"),
        ("O", "Why is adaptability important when {task}?"),
    ],
    "Leadership": [
        ("B", "Describe a time you took the lead when {task}."),
        ("B", "Tell me about a time you guided a less experienced colleague while {task}."),
        ("B", "Give an example of a decision you made for the team when {task}."),
        ("S", "What would you do if nobody took responsibility while {task}?"),
        ("S", "How would you motivate a team that is losing energy while {task}?"),
        ("O", "What does good leadership look like when {task}?"),
        ("O", "How do you delegate work when {task}?"),
        ("B", "Tell me about a time you inspired others during {task}."),
        ("S", "Imagine two team members disagree about how to handle {task}. How do you lead them?"),
        ("O", "How do you give feedback to colleagues when {task}?"),
    ],
    "Motivation": [
        ("O", "What motivates you most when {task}?"),
        ("O", "Why did you choose a career where you spend time {task}?"),
        ("B", "Tell me about a time you stayed motivated during a long task of {task}."),
        ("O", "How do you keep your energy up when {task} becomes repetitive?"),
        ("B", "Describe a moment you felt proud of your work while {task}."),
        ("O", "What goals do you have for improving at {task}?"),
        ("S", "What would you do if you lost interest while {task}?"),
        ("O", "How do you set personal targets when {task}?"),
        ("B", "Tell me about a time you went beyond expectations when {task}."),
        ("O", "What do you enjoy most about {task}?"),
    ],
    "Teamwork": [
        ("B", "Tell me about a time you worked closely with a team while {task}."),
        ("B", "Describe how you helped a teammate who was struggling with {task}."),
        ("B", "Give an example of a team success you contributed to when {task}."),
        ("S", "What would you do if a teammate did not share information while {task}?"),
        ("S", "How would you join a team that is already behind schedule on {task}?"),
        ("O", "What makes collaboration effective when {task}?"),
        ("O", "How do you share credit and responsibility when {task}?"),
        ("B", "Tell me about a time you asked others for help while {task}."),
        ("S", "Imagine a remote teammate is hard to reach while you are {task}. What do you do?"),
        ("O", "How do you build trust in a new team when {task}?"),
    ],
    "Communication": [
        ("B", "Tell me about a time you explained a difficult idea while {task}."),
        ("B", "Describe a misunderstanding you cleared up while {task}."),
        ("S", "How would you tell your manager about a problem you found while {task}?"),
        ("S", "What would you do if a colleague did not understand your message about {task}?"),
        ("O", "How do you keep stakeholders informed when {task}?"),
        ("O", "What makes a clear status update when {task}?"),
        ("B", "Give an example of listening carefully to someone while {task}."),
        ("O", "How do you adjust your style for different audiences when {task}?"),
        ("B", "Tell me about a time you wrote a clear message or report about {task}."),
        ("S", "Imagine you must deliver bad news about {task}. How do you do it?"),
    ],
    "Problem Solving": [
        ("B", "Tell me about a difficult problem you solved while {task}."),
        ("B", "Describe how you found the root cause of an issue when {task}."),
        ("S", "What would you do if your first solution failed while {task}?"),
        ("S", "How would you handle a problem nobody has seen before when {task}?"),
        ("O", "What steps do you follow to solve a problem when {task}?"),
        ("O", "How do you decide between several solutions when {task}?"),
        ("B", "Give an example of a creative solution you used when {task}."),
        ("S", "Imagine you have limited information while {task}. How do you decide?"),
        ("B", "Tell me about a mistake you made while {task} and how you fixed it."),
        ("O", "How do you prevent the same problem from returning when {task}?"),
    ],
    "Conflict Resolution": [
        ("B", "Tell me about a disagreement with a colleague while {task}."),
        ("B", "Describe a time you handled criticism while {task}."),
        ("S", "What would you do if two people asked for opposite things while {task}?"),
        ("S", "How would you respond to a harsh comment during {task}?"),
        ("O", "How do you stay calm in a tense discussion about {task}?"),
        ("O", "What is your approach to resolving conflict when {task}?"),
        ("B", "Give an example of turning a conflict into a better result when {task}."),
        ("S", "Imagine a stakeholder blames you for a delay in {task}. What do you do?"),
        ("B", "Tell me about a time you had to compromise while {task}."),
        ("O", "How do you rebuild a working relationship after an argument about {task}?"),
    ],
    "Time Management": [
        ("B", "Tell me about a time you met a tight deadline while {task}."),
        ("B", "Describe how you handled several tasks at once while {task}."),
        ("S", "What would you do if you could not finish everything while {task}?"),
        ("S", "How would you react if a new urgent task arrived during {task}?"),
        ("O", "How do you prioritise your work when {task}?"),
        ("O", "What tools or habits help you plan your time when {task}?"),
        ("B", "Give an example of a deadline you missed and what you learned when {task}."),
        ("S", "Imagine your estimate for {task} was wrong. How do you tell the team?"),
        ("B", "Tell me about a time you saved time by improving how you worked while {task}."),
        ("O", "How do you avoid burnout when {task} fills your week?"),
    ],
    "Ethics and Integrity": [
        ("B", "Tell me about a time you did the right thing even though it was difficult while {task}."),
        ("B", "Describe a time you admitted a mistake while {task}."),
        ("S", "What would you do if a colleague asked you to cut a corner while {task}?"),
        ("S", "How would you handle confidential information you saw while {task}?"),
        ("O", "What does professional integrity mean when {task}?"),
        ("O", "How do you make fair decisions when {task}?"),
        ("B", "Give an example of speaking up about a problem while {task}."),
        ("S", "Imagine your manager asks you to hide a problem found while {task}. What do you do?"),
        ("B", "Tell me about a time you protected the trust of a customer or colleague when {task}."),
        ("O", "How do you follow company rules under pressure while {task}?"),
    ],
    "Customer Focus": [
        ("B", "Tell me about a time you went the extra mile for a customer while {task}."),
        ("B", "Describe how you handled difficult customer feedback while {task}."),
        ("S", "What would you do if a customer's request conflicted with policy while {task}?"),
        ("S", "How would you respond to an unhappy customer during {task}?"),
        ("O", "How do you learn what customers really need when {task}?"),
        ("O", "What does great service look like when {task}?"),
        ("B", "Give an example of using customer feedback to improve how you worked while {task}."),
        ("S", "Imagine a customer asks for something impossible while you are {task}. What do you do?"),
        ("B", "Tell me about a time you turned an unhappy customer around while {task}."),
        ("O", "How do you balance customer needs and business goals when {task}?"),
    ],
}

KEYWORDS = {
    "Adaptability": ["flexible", "change", "learning", "open-minded", "resilience", "quick learner", "new tools", "feedback"],
    "Leadership": ["leadership", "delegation", "vision", "accountability", "coaching", "decision making", "inspiring", "ownership"],
    "Motivation": ["passion", "growth", "goals", "drive", "purpose", "curiosity", "commitment", "achievement"],
    "Teamwork": ["collaboration", "trust", "support", "shared goals", "respect", "listening", "contribution", "cooperation"],
    "Communication": ["clarity", "listening", "audience", "feedback", "transparency", "empathy", "summary", "follow-up"],
    "Problem Solving": ["root cause", "analysis", "options", "prioritisation", "creativity", "testing", "evidence", "prevention"],
    "Conflict Resolution": ["empathy", "compromise", "calm", "listening", "mediation", "respect", "common ground", "feedback"],
    "Time Management": ["prioritisation", "planning", "deadlines", "organisation", "focus", "delegation", "estimation", "balance"],
    "Ethics and Integrity": ["honesty", "transparency", "responsibility", "confidentiality", "fairness", "trust", "courage", "policy"],
    "Customer Focus": ["empathy", "service", "needs", "feedback", "follow-up", "trust", "solution", "satisfaction"],
}

EXPERIENCE = ["Fresher", "Mid-Level", "Senior"]
DIFFICULTY = ["Easy", "Medium", "Hard"]
TYPE_NAME = {"B": "Behavioral", "S": "Situational", "O": "Open-Ended"}

PREFIXES = {
    "Fresher": ([""], ["Thinking of your studies or first projects, ", "Even in an internship or class project, "]),
    "Mid-Level": ([""], ["In your professional experience, ", "From your years in the role, "]),
    "Senior": ([""], ["As a senior {role}, ", "Drawing on your leadership experience, "]),
}
SUFFIXES = {
    "Easy": ["", "", " Please give a short example."],
    "Medium": ["", "", " Explain what you did and why."],
    "Hard": ["", "", " Include the trade-offs you considered and the measurable result."],
}
LEVEL_TIP = {
    "Fresher": "Use an example from your studies, an internship or a first project if you do not have work experience yet.",
    "Mid-Level": "Show how you handled it independently and what you improved afterwards.",
    "Senior": "Show how you guided others, managed risk and measured the impact.",
}
IDEAL = {
    "B": "Use the STAR method: describe the situation while {task}, your task, the actions you took and the result. A strong answer for a {role} shows {k1}, {k2} and {k3}, and ends with a measurable outcome and what you learned. {tip}",
    "S": "Explain your thinking step by step: clarify the situation, name your options while {task}, choose one and say why. A strong answer for a {role} shows {k1}, {k2} and {k3}, and says how you would check the result. {tip}",
    "O": "Answer directly, then support your view with one real example from {task}. A strong answer for a {role} shows {k1}, {k2} and {k3}, and connects the idea to the team's goals. {tip}",
}


def build_question(rng, role, category, experience, difficulty):
    qtype, stem = rng.choice(STEMS[category])
    task = rng.choice(ROLES[role])
    prefix = rng.choice(PREFIXES[experience][rng.choice([0, 1, 1])]) if rng.random() < 0.55 else ""
    text = stem.format(task=task)
    if prefix:
        text = prefix.format(role=role) + text[0].lower() + text[1:]
    text += rng.choice(SUFFIXES[difficulty])
    return qtype, task, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=250000)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rng = random.Random(2026)

    cells = [(r, c, e, d) for r in ROLES for c in STEMS for e in EXPERIENCE for d in DIFFICULTY]
    base, extra = divmod(a.rows, len(cells))
    bonus = set(rng.sample(range(len(cells)), extra))

    used = set()
    rows = []
    for i, (role, cat, exp, diff) in enumerate(cells):
        want = base + (1 if i in bonus else 0)
        made, attempts = 0, 0
        while made < want:
            attempts += 1
            if attempts > 20000:
                raise SystemExit(f"Could not create enough unique questions for {role} / {cat} / {exp} / {diff}")
            qtype, task, text = build_question(rng, role, cat, exp, diff)
            if text in used:
                continue
            used.add(text)
            k = rng.sample(KEYWORDS[cat], 3)
            ideal = IDEAL[qtype].format(task=task, role=role, k1=k[0], k2=k[1], k3=k[2], tip=LEVEL_TIP[exp])
            rows.append([text, cat, role, exp, diff, TYPE_NAME[qtype], ideal, json.dumps(k)])
            made += 1
    rng.shuffle(rows)

    out = pathlib.Path(a.out) if a.out else pathlib.Path(__file__).resolve().parents[2] / "data" / f"demo_dataset_{a.rows}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question", "category", "role", "experience", "difficulty", "source_type", "ideal_answer", "keywords"])
        w.writerows(rows)
    print(f"Wrote {len(rows):,} unique synthetic questions to {out}")
    print(f"{len(ROLES)} roles, {len(STEMS)} categories, {len(EXPERIENCE)} experience levels, {len(DIFFICULTY)} difficulty levels")


if __name__ == "__main__":
    main()
