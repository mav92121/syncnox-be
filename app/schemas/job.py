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
    # Mandatory fields
    scheduled_date: datetime
    job_type: JobType
    delivery_address: str
    priority_level: PriorityLevel = PriorityLevel.medium
    recurrence_type: RecurrenceType = RecurrenceType.one_time
    payment_status: PaymentStatus = PaymentStatus.paid  # Default to paid
    address_id: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    # Non-mandatory fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    business_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    phone_number: Optional[str] = None
    customer_preferences: Optional[str] = None
    additional_notes: Optional[str] = None
    documents: Optional[List[str]] = None

class JobCreate(JobBase):
    pass

class Job(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True  # Add this for SQLAlchemy model compatibility
