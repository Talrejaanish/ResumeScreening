from motor.motor_asyncio import AsyncIOMotorClient
from .config import MONGODB_URI, MONGODB_DB

client = AsyncIOMotorClient(MONGODB_URI)
db = client[MONGODB_DB]

async def setup_indexes():
    await db.users.create_index("email", unique=True)
    await db.jobs.create_index("created_at")
    await db.applications.create_index([("job_id", 1), ("applicant_id", 1)], unique=True)
