from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter(prefix="/driver", tags=["driver"])

@router.get("", response_model=List[schemas.Driver])
def read_drivers(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve drivers.
    """
    drivers = crud.driver.get_multi(db, skip=skip, limit=limit)
    return drivers

@router.post("", response_model=schemas.Driver, status_code=status.HTTP_201_CREATED)
def create_driver(
    *,
    db: Session = Depends(deps.get_db),
    driver_in: schemas.DriverCreate,
):
    """
    Create new driver.
    """
    driver = crud.driver.get_by_email(db, email=driver_in.email)
    if driver:
        raise HTTPException(
            status_code=400,
            detail="The driver with this email already exists in the system.",
        )
    
    driver = crud.driver.get_by_license(db, license_number=driver_in.license_number)
    if driver:
        raise HTTPException(
            status_code=400,
            detail="The driver with this license number already exists in the system.",
        )
    
    return crud.driver.create(db=db, obj_in=driver_in)

@router.get("/available", response_model=List[schemas.Driver])
def read_available_drivers(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve available drivers.
    """
    drivers = crud.driver.get_multi_available(db, skip=skip, limit=limit)
    return drivers

@router.get("/{driver_id}", response_model=schemas.Driver)
def read_driver(
    driver_id: int,
    db: Session = Depends(deps.get_db),
):
    """
    Get driver by ID.
    """
    driver = crud.driver.get(db, id=driver_id)
    if not driver:
        raise HTTPException(
            status_code=404,
            detail="The driver with this ID does not exist in the system",
        )
    return driver

@router.put("/{driver_id}", response_model=schemas.Driver)
def update_driver(
    *,
    db: Session = Depends(deps.get_db),
    driver_id: int,
    driver_in: schemas.DriverUpdate,
):
    """
    Update a driver.
    """
    driver = crud.driver.get(db, id=driver_id)
    if not driver:
        raise HTTPException(
            status_code=404,
            detail="The driver with this ID does not exist in the system",
        )
    
    # Check if email is being updated to an existing one
    if driver_in.email and driver_in.email != driver.email:
        existing_driver = crud.driver.get_by_email(db, email=driver_in.email)
        if existing_driver and existing_driver.id != driver_id:
            raise HTTPException(
                status_code=400,
                detail="The driver with this email already exists in the system.",
            )
    
    # Check if license number is being updated to an existing one
    if driver_in.license_number and driver_in.license_number != driver.license_number:
        existing_driver = crud.driver.get_by_license(db, license_number=driver_in.license_number)
        if existing_driver and existing_driver.id != driver_id:
            raise HTTPException(
                status_code=400,
                detail="The driver with this license number already exists in the system.",
            )
    
    return crud.driver.update(db=db, db_obj=driver, obj_in=driver_in)

@router.delete("/{driver_id}", response_model=schemas.Driver)
def delete_driver(
    *,
    db: Session = Depends(deps.get_db),
    driver_id: int,
):
    """
    Delete a driver.
    """
    driver = crud.driver.get(db, id=driver_id)
    if not driver:
        raise HTTPException(
            status_code=404,
            detail="The driver with this ID does not exist in the system",
        )
    
    # Check if driver is assigned to any jobs
    if driver.jobs:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete driver with assigned jobs. Reassign or delete the jobs first.",
        )
    
    return crud.driver.remove(db=db, id=driver_id)
