from typing import Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.driver import Driver
from app.schemas.driver import DriverCreate, DriverUpdate

class CRUDDriver(CRUDBase[Driver, DriverCreate, DriverUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[Driver]:
        return db.query(Driver).filter(Driver.email == email).first()
    
    def get_by_license(self, db: Session, *, license_number: str) -> Optional[Driver]:
        return db.query(Driver).filter(Driver.license_number == license_number).first()
    
    def get_multi_available(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> list[Driver]:
        return (
            db.query(self.model)
            .filter(Driver.status == "available")
            .offset(skip)
            .limit(limit)
            .all()
        )

    def is_active(self, driver: Driver) -> bool:
        return driver.status == "available"

# Create a singleton instance
driver = CRUDDriver(Driver)
