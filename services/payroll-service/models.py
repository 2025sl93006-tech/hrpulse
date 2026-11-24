from sqlalchemy import Column, String, Integer, Float, Enum, Text, DateTime
from sqlalchemy.sql import func
from database import Base
import uuid
import enum

class PayrollStatus(str, enum.Enum):
    pending = "pending"
    processed = "processed"

class AdjustmentType(str, enum.Enum):
    leave_deduction = "leave_deduction"
    performance_bonus = "performance_bonus"

class Payroll(Base):
    __tablename__ = "payrolls"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, nullable=False, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    basic_salary = Column(Float, nullable=False)
    deductions = Column(Float, default=0.0)
    bonus = Column(Float, default=0.0)
    net_salary = Column(Float, nullable=False)
    status = Column(Enum(PayrollStatus), default=PayrollStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PayrollAdjustment(Base):
    __tablename__ = "payroll_adjustments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, nullable=False, index=True)
    adjustment_type = Column(Enum(AdjustmentType), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
