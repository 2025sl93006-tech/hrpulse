from sqlalchemy import Column, String, Integer, Float, Date, Enum, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import uuid
import enum

class EmployeeStatus(str, enum.Enum):
    onboarding = "onboarding"
    active = "active"
    inactive = "inactive"

class SalaryGrade(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"

class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    department = Column(String, nullable=False)
    designation = Column(String, nullable=False)
    manager_id = Column(String, ForeignKey("employees.id"), nullable=True)
    salary_grade = Column(Enum(SalaryGrade), default=SalaryGrade.L1)
    bank_account = Column(String, nullable=True)
    joining_date = Column(Date, nullable=False)
    status = Column(Enum(EmployeeStatus), default=EmployeeStatus.onboarding)

    reports_to = relationship("Employee", remote_side=[id], backref="direct_reports")
