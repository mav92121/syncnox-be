from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.route_optimizer import RouteOptimizer, RouteOptimizationError
from app.api import deps
from app.models.job import Job
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/optimize-routes")
async def optimize_routes(
    db: Session = Depends(deps.get_db),
):
    """
    Optimize routes for all unassigned jobs.
    
    This endpoint will:
    1. Find all unassigned jobs
    2. Find all available drivers and vehicles
    3. Call the route optimization service
    4. Return the optimized routes
    """
    try:
        # Get unassigned jobs
        jobs = db.query(Job).filter(
            Job.driver_id.is_(None),
            Job.vehicle_id.is_(None),
            Job.scheduled_date >= datetime.utcnow()
        ).all()
        
        if not jobs:
            return {"message": "No unassigned jobs found for optimization"}
        
        # Get available drivers and vehicles
        drivers = db.query(Driver).filter(
            Driver.status == 'available'
        ).all()
        
        vehicles = db.query(Vehicle).filter(
            Vehicle.status == 'available'
        ).all()
        
        if not drivers or not vehicles:
            raise HTTPException(
                status_code=400,
                detail="Not enough drivers or vehicles available for optimization"
            )
        
        # Prepare data for optimization
        optimizer = RouteOptimizer()
        
        # Convert vehicles and jobs to format expected by GraphHopper
        vehicle_data = [
            {
                "id": vehicle.id,
                "type": vehicle.type,
                "start_lon": 0.0,  # Replace with actual depot coordinates
                "start_lat": 0.0,
                "max_distance": vehicle.max_distance
            }
            for vehicle in vehicles
        ]
        
        job_data = [
            {
                "id": job.id,
                "pickup_lon": 0.0,  # Replace with actual coordinates
                "pickup_lat": 0.0,
                "delivery_lon": 0.0,  # Replace with actual coordinates
                "delivery_lat": 0.0,
                "priority": job.priority_level.value if hasattr(job, 'priority_level') else 'medium',
                "pickup_duration": 300,  # 5 minutes in seconds
                "delivery_duration": 300,  # 5 minutes in seconds
            }
            for job in jobs
        ]
        
        # Call the optimization service
        result = await optimizer.optimize_routes(vehicle_data, job_data)
        
        # Process the result and update the database
        # This is a simplified example - you might want to implement more robust logic
        if result.get("status") == "success":
            # Extract assignments from the solution and update the database
            solution = result.get("solution", {})
            routes = solution.get("routes", [])
            
            for route in routes:
                vehicle_id = route.get("vehicle_id")
                activities = route.get("activities", [])
                
                for activity in activities:
                    if activity.get("type") == "delivery" and "job_id" in activity.get("id", ""):
                        job_id = activity["id"].split("_")[1]  # Extract job ID from activity ID
                        
                        # Update job with driver and vehicle assignment
                        job = db.query(Job).filter(Job.id == job_id).first()
                        if job:
                            job.driver_id = vehicle_id  # In a real app, you'd map vehicle_id to driver_id
                            job.vehicle_id = vehicle_id
                            
            db.commit()
            
        return {"message": "Route optimization completed successfully", "result": result}
        
    except RouteOptimizationError as e:
        logger.error(f"Route optimization error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in route optimization: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during route optimization")

@router.get("/status/{job_id}")
async def get_optimization_status(
    job_id: str,
):
    """
    Get the status of a route optimization job.
    """
    try:
        # In a real implementation, you would check the status from your optimization service
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error getting optimization status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
