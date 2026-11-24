from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import httpx
import os
import uvicorn

from database import engine, get_db, Base
from models import LeaveRequest, LeaveBalance, LeaveType, LeaveStatus
from publisher import publish_leave_approved

Base.metadata.create_all(bind=engine)

app = FastAPI(title="HRPulse Leave Service", version="1.0.0")

EMPLOYEE_SERVICE_URL = os.getenv("EMPLOYEE_SERVICE_URL", "http://localhost:8001")

# ── Schemas ──────────────────────────────────────────────────────────────────

class LeaveRequestCreate(BaseModel):
    employee_id: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None

class LeaveRequestOut(BaseModel):
    id: str
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    days: int
    reason: Optional[str]
    status: str

    class Config:
        from_attributes = True

class LeaveBalanceOut(BaseModel):
    employee_id: str
    annual_balance: int
    sick_balance: int
    casual_balance: int

    class Config:
        from_attributes = True

# ── Helpers ───────────────────────────────────────────────────────────────────

def calculate_days(start: date, end: date) -> int:
    delta = (end - start).days + 1
    if delta <= 0:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    return delta

def verify_employee(employee_id: str):
    try:
        resp = httpx.get(f"{EMPLOYEE_SERVICE_URL}/employees/{employee_id}", timeout=5.0)
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Employee not found")
        resp.raise_for_status()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Employee service unavailable")

def get_or_create_balance(db: Session, employee_id: str) -> LeaveBalance:
    balance = db.query(LeaveBalance).filter(LeaveBalance.employee_id == employee_id).first()
    if not balance:
        balance = LeaveBalance(employee_id=employee_id)
        db.add(balance)
        db.commit()
        db.refresh(balance)
    return balance

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "healthy", "service": "leave-service"}

@app.post("/leave/request", response_model=LeaveRequestOut, status_code=201)
def create_leave_request(payload: LeaveRequestCreate, db: Session = Depends(get_db)):
    verify_employee(payload.employee_id)
    days = calculate_days(payload.start_date, payload.end_date)
    balance = get_or_create_balance(db, payload.employee_id)

    # Check balance
    if payload.leave_type == LeaveType.annual and balance.annual_balance < days:
        raise HTTPException(status_code=400, detail=f"Insufficient annual leave balance ({balance.annual_balance} days)")
    if payload.leave_type == LeaveType.sick and balance.sick_balance < days:
        raise HTTPException(status_code=400, detail=f"Insufficient sick leave balance ({balance.sick_balance} days)")
    if payload.leave_type == LeaveType.casual and balance.casual_balance < days:
        raise HTTPException(status_code=400, detail=f"Insufficient casual leave balance ({balance.casual_balance} days)")

    leave = LeaveRequest(
        employee_id=payload.employee_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        days=days,
        reason=payload.reason
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave

@app.get("/leave/{employee_id}", response_model=List[LeaveRequestOut])
def get_employee_leaves(employee_id: str, db: Session = Depends(get_db)):
    return db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee_id).all()

@app.get("/leave/request/{leave_id}", response_model=LeaveRequestOut)
def get_leave(leave_id: str, db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave

@app.put("/leave/request/{leave_id}/approve", response_model=LeaveRequestOut)
def approve_leave(leave_id: str, db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")

    # Deduct from balance
    balance = get_or_create_balance(db, leave.employee_id)
    if leave.leave_type == LeaveType.annual:
        balance.annual_balance -= leave.days
    elif leave.leave_type == LeaveType.sick:
        balance.sick_balance -= leave.days
    elif leave.leave_type == LeaveType.casual:
        balance.casual_balance -= leave.days

    leave.status = LeaveStatus.approved
    db.commit()
    db.refresh(leave)

    # Publish async event to Payroll via RabbitMQ
    publish_leave_approved(leave.employee_id, leave.id, leave.days, leave.leave_type)
    return leave

@app.put("/leave/request/{leave_id}/reject", response_model=LeaveRequestOut)
def reject_leave(leave_id: str, db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending requests can be rejected")
    leave.status = LeaveStatus.rejected
    db.commit()
    db.refresh(leave)
    return leave

@app.get("/leave/balance/{employee_id}", response_model=LeaveBalanceOut)
def get_leave_balance(employee_id: str, db: Session = Depends(get_db)):
    balance = get_or_create_balance(db, employee_id)
    return balance

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
