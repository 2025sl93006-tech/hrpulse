from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from contextlib import asynccontextmanager

from database import engine, get_db, Base
from models import Payroll, PayrollAdjustment, PayrollStatus
from circuit_breaker import get_employee_safe, SALARY_GRADES, employee_breaker
from consumer import start_consumer_thread

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_consumer_thread()
    yield

app = FastAPI(title="HRPulse Payroll Service", version="1.0.0", lifespan=lifespan)

# ── Schemas ──────────────────────────────────────────────────────────────────

class PayrollRunRequest(BaseModel):
    employee_id: str
    month: int
    year: int

class PayrollOut(BaseModel):
    id: str
    employee_id: str
    month: int
    year: int
    basic_salary: float
    deductions: float
    bonus: float
    net_salary: float
    status: str

    class Config:
        from_attributes = True

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    breaker_state = str(employee_breaker.current_state)
    return {
        "status": "healthy",
        "service": "payroll-service",
        "circuit_breaker": breaker_state
    }

@app.post("/payroll/run", response_model=PayrollOut, status_code=201)
def run_payroll(payload: PayrollRunRequest, db: Session = Depends(get_db)):
    existing = db.query(Payroll).filter(
        Payroll.employee_id == payload.employee_id,
        Payroll.month == payload.month,
        Payroll.year == payload.year
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Payroll already processed for this period")

    # Fetch employee via circuit breaker
    employee = get_employee_safe(payload.employee_id)
    grade = employee.get("salary_grade", "L2")
    basic = SALARY_GRADES.get(grade, 50000.0)

    # Collect adjustments for this employee
    adjustments = db.query(PayrollAdjustment).filter(
        PayrollAdjustment.employee_id == payload.employee_id
    ).all()
    deductions = sum(a.amount for a in adjustments if a.adjustment_type.value == "leave_deduction")
    bonus = sum(a.amount for a in adjustments if a.adjustment_type.value == "performance_bonus")

    net = basic - deductions + bonus

    payroll = Payroll(
        employee_id=payload.employee_id,
        month=payload.month,
        year=payload.year,
        basic_salary=basic,
        deductions=deductions,
        bonus=bonus,
        net_salary=net,
        status=PayrollStatus.processed
    )
    db.add(payroll)
    db.commit()
    db.refresh(payroll)
    return payroll

@app.get("/payroll/{employee_id}", response_model=List[PayrollOut])
def get_payroll_history(employee_id: str, db: Session = Depends(get_db)):
    return db.query(Payroll).filter(Payroll.employee_id == employee_id).all()

@app.get("/payslip/{payroll_id}", response_model=PayrollOut)
def get_payslip(payroll_id: str, db: Session = Depends(get_db)):
    p = db.query(Payroll).filter(Payroll.id == payroll_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payslip not found")
    return p

@app.get("/circuit-breaker/status")
def circuit_breaker_status():
    return {
        "state": str(employee_breaker.current_state),
        "fail_count": employee_breaker.fail_counter,
        "fail_max": employee_breaker.fail_max,
        "reset_timeout": employee_breaker.reset_timeout
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=False)
