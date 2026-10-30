# AI HR Interview Chatbot

A web app for practising HR job interviews. You pick a job role, your experience level, a difficulty and some categories, and
the chatbot asks you questions one at a time. The next question is not random: every question is turned into a vector with
Sentence-BERT, the vectors are kept in a FAISS index, and the app picks the unseen question whose meaning is closest to your
setup and to your last answer. No external AI service (LLM API) is used. This is my project for the WEX428 course at Ostim Technical University.

Built with React + TypeScript (Vite) for the frontend, FastAPI for the backend, SQLite (or PostgreSQL), JWT and BCrypt for login,
sentence-transformers (`all-MiniLM-L6-v2`) and FAISS for the language part, and Docker with Nginx for deployment.

## Running it on your computer

You need Python 3.11 or 3.12 and Node.js 18 or newer. The first start downloads the Sentence-BERT model (about 90 MB), so you
need internet once.

Backend, in the first terminal:
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows. On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
The API documentation is at http://localhost:8000/docs.

Frontend, in a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Then open http://localhost:5173.

## First login and loading the questions

The administrator account is `admin@example.com` with the password `Admin123!`. You can change it with the `ADMIN_EMAIL` and
`ADMIN_PASSWORD` environment variables.

Nothing works until some questions are loaded. There are two ways:

1. **Small test.** In the admin panel open **Dataset** and upload `data/sample_dataset.csv` (96 questions). It takes seconds.
2. **The course dataset.** It is in the `data` folder as a zip file (`data/*.zip`). Unzip it so you have the `.json` file. The
   file is about 1.2 GB and holds 2.5 million rows, but only 8,640 of them are different (40 question texts across 8 roles,
   9 experience levels, 3 difficulties and 8 categories). The importer skips the repeats, so the app ends up with about 8,640
   questions. Do not upload the file in the browser. Stop the backend and run this in the `backend` folder with the venv
   active (use your real path to the unzipped file):
   ```
   python scripts/import_dataset.py "C:\path\to\hr_interview_questions_dataset.json" --limit 100000
   ```
   `--limit 100000` reads the first 100,000 rows, which already contains nearly every different question and takes a few
   minutes. Without `--limit` the whole file is read (much longer, same result). The script reads the file piece by piece
   (20,000 records at a time, change it with `--part-size`), skips duplicates and can be run again safely. Start the backend
   again when it finishes, and the questions show on the admin **Questions** page.

   `scripts/shrink_dataset.py` can make a smaller copy of a big file (one record in N), but for this dataset it is not needed.

3. **Generated demo set (250,000 questions).** `data/demo_dataset_250000.zip` holds `demo_dataset_250000.csv`, 250,000 unique
   questions that I generated with `backend/scripts/make_demo_dataset.py`. It is synthetic, it is NOT the university dataset, and it
   is used to show the app working at that size. Unzip it and run
   `python scripts/import_dataset.py "C:\path\to\demo_dataset_250000.csv"` in the `backend` folder (backend stopped).

After that, log out, create a candidate account with **Create an account**, and start an interview.

## Running with Docker

```bash
docker compose up --build
```
The app is then at http://localhost:3000. Everything that must survive a restart (database, FAISS index, model cache) is
stored in the `data` folder. For anything more than a demo, set `SECRET_KEY`, `ADMIN_EMAIL` and `ADMIN_PASSWORD` in a `.env` file.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```
The tests use a very small fake embedder, so they need no internet and no model download. They cover registration and login,
password reset, access rules for admins and candidates, importing CSV and JSON with duplicate detection, the full interview
(answer, skip, ideal answer, finish, history, no repeated questions), question and user management, and the reports.
GitHub Actions runs them on every push, together with the frontend type check and build (`.github/workflows/ci.yml`).

## How the question is chosen

1. **Import** (`services/importer.py`). The file is checked, duplicates are skipped, keywords are saved, and each question is
   embedded with Sentence-BERT and added to the FAISS index. Each question remembers its position in the index (`vec_idx`).
2. **Retrieval** (`services/retrieval.py`). The database first narrows the questions down to the chosen role, level, difficulty
   and category. Then the setup and the candidate's last answer are embedded, and the candidates are ranked by cosine similarity.
3. **Variety.** The score is lowered for questions that look like ones already asked (Maximal Marginal Relevance, weight 0.7),
   and near-copies above 0.92 similarity are dropped. With several categories chosen, the interview goes through them in turn.
4. **When few questions match**, the filters are loosened step by step (category, then difficulty, then level). The job role is never loosened.

To see the search at work, run `python scripts/semantic_demo.py --text "how do you handle sudden change at work" --role "DevOps Engineer"`
in the `backend` folder, or tick **Search by meaning** on the admin Questions page.

## Folders

```
backend/app/        main.py, config.py, database.py, models.py, security.py
  routers/          auth, users, interview, questions, dataset, meta, analytics
  services/         nlp.py (Sentence-BERT and FAISS), retrieval.py, importer.py
backend/scripts/    import_dataset.py, shrink_dataset.py, make_sample_dataset.py, make_demo_dataset.py, semantic_demo.py
backend/tests/      the pytest tests
frontend/src/       App.tsx, api.ts, auth.tsx, pages/ (Auth, Candidate, Interview, Admin)
.github/workflows/  ci.yml
docker-compose.yml
```

## Known limits

- Forgot password has no mail server. The reset token is shown on the screen instead (demo mode).
- Logging out blocks the token only until the backend restarts.
- The interview tips are rule-based (STAR method, category hints, keywords) because the dataset has no tips field.
- The Sentence-BERT model is used as it is, without extra training.
