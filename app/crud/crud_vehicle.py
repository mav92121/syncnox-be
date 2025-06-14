from typing import Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate

class CRUDVehicle(CRUDBase[Vehicle, VehicleCreate, VehicleUpdate]):
    def get_by_license_plate(
        self, db: Session, *, license_plate: str
    ) -> Optional[Vehicle]:
        return db.query(Vehicle).filter(
            Vehicle.license_plate == license_plate.upper()
        ).first()
    
    def get_multi_available(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> list[Vehicle]:
        return (
            db.query(self.model)
            .filter(Vehicle.status == "available")
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_type(
        self, db: Session, *, vehicle_type: str, skip: int = 0, limit: int = 100
    ) -> list[Vehicle]:
        return (
            db.query(self.model)
            .filter(Vehicle.type == vehicle_type, Vehicle.status == "available")
            .offset(skip)
            .limit(limit)
            .all()
        )

# Create a singleton instance
vehicle = CRUDVehicle(Vehicle)
