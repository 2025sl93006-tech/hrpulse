from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date
import uvicorn

from database import engine, get_db, Base
from models import Employee, EmployeeStatus, SalaryGrade

Base.metadata.create_all(bind=engine)

app = FastAPI(title="HRPulse Employee Service", version="1.0.0")

# ── Schemas ──────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    name: str
    email: str
    department: str
    designation: str
    manager_id: Optional[str] = None
    salary_grade: SalaryGrade = SalaryGrade.L1
    bank_account: Optional[str] = None
    joining_date: date

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    manager_id: Optional[str] = None
    salary_grade: Optional[SalaryGrade] = None
    bank_account: Optional[str] = None
    status: Optional[EmployeeStatus] = None

class EmployeeOut(BaseModel):
    id: str
    name: str
    email: str
    department: str
    designation: str
    manager_id: Optional[str]
    salary_grade: str
    bank_account: Optional[str]
    joining_date: date
    status: str

    class Config:
        from_attributes = True

class OrgNode(BaseModel):
    id: str
    name: str
    designation: str
    department: str
    direct_reports: List["OrgNode"] = []

OrgNode.model_rebuild()

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_org_tree(employee: Employee, all_employees: list) -> dict:
    reports = [e for e in all_employees if e.manager_id == employee.id]
    return {
        "id": employee.id,
        "name": employee.name,
        "designation": employee.designation,
        "department": employee.department,
        "direct_reports": [build_org_tree(r, all_employees) for r in reports]
    }

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "healthy", "service": "employee-service"}

@app.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    existing = db.query(Employee).filter(Employee.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    if payload.manager_id:
        manager = db.query(Employee).filter(Employee.id == payload.manager_id).first()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")
    emp = Employee(**payload.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp

@app.get("/employees", response_model=List[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).all()

@app.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@app.put("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: str, payload: EmployeeUpdate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(emp, field, value)
    db.commit()
    db.refresh(emp)
    return emp

@app.get("/org-chart")
def org_chart(db: Session = Depends(get_db)):
    all_employees = db.query(Employee).all()
    roots = [e for e in all_employees if e.manager_id is None]
    return [build_org_tree(r, all_employees) for r in roots]

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
