from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter(prefix="/vehicle", tags=["vehicle"])

@router.get("", response_model=List[schemas.Vehicle])
def read_vehicles(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    type: Optional[schemas.VehicleType] = None,
):
    """
    Retrieve vehicles, optionally filtered by type.
    """
    if type:
        return crud.vehicle.get_by_type(db, vehicle_type=type, skip=skip, limit=limit)
    return crud.vehicle.get_multi(db, skip=skip, limit=limit)

@router.post("", response_model=schemas.Vehicle, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    *,
    db: Session = Depends(deps.get_db),
    vehicle_in: schemas.VehicleCreate,
):
    """
    Create new vehicle.
    """
    vehicle = crud.vehicle.get_by_license_plate(db, license_plate=vehicle_in.license_plate)
    if vehicle:
        raise HTTPException(
            status_code=400,
            detail="A vehicle with this license plate already exists in the system.",
        )
    return crud.vehicle.create(db=db, obj_in=vehicle_in)

@router.get("/available", response_model=List[schemas.Vehicle])
def read_available_vehicles(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    type: Optional[schemas.VehicleType] = None,
):
    """
    Retrieve available vehicles, optionally filtered by type.
    """
    if type:
        return crud.vehicle.get_available_by_type(db, vehicle_type=type, skip=skip, limit=limit)
    return crud.vehicle.get_multi_available(db, skip=skip, limit=limit)

@router.get("/{vehicle_id}", response_model=schemas.Vehicle)
def read_vehicle(
    vehicle_id: int,
    db: Session = Depends(deps.get_db),
):
    """
    Get vehicle by ID.
    """
    vehicle = crud.vehicle.get(db, id=vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="The vehicle with this ID does not exist in the system",
        )
    return vehicle

@router.put("/{vehicle_id}", response_model=schemas.Vehicle)
def update_vehicle(
    *,
    db: Session = Depends(deps.get_db),
    vehicle_id: int,
    vehicle_in: schemas.VehicleUpdate,
):
    """
    Update a vehicle.
    """
    vehicle = crud.vehicle.get(db, id=vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="The vehicle with this ID does not exist in the system",
        )
    
    # Check if license plate is being updated to an existing one
    if vehicle_in.license_plate and vehicle_in.license_plate != vehicle.license_plate:
        existing_vehicle = crud.vehicle.get_by_license_plate(db, license_plate=vehicle_in.license_plate)
        if existing_vehicle and existing_vehicle.id != vehicle_id:
            raise HTTPException(
                status_code=400,
                detail="A vehicle with this license plate already exists in the system.",
            )
    
    return crud.vehicle.update(db=db, db_obj=vehicle, obj_in=vehicle_in)

@router.delete("/{vehicle_id}", response_model=schemas.Vehicle)
def delete_vehicle(
    *,
    db: Session = Depends(deps.get_db),
    vehicle_id: int,
):
    """
    Delete a vehicle.
    """
    vehicle = crud.vehicle.get(db, id=vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="The vehicle with this ID does not exist in the system",
        )
    
    # Check if vehicle is assigned to any jobs
    if vehicle.jobs:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete vehicle with assigned jobs. Reassign or delete the jobs first.",
        )
    
    return crud.vehicle.remove(db=db, id=vehicle_id)
