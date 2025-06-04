from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.job import JobCreate, Job
from app.services import job_service

router = APIRouter()

@router.post("/", response_model=Job)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    return job_service.create_job(db=db, job=job)

@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    if not job_service.delete_job(db=db, job_id=job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully"}
