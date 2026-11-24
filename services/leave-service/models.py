from sqlalchemy import Column, String, Integer, Date, Enum, Text
from database import Base
import uuid
import enum

class LeaveType(str, enum.Enum):
    annual = "annual"
    sick = "sick"
    casual = "casual"

class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, nullable=False, index=True)
    leave_type = Column(Enum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.pending)

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, unique=True, nullable=False, index=True)
    annual_balance = Column(Integer, default=18)
    sick_balance = Column(Integer, default=10)
    casual_balance = Column(Integer, default=6)
