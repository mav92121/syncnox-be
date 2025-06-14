from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum

class VehicleType(str, Enum):
    car = "car"
    bike = "bike"
    truck = "truck"
    van = "van"
    motorcycle = "motorcycle"
    scooter = "scooter"
    bicycle = "bicycle"

class VehicleStatus(str, Enum):
    available = "available"
    in_use = "in_use"
    maintenance = "maintenance"
    inactive = "inactive"

class VehicleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    type: VehicleType
    license_plate: str = Field(..., min_length=4, max_length=15)
    capacity: int = Field(..., gt=0, description="Capacity in kg")
    max_distance: Optional[int] = Field(None, gt=0, description="Maximum distance in km")
    cost_per_km: float = Field(..., gt=0)
    status: VehicleStatus = VehicleStatus.available

    @field_validator('license_plate')
    def validate_license_plate(cls, v):
        # Basic validation for license plate format
        if not v.replace(" ", "").isalnum():
            raise ValueError("License plate must be alphanumeric")
        return v.upper()

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    type: Optional[VehicleType] = None
    license_plate: Optional[str] = Field(None, min_length=4, max_length=15)
    capacity: Optional[int] = Field(None, gt=0)
    max_distance: Optional[int] = Field(None, gt=0)
    cost_per_km: Optional[float] = Field(None, gt=0)
    status: Optional[VehicleStatus] = None

    @field_validator('license_plate')
    def validate_license_plate(cls, v):
        if v and not v.replace(" ", "").isalnum():
            raise ValueError("License plate must be alphanumeric")
        return v.upper() if v else v

class Vehicle(VehicleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
