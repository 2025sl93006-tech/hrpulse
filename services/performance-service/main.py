from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uvicorn
import uuid

from database import reviews_collection
from publisher import publish_performance_rated

app = FastAPI(title="HRPulse Performance Service", version="1.0.0")

# ── Schemas ──────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    employee_id: str
    reviewer_id: str
    period: str  # e.g. "Q3-2026"
    goals: str
    achievements: str

class ReviewRate(BaseModel):
    rating: int = Field(ge=1, le=5)

class ReviewOut(BaseModel):
    id: str
    employee_id: str
    reviewer_id: str
    period: str
    goals: str
    achievements: str
    rating: Optional[int]
    status: str
    created_at: str
    submitted_at: Optional[str]

def doc_to_out(doc: dict) -> ReviewOut:
    return ReviewOut(
        id=doc["_id"],
        employee_id=doc["employee_id"],
        reviewer_id=doc["reviewer_id"],
        period=doc["period"],
        goals=doc["goals"],
        achievements=doc["achievements"],
        rating=doc.get("rating"),
        status=doc["status"],
        created_at=str(doc["created_at"]),
        submitted_at=str(doc["submitted_at"]) if doc.get("submitted_at") else None
    )

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "performance-service"}

@app.post("/reviews", status_code=201)
async def create_review(payload: ReviewCreate):
    doc = {
        "_id": str(uuid.uuid4()),
        "employee_id": payload.employee_id,
        "reviewer_id": payload.reviewer_id,
        "period": payload.period,
        "goals": payload.goals,
        "achievements": payload.achievements,
        "rating": None,
        "status": "draft",
        "created_at": datetime.utcnow(),
        "submitted_at": None
    }
    await reviews_collection.insert_one(doc)
    return doc_to_out(doc)

@app.get("/reviews/{employee_id}", response_model=List[ReviewOut])
async def get_employee_reviews(employee_id: str):
    docs = await reviews_collection.find({"employee_id": employee_id}).to_list(100)
    return [doc_to_out(d) for d in docs]

@app.get("/reviews/detail/{review_id}", response_model=ReviewOut)
async def get_review(review_id: str):
    doc = await reviews_collection.find_one({"_id": review_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Review not found")
    return doc_to_out(doc)

@app.put("/reviews/{review_id}/submit", response_model=ReviewOut)
async def submit_review(review_id: str):
    doc = await reviews_collection.find_one({"_id": review_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Review not found")
    if doc["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft reviews can be submitted")
    await reviews_collection.update_one(
        {"_id": review_id},
        {"$set": {"status": "submitted", "submitted_at": datetime.utcnow()}}
    )
    doc = await reviews_collection.find_one({"_id": review_id})
    return doc_to_out(doc)

@app.put("/reviews/{review_id}/rate", response_model=ReviewOut)
async def rate_review(review_id: str, payload: ReviewRate):
    doc = await reviews_collection.find_one({"_id": review_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Review not found")
    if doc["status"] not in ("submitted", "draft"):
        raise HTTPException(status_code=400, detail="Cannot rate a completed review")
    await reviews_collection.update_one(
        {"_id": review_id},
        {"$set": {"rating": payload.rating, "status": "completed"}}
    )
    doc = await reviews_collection.find_one({"_id": review_id})

    # Publish async event to Payroll via RabbitMQ
    publish_performance_rated(doc["employee_id"], review_id, payload.rating)
    return doc_to_out(doc)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
