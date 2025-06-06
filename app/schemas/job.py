from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from enum import Enum

class JobType(str, Enum):
    delivery = "delivery"
    pickup = "pickup"
    task = "task"

class PriorityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class RecurrenceType(str, Enum):
    one_time = "one_time"
    recurring = "recurring"

class PaymentStatus(str, Enum):
    paid = "paid"
    unpaid = "unpaid"

class JobBase(BaseModel):
    scheduled_date: datetime
    job_type: JobType
    delivery_address: str
    priority_level: PriorityLevel
    first_name: str
    last_name: str
    email: EmailStr
    business_name: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    phone_number: str
    customer_preferences: Optional[str] = None
    additional_notes: Optional[str] = None
    recurrence_type: RecurrenceType
    documents: Optional[List[str]] = None  # Changed from document_urls to match model
    payment_status: PaymentStatus = PaymentStatus.unpaid

class JobCreate(JobBase):
    pass

class Job(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True  # Add this for SQLAlchemy model compatibility
