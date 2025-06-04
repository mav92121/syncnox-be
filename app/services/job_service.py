from sqlalchemy.orm import Session
from app.models.job import Job
from app.schemas.job import JobCreate

def create_job(db: Session, job: JobCreate):
    job_data = job.model_dump()  # Use model_dump() instead of dict()
    db_job = Job(**job_data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def delete_job(db: Session, job_id: int) -> bool:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True
