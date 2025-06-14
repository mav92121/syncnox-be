from sqlalchemy import Column, String, DateTime, Integer, DECIMAL
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # truck, van, car, bike, etc.
    license_plate = Column(String, unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)  # in kg
    max_distance = Column(Integer, nullable=True)  # in km, optional
    cost_per_km = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String, default='available')  # available, in_use, maintenance
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="vehicle")

    def __repr__(self):
        return f"<Vehicle {self.name} ({self.license_plate})>"
