from sqlalchemy import Column, String, DateTime, Integer, DECIMAL
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=False)
    license_number = Column(String, nullable=False, unique=True)
    license_type = Column(String, nullable=False)
    max_working_hours = Column(Integer, default=8)  # in hours
    hourly_cost = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String, default='available')  # available, busy, on_leave
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="driver")

    def __repr__(self):
        return f"<Driver {self.first_name} {self.last_name}>"
