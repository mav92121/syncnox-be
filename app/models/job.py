from sqlalchemy import Column, String, DateTime, Integer, Enum, Boolean, JSON
from app.db.base_class import Base
import enum
from datetime import datetime

class JobType(str, enum.Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"
    TASK = "task"

class PriorityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class RecurrenceType(str, enum.Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Job Details
    scheduled_date = Column(DateTime, nullable=False)
    job_type = Column(Enum(JobType), nullable=False)
    delivery_address = Column(String, nullable=False)
    priority_level = Column(Enum(PriorityLevel), nullable=False)
    
    # Customer Information
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    business_name = Column(String)
    phone_number = Column(String, nullable=False)  # E.164 format
    
    # Scheduling
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Additional Information
    customer_preferences = Column(String)
    additional_notes = Column(String)
    
    # Configuration
    recurrence_type = Column(Enum(RecurrenceType), nullable=False)
    documents = Column(JSON, comment="Array of file paths/urls")
    payment_status = Column(Boolean, default=False)
