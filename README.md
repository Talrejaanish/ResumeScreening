# Resume Screening Automation

React + FastAPI application for job posting, applicant profiles, PDF resume extraction and JD-based screening.

## Run locally

### Backend
```powershell
cd backend
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

MongoDB must be running at the URI in `backend/.env`. The built-in administrator is `Admin@gmail.com` / `120405` (its password is stored as a hash on startup, not in MongoDB plaintext).

## Optional Gemini skill matching

Set `GEMINI_API_KEY` in `backend/.env` to enable Gemini structured scoring. You can optionally set `GEMINI_MODEL` (default: `gemini-2.5-flash`). Without a key, the API uses local PDF parsing and deterministic keyword scoring.
