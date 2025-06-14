import httpx
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)

class RouteOptimizationError(Exception):
    """Custom exception for route optimization errors"""
    pass

class RouteOptimizer:
    """
    Service for handling route optimization using GraphHopper's Optimization API.
    """
    
    def __init__(self):
        self.base_url = settings.GRAPHHOPPER_BASE_URL
        self.api_key = settings.GRAPHHOPPER_API_KEY
        self.optimize_endpoint = settings.GRAPHHOPPER_OPTIMIZE_ENDPOINT
        self.solution_endpoint = settings.GRAPHHOPPER_SOLUTION_ENDPOINT
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the GraphHopper API"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        params = kwargs.get('params', {})
        params['key'] = self.api_key
        kwargs['params'] = params
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"GraphHopper API error: {e.response.text}")
            raise RouteOptimizationError(f"GraphHopper API error: {e.response.text}")
        except Exception as e:
            logger.error(f"Error making request to GraphHopper API: {str(e)}")
            raise RouteOptimizationError(f"Error communicating with GraphHopper API: {str(e)}")
    
    async def optimize_routes(
        self,
        vehicles: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Optimize routes for given vehicles and jobs.
        
        Args:
            vehicles: List of vehicle configurations
            jobs: List of jobs to be assigned to vehicles
            options: Additional optimization options
            
        Returns:
            Dict containing the optimization solution
        """
        if not options:
            options = {
                "g": True,  # Enable geocoding
                "vehicle": settings.DEFAULT_VEHICLE_TYPE,
                "timeout": settings.DEFAULT_OPTIMIZATION_TIMEOUT * 1000,  # Convert to milliseconds
            }
        
        payload = {
            "vehicles": vehicles,
            "jobs": jobs,
            "options": options
        }
        
        try:
            # Start optimization
            response = await self._make_request(
                "POST",
                self.optimize_endpoint,
                json=payload
            )
            
            # Get solution
            job_id = response.get('job_id')
            if not job_id:
                raise RouteOptimizationError("No job ID returned from GraphHopper")
                
            # In a real implementation, you might want to poll for the solution
            # Here we're making a simplified version
            solution = await self._get_solution(job_id)
            return solution
            
        except Exception as e:
            logger.error(f"Error in route optimization: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Route optimization failed: {str(e)}")
    
    async def _get_solution(self, job_id: str) -> Dict[str, Any]:
        """Get the solution for a specific job ID"""
        endpoint = f"{self.solution_endpoint.rstrip('/')}/{job_id}"
        return await self._make_request("GET", endpoint)
    
    def prepare_vehicle_data(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare vehicle data for GraphHopper API"""
        return {
            "vehicle_id": str(vehicle_data["id"]),
            "type_id": vehicle_data["type"],
            "start_address": {
                "location_id": f"vehicle_{vehicle_data['id']}_start",
                "lon": vehicle_data["start_lon"],
                "lat": vehicle_data["start_lat"]
            },
            "end_address": {
                "location_id": f"vehicle_{vehicle_data['id']}_end",
                "lon": vehicle_data.get("end_lon", vehicle_data["start_lon"]),
                "lat": vehicle_data.get("end_lat", vehicle_data["start_lat"])
            },
            "return_to_depot": True,
            "earliest_start": 0,
            "latest_end": 24 * 60 * 60,  # 24 hours in seconds
            "max_jobs": 50,  # Adjust based on your needs
            "max_distance": vehicle_data.get("max_distance") * 1000 if vehicle_data.get("max_distance") else None
        }
    
    def prepare_job_data(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare job data for GraphHopper API"""
        return {
            "id": str(job_data["id"]),
            "pickup": {
                "address": {
                    "location_id": f"job_{job_data['id']}_pickup",
                    "lon": job_data["pickup_lon"],
                    "lat": job_data["pickup_lat"]
                },
                "duration": job_data.get("pickup_duration", 300),  # Default 5 minutes
                "time_windows": job_data.get("pickup_time_windows", [])
            },
            "delivery": {
                "address": {
                    "location_id": f"job_{job_data['id']}_delivery",
                    "lon": job_data["delivery_lon"],
                    "lat": job_data["delivery_lat"]
                },
                "duration": job_data.get("delivery_duration", 300),  # Default 5 minutes
                "time_windows": job_data.get("delivery_time_windows", [])
            },
            "skills": job_data.get("required_skills", []),
            "priority": {
                "high": 10,  # Higher number = higher priority
                "medium": 5,
                "low": 1
            }.get(job_data.get("priority", "medium"), 5)
        }
