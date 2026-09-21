from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from bson import ObjectId
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from .config import ADMIN_EMAIL, ADMIN_MPIN, FRONTEND_ORIGIN
from .database import db, setup_indexes
from .models import RegisterInput, LoginInput, ProfileInput, JobInput
from .auth import hash_mpin, verify_mpin, create_token, current_user, admin_only
from .agents import extract_resume, screen_resume

app = FastAPI(title="Resume Screening API")
# Vite may use either localhost or 127.0.0.1, and moves to 5174 when its
# default port is occupied. Permit these local development origins as well.
LOCAL_FRONTEND_ORIGINS = [
    FRONTEND_ORIGIN,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(LOCAL_FRONTEND_ORIGINS)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOADS = Path("uploads"); UPLOADS.mkdir(exist_ok=True)

def clean(doc):
    doc["id"] = str(doc.pop("_id")); return doc

@app.on_event("startup")
async def startup(): await setup_indexes()

@app.post("/auth/register")
async def register(data: RegisterInput):
    if data.email.lower() == ADMIN_EMAIL.lower(): raise HTTPException(400, "This email is reserved")
    user = {"name": data.name, "email": data.email.lower(), "mpin_hash": hash_mpin(data.mpin), "role": "applicant", "profile": {}, "created_at": datetime.now(timezone.utc)}
    try: result = await db.users.insert_one(user)
    except Exception: raise HTTPException(409, "An account with this email already exists")
    user["_id"] = result.inserted_id
    return {"token": create_token(user), "user": {"id": str(result.inserted_id), "name": data.name, "email": user["email"], "role": "applicant"}}

@app.post("/auth/login")
async def login(data: LoginInput):
    if data.email.lower() == ADMIN_EMAIL.lower() and data.mpin == ADMIN_MPIN:
        user = {"_id": "built-in-admin", "name": "Administrator", "email": ADMIN_EMAIL, "role": "admin"}
    else:
        user = await db.users.find_one({"email": data.email.lower()})
        if not user or not verify_mpin(data.mpin, user["mpin_hash"]): raise HTTPException(401, "Incorrect email or MPIN")
    return {"token": create_token(user), "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"], "role": user["role"]}}

@app.get("/jobs")
async def jobs(): return [clean(x) async for x in db.jobs.find().sort("created_at", -1)]

@app.post("/jobs")
async def create_job(data: JobInput, _: dict = Depends(admin_only)):
    job = data.model_dump() | {"created_at": datetime.now(timezone.utc)}
    result = await db.jobs.insert_one(job); job["_id"] = result.inserted_id
    return clean(job)

@app.get("/profile")
async def get_profile(user: dict = Depends(current_user)):
    if user["role"] == "admin": return {"name": "Administrator", "role": "admin", "profile": {}}
    doc = await db.users.find_one({"_id": ObjectId(user["sub"])})
    return {"name": doc["name"], "email": doc["email"], "role": doc["role"], "profile": doc.get("profile", {})}

@app.put("/profile")
async def update_profile(data: ProfileInput, user: dict = Depends(current_user)):
    if user["role"] != "applicant": raise HTTPException(403, "Applicants only")
    await db.users.update_one({"_id": ObjectId(user["sub"])}, {"$set": {"profile": data.model_dump()}})
    return {"ok": True}

@app.post("/jobs/{job_id}/apply")
async def apply(job_id: str, resume: UploadFile = File(...), user: dict = Depends(current_user)):
    if user["role"] != "applicant": raise HTTPException(403, "Applicants only")
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job: raise HTTPException(404, "Job not found")
    if not resume.filename.lower().endswith(".pdf"): raise HTTPException(400, "Please upload a PDF resume")
    destination = UPLOADS / f"{uuid4()}.pdf"; destination.write_bytes(await resume.read())
    resume_json = extract_resume(str(destination)); screening = screen_resume(resume_json, job)
    application = {"job_id": job_id, "applicant_id": user["sub"], "resume_file": str(destination), "resume_json": resume_json, "screening": screening, "created_at": datetime.now(timezone.utc)}
    try: result = await db.applications.insert_one(application)
    except Exception: raise HTTPException(409, "You have already applied to this job")
    return {"id": str(result.inserted_id), "screening": screening}

@app.get("/jobs/{job_id}/applications")
async def applications(job_id: str, _: dict = Depends(admin_only)):
    records = []
    async for a in db.applications.find({"job_id": job_id}).sort("screening.score", -1):
        applicant = await db.users.find_one({"_id": ObjectId(a["applicant_id"])})
        records.append({"id": str(a["_id"]), "applicant": {"name": applicant["name"], "email": applicant["email"], "profile": applicant.get("profile", {})}, "screening": a["screening"], "resume_json": a["resume_json"], "created_at": a["created_at"]})
    return records
