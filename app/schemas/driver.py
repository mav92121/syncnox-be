from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

class LicenseType(str, Enum):
    car = "car"
    bike = "bike"
    truck = "truck"
    van = "van"
    motorcycle = "motorcycle"

class DriverStatus(str, Enum):
    available = "available"
    busy = "busy"
    on_leave = "on_leave"
    inactive = "inactive"

class DriverBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    license_number: str = Field(..., min_length=5, max_length=50)
    license_type: LicenseType
    max_working_hours: int = Field(8, ge=1, le=24)
    hourly_cost: float = Field(..., gt=0)
    status: DriverStatus = DriverStatus.available

    @field_validator('phone')
    def validate_phone(cls, v):
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v

class DriverCreate(DriverBase):
    pass

class DriverUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    license_number: Optional[str] = Field(None, min_length=5, max_length=50)
    license_type: Optional[LicenseType] = None
    max_working_hours: Optional[int] = Field(None, ge=1, le=24)
    hourly_cost: Optional[float] = Field(None, gt=0)
    status: Optional[DriverStatus] = None

    @field_validator('phone')
    def validate_phone(cls, v):
        if v and not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v

class Driver(DriverBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
