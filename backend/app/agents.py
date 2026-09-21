import json, re
from pypdf import PdfReader
from .config import GEMINI_API_KEY, GEMINI_MODEL

def _gemini_json(prompt: str, schema: dict) -> dict | None:
    """Return Gemini structured output, or None so deterministic scoring can continue."""
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": schema},
        )
        return json.loads(response.text)
    except Exception:
        # Invalid keys, unavailable models, or malformed output must never block applying.
        return None

def extract_resume(pdf_path: str) -> dict:
    """PDF-to-JSON agent. CrewAI can enrich this; baseline extraction always works."""
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    phone = re.search(r"(?:\+?\d[\d\s-]{8,}\d)", text)
    skills = re.findall(r"(?i)(?:python|java|javascript|react|fastapi|mongodb|sql|aws|docker|kubernetes|node(?:\.js)?)", text)
    result = {"raw_text": text, "name": lines[0] if lines else "Unknown", "email": email.group(0) if email else "", "phone": phone.group(0) if phone else "", "skills": sorted(set(s.lower() for s in skills))}
    candidate = _gemini_json(
        f"Extract factual applicant information from this resume. Do not infer missing facts. Resume text:\n{text[:12000]}",
        {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "skills": {"type": "array", "items": {"type": "string"}}, "education": {"type": "string"}, "experience_years": {"type": "number"}, "summary": {"type": "string"}}, "required": ["name", "email", "phone", "skills", "education", "experience_years", "summary"]},
    )
    if candidate:
        result.update(candidate)
    return result

def screen_resume(resume: dict, job: dict) -> dict:
    """Screening agent: explainable JD skill-match score, 0–100."""
    jd = (job.get("description", "") + " " + " ".join(job.get("required_skills", []))).lower()
    resume_text = (resume.get("raw_text", "") + " " + " ".join(resume.get("skills", []))).lower()
    required = [s.lower().strip() for s in job.get("required_skills", []) if s.strip()]
    if not required:
        required = sorted(set(re.findall(r"\b(?:python|java|javascript|react|fastapi|mongodb|sql|aws|docker|kubernetes|node(?:\.js)?)\b", jd)))
    matched = [skill for skill in required if skill in resume_text]
    missing = [skill for skill in required if skill not in resume_text]
    fallback = {"score": round((len(matched) / len(required) * 100) if required else 0), "matched_skills": matched, "missing_skills": missing, "summary": f"Matched {len(matched)} of {len(required)} required skills."}
    candidate = _gemini_json(
        "Evaluate this resume only against the stated role requirements. Score 0–100 based only on evidence in the resume. "
        "Do not infer skills, seniority, identity, or other unstated attributes. Explain the result concisely.\n"
        f"JOB DESCRIPTION:\n{job.get('description', '')}\nREQUIRED SKILLS: {required}\n"
        f"RESUME JSON:\n{json.dumps(resume)[:12000]}",
        {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "matched_skills": {"type": "array", "items": {"type": "string"}}, "missing_skills": {"type": "array", "items": {"type": "string"}}, "summary": {"type": "string"}}, "required": ["score", "matched_skills", "missing_skills", "summary"]},
    )
    if candidate and isinstance(candidate.get("score"), (int, float)):
        candidate["score"] = max(0, min(100, round(candidate["score"])))
        candidate.setdefault("matched_skills", matched)
        candidate.setdefault("missing_skills", missing)
        candidate.setdefault("summary", fallback["summary"])
        return candidate
    return fallback
