from sqlalchemy import Column, String, DateTime, Integer, Enum, Boolean, JSON
from app.db.base_class import Base
import enum
from datetime import datetime

class JobType(str, enum.Enum):
    delivery = "delivery"
    pickup = "pickup"
    task = "task"

class PriorityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class RecurrenceType(str, enum.Enum):
    one_time = "one_time"
    recurring = "recurring"

class PaymentStatus(str, enum.Enum):
    paid = "paid"
    unpaid = "unpaid"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Job Details
    scheduled_date = Column(DateTime, nullable=False)
    job_type = Column(Enum(JobType), nullable=False)
    delivery_address = Column(String, nullable=False)
    priority_level = Column(Enum(PriorityLevel), nullable=False, default=PriorityLevel.medium)
    
    # Customer Information
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)  # E.164 format
    
    # Scheduling
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    
    # Additional Information
    customer_preferences = Column(String, nullable=True)
    additional_notes = Column(String, nullable=True)
    
    # Configuration
    recurrence_type = Column(Enum(RecurrenceType), nullable=False, default=RecurrenceType.one_time)
    
    # Using JSON to store array of file paths/metadata
    documents = Column(JSON, nullable=True, comment="Array of file metadata with paths and info")
    
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.paid)
