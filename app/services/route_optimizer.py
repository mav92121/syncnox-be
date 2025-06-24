import logging
import math
from typing import List, Dict, Optional, Any, Tuple, Union, Set, DefaultDict
from datetime import datetime, time, date, timedelta
import asyncio
import json
import hashlib
import time as time_module
from collections import defaultdict
from enum import Enum
from dataclasses import dataclass, field
import aiohttp

from fastapi import HTTPException, status
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver.pywrapcp import RoutingIndexManager, RoutingModel, DefaultRoutingSearchParameters

from app.core.config import settings
from app.schemas.optimization import (
    VehicleRequest, JobRequest, OptimizationRequest, OptimizationResult,
    VehicleSchedule, OptimizationStatus, OptimizationType, PlanningHorizon,
    Location, TimeWindow, BreakTimeWindow, VehicleBreak, VehicleCosts, VehicleSkills, JobRequirements
)
from app.services.clients.graphhopper import GraphHopperClient, GraphHopperClientError

# Constants
DEFAULT_PROFILE = 'car'
DEFAULT_WORKING_HOURS = (time(9, 0), time(17, 0))
MAX_OPTIMIZATION_TIME_SECONDS = 30  # Maximum time to spend on optimization in seconds
TimeWindowSeconds = Tuple[int, int]  # (start_seconds, end_seconds)
BreakId = str
VehicleId = str
JobId = str
Date = date

# Type aliases
Location = Tuple[float, float]  # (latitude, longitude)
TimeWindow = Tuple[datetime, datetime]  # (start_time, end_time)

logger = logging.getLogger(__name__)

class RouteOptimizationError(Exception):
    """Custom exception for route optimization errors"""
    pass


class OptimizationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VehicleSchedule:
    """Represents a vehicle's schedule for a single day"""
    date: date
    start_time: time
    end_time: time
    breaks: List[VehicleBreak] = field(default_factory=list)
    max_driving_duration: Optional[int] = None  # in seconds
    max_distance: Optional[float] = None  # in meters
    assigned_jobs: List[JobRequest] = field(default_factory=list)
    
    @property
    def working_duration(self) -> int:
        """Total working duration in seconds"""
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        if end <= start:
            end += timedelta(days=1)
        return int((end - start).total_seconds())


@dataclass
class OptimizationResult:
    """Result of a route optimization"""
    status: OptimizationStatus
    routes: List[Dict[str, Any]] = field(default_factory=list)
    total_distance: float = 0.0  # in meters
    total_duration: float = 0.0  # in seconds
    total_cost: float = 0.0  # in currency units
    optimization_type: OptimizationType = OptimizationType.DURATION
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

class Job:
    """Represents a job or stop that needs to be visited by a vehicle."""
    def __init__(self, 
                 job_id: str, 
                 location: Location, 
                 duration: int = 300, 
                 time_window: Optional[TimeWindow] = None,
                 priority: int = 1,
                 requirements: Optional[JobRequirements] = None,
                 allowed_vehicles: Optional[List[str]] = None,
                 setup_duration: int = 0,
                 service_duration: int = 0,
                 pickup_delivery: Optional[Tuple[str, int]] = None,
                 **kwargs):
        """
        Initialize a job.
        
        Args:
            job_id: Unique identifier for the job
            location: Tuple of (latitude, longitude)
            duration: Service duration in seconds (default: 300)
            time_window: Optional time window as (start_time, end_time)
            priority: Job priority (1-10, higher is more important)
            requirements: Requirements for performing this job
            allowed_vehicles: List of vehicle IDs that can perform this job
            setup_duration: Additional setup time in seconds
            service_duration: Time required to perform the actual service
            pickup_delivery: For pickup and delivery jobs (delivery_job_id, max_transit_time)
            **kwargs: Additional keyword arguments for future extensions
        """
        self.id = job_id
        self.location = location  # (lat, lon)
        self.duration = duration  # in seconds
        self.time_window = time_window
        self.priority = priority
        self.requirements = requirements or JobRequirements()
        self.allowed_vehicles = allowed_vehicles or []
        self.setup_duration = setup_duration
        self.service_duration = service_duration or duration
        self.pickup_delivery = pickup_delivery

class Vehicle:
    """Represents a vehicle that can perform jobs."""
    def __init__(self, 
                 id: str, 
                 start_location: Location,
                 capacity: int = 1,
                 time_window: Optional[TimeWindow] = None,
                 breaks: Optional[List[VehicleBreak]] = None,
                 costs: Optional[VehicleCosts] = None,
                 skills: Optional[VehicleSkills] = None,
                 max_daily_driving_time: Optional[int] = None,
                 max_weekly_driving_time: Optional[int] = None,
                 **kwargs):
        """
        Initialize a vehicle.
        
        Args:
            id: Unique identifier for the vehicle
            start_location: Starting location as (latitude, longitude)
            capacity: Vehicle capacity (default: 1)
            time_window: Optional time window as (start_time, end_time)
            breaks: Optional list of vehicle breaks
            costs: Vehicle cost factors
            skills: Vehicle skills and capabilities
            max_daily_driving_time: Maximum daily driving time in seconds
            max_weekly_driving_time: Maximum weekly driving time in seconds
            **kwargs: Additional keyword arguments for future extensions
        """
        self.id = id
        self.start_location = start_location  # (lat, lon)
        self.capacity = capacity
        self.time_window = time_window
        self.breaks = breaks or []
        self.costs = costs or VehicleCosts()
        self.skills = skills or VehicleSkills()
        self.max_daily_driving_time = max_daily_driving_time
        self.max_weekly_driving_time = max_weekly_driving_time

class RouteOptimizer:
    """A service for optimizing routes using GraphHopper and OR-Tools.
    Handles the optimization logic while delegating API calls to the GraphHopper client.
    """
    def __init__(
        self, 
        api_key: str = None,
        timeout: int = 30,
        max_workers: int = 4,
        graphhopper_client: GraphHopperClient = None
    ):
        """
        Initialize the route optimizer.
        
        Args:
            api_key: GraphHopper API key (defaults to settings.GRAPHHOPPER_API_KEY)
            timeout: Optimization timeout in seconds per day
            max_workers: Maximum number of worker threads for parallel operations
            graphhopper_client: Optional GraphHopperClient instance (for testing)
        """
        self.api_key = api_key or settings.GRAPHHOPPER_API_KEY
        if not self.api_key:
            raise ValueError("GraphHopper API key is required. Set GRAPHHOPPER_API_KEY in settings.")
            
        self.timeout = timeout
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        
        # Cache for distance/duration matrices
        self._matrix_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Store the GraphHopper client or create a new one if not provided
        self._gh_client = graphhopper_client or GraphHopperClient(
            api_key=self.api_key,
            base_url=settings.GRAPHHOPPER_BASE_URL
        )
        
        # Log initialization
        self.logger.info("RouteOptimizer initialized with timeout=%ss, max_workers=%d", 
                        timeout, max_workers)
    
    def _get_cache_key(
        self,
        locations: List[Tuple[float, float]],
        profile: str
    ) -> str:
        """Generate a cache key for the distance/duration matrix"""
        loc_str = '|'.join(f"{lat:.6f},{lon:.6f}" for lat, lon in locations)
        return f"{profile}:{loc_str}"
        
    async def _get_matrices(
        self,
        locations: List[Tuple[float, float]],
        profile: str = 'car',
        force_refresh: bool = False
    ) -> Dict[str, List[List[float]]]:
        """
        Get both distance and duration matrices from GraphHopper with caching.
        
        Args:
            locations: List of (lat, lon) tuples
            profile: Vehicle profile (car, bike, foot, etc.)
            force_refresh: If True, bypass the cache
            
        Returns:
            Dict containing 'distances' and 'times' matrices
            
        Raises:
            RouteOptimizationError: If there's an error fetching the matrices
        """
        try:
            # Generate a cache key for the request
            cache_key = self._get_cache_key(locations, profile)
            
            # Return cached result if available and not forcing refresh
            if cache_key in self._matrix_cache and not force_refresh:
                self._cache_hits += 1
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return self._matrix_cache[cache_key]
            
            self._cache_misses += 1
            self.logger.debug(f"Cache miss for key: {cache_key}")
            
            # Get the distance and time matrices using the stored client
            response = await self._gh_client.get_distance_matrix(
                locations=locations,
                profile=profile,
                out_arrays=['distances', 'times']
            )
            
            # Format the response to match the expected structure
            matrices = {
                'distances': response.get('distances', []),
                'times': response.get('times', [])
            }
            
            # Cache the result
            self._matrix_cache[cache_key] = matrices
            
            # Enforce cache size limit (optional)
            if len(self._matrix_cache) > 1000:  # Limit cache to 1000 entries
                self._matrix_cache.pop(next(iter(self._matrix_cache)))
            
            return matrices
                
        except GraphHopperClientError as e:
            error_msg = f"GraphHopper API error: {str(e) or 'Unknown error'}"
            self.logger.error(error_msg)
            raise RouteOptimizationError(f"Failed to get distance matrix: {str(e) or 'Unknown error'}")
            
        except Exception as e:
            error_msg = f"Unexpected error in _get_matrices: {str(e) or 'Unknown error'}"
            self.logger.error(error_msg, exc_info=True)
            raise RouteOptimizationError("An unexpected error occurred while processing the distance matrix")
    
    def _generate_vehicle_schedules(
        self,
        vehicles: List[VehicleRequest],
        planning_horizon: Optional[PlanningHorizon] = None
    ) -> Dict[str, List[VehicleSchedule]]:
        """
        Generate daily schedules for all vehicles over the planning horizon.
        
        Args:
            vehicles: List of vehicle requests
            planning_horizon: Optional planning horizon
            
        Returns:
            Dict mapping vehicle_id to list of VehicleSchedules
        """
        schedules = {}
        
        for vehicle in vehicles:
            if planning_horizon:
                # Multi-day planning
                current_date = planning_horizon.start_date
                vehicle_schedules = []
                
                while current_date <= planning_horizon.end_date:
                    if current_date.weekday() in planning_horizon.working_days:
                        vehicle_schedules.append(VehicleSchedule(
                            date=current_date,
                            start_time=planning_horizon.working_hours[0],
                            end_time=planning_horizon.working_hours[1],
                            breaks=vehicle.breaks.copy(),
                            max_driving_duration=vehicle.max_daily_driving_time,
                            max_distance=vehicle.max_daily_distance
                        ))
                    current_date += timedelta(days=1)
            else:
                # Single day planning
                vehicle_schedules = [VehicleSchedule(
                    date=date.today(),
                    start_time=time(9, 0),  # Default working hours
                    end_time=time(17, 0),
                    breaks=vehicle.breaks.copy(),
                    max_driving_duration=vehicle.max_daily_driving_time,
                    max_distance=vehicle.max_daily_distance
                )]
                
            schedules[vehicle.id] = vehicle_schedules
            
        return schedules
    
    async def optimize_routes(
        self,
        vehicles: List[VehicleRequest],
        jobs: List[JobRequest],
        optimization_type: OptimizationType = OptimizationType.DURATION,
        planning_horizon: Optional[PlanningHorizon] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        Optimize routes for the given vehicles and jobs.
        
        Args:
            vehicles: List of vehicle requests
            jobs: List of job requests
            optimization_type: Type of optimization (duration or distance)
            planning_horizon: Optional planning horizon for multi-day optimization
            options: Additional optimization options
            
        Returns:
            OptimizationResult containing the optimized routes and metrics
            
        Raises:
            ValueError: If no vehicles are provided, if vehicles is None, or if jobs is None
            RouteOptimizationError: If optimization fails
        """
        # Input validation
        if vehicles is None:
            raise ValueError("vehicles cannot be None")
            
        if not vehicles:
            raise ValueError("At least one vehicle must be provided")
            
        if jobs is None:
            jobs = []
            
        # Ensure all vehicles have valid locations
        for i, vehicle in enumerate(vehicles):
            if not hasattr(vehicle, 'start_location') or not vehicle.start_location:
                raise ValueError(f"Vehicle at index {i} is missing start_location")
                
        # Ensure all jobs have valid locations
        for i, job in enumerate(jobs):
            if not hasattr(job, 'location') or not job.location:
                raise ValueError(f"Job at index {i} is missing location")
                
        start_time = time_module.time()
        self.logger.info(
            "Starting route optimization for %d vehicles and %d jobs with type=%s", 
            len(vehicles), 
            len(jobs),
            optimization_type.value
        )
        
        # Initialize result with default values
        result = OptimizationResult(
            status=OptimizationStatus.IN_PROGRESS,
            optimization_type=optimization_type,
            metadata={
                'vehicles': len(vehicles),
                'jobs': len(jobs),
                'optimization_type': optimization_type.value,
                'planning_horizon': planning_horizon.dict() if planning_horizon else None,
                'start_time': datetime.utcnow().isoformat(),
                'cache_stats': {
                    'hits': self._cache_hits,
                    'misses': self._cache_misses,
                    'size': len(self._matrix_cache)
                }
            }
        )
        
        try:
            # Generate vehicle schedules
            vehicle_schedules = self._generate_vehicle_schedules(vehicles, planning_horizon)
            
            # Prepare optimization data (this will fetch distance/duration matrices)
            try:
                optimization_data = await self._prepare_optimization_data(
                    vehicles=vehicles,
                    jobs=jobs,
                    vehicle_schedules=vehicle_schedules,
                    optimization_type=optimization_type,
                    options=options or {}
                )
            except GraphHopperClientError as e:
                error_msg = f"Failed to fetch routing data: {str(e)}"
                self.logger.error(error_msg)
                result.status = OptimizationStatus.FAILED
                result.errors.append(error_msg)
                return result
            
            # Solve the optimization problem
            try:
                solution = await self._solve_optimization(optimization_data)
                
                # Format the result
                result = self._format_optimization_result(solution, optimization_data)
                result.status = OptimizationStatus.COMPLETED
                
            except Exception as e:
                error_msg = f"Optimization failed: {str(e)}"
                self.logger.exception(error_msg)
                result.status = OptimizationStatus.FAILED
                result.errors.append(error_msg)
                
            # Update metadata with execution details
            duration = time_module.time() - start_time
            result.metadata.update({
                'execution_time_seconds': duration,
                'end_time': datetime.utcnow().isoformat(),
                'cache_stats': {
                    'hits': self._cache_hits,
                    'misses': self._cache_misses,
                    'hit_ratio': self._cache_hits / (self._cache_hits + self._cache_misses) 
                                if (self._cache_hits + self._cache_misses) > 0 else 0,
                    'size': len(self._matrix_cache)
                }
            })
            
            # Log optimization metrics
            if result.status == OptimizationStatus.COMPLETED:
                self.logger.info(
                    "Optimization completed in %.2f seconds. "
                    "Total distance: %.2f km, Total duration: %.2f hours",
                    duration,
                    result.total_distance / 1000,  # Convert to km
                    result.total_duration / 3600   # Convert to hours
                )
            else:
                self.logger.warning(
                    "Optimization failed after %.2f seconds. Errors: %s",
                    duration,
                    ", ".join(result.errors)
                )
            
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during optimization: {str(e)}"
            self.logger.exception(error_msg)
            
            # Update result with error information
            result.status = OptimizationStatus.FAILED
            result.errors.append(error_msg)
            result.metadata.update({
                'error': str(e),
                'execution_time_seconds': time_module.time() - start_time,
                'end_time': datetime.utcnow().isoformat()
            })
            
            return result
    
    async def _prepare_optimization_data(
        self,
        vehicles: List[VehicleRequest],
        jobs: List[JobRequest],
        vehicle_schedules: Dict[str, List[VehicleSchedule]],
        optimization_type: OptimizationType,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare data for optimization.
        
        Args:
            vehicles: List of vehicle requests
            jobs: List of job requests
            vehicle_schedules: Vehicle schedules by vehicle ID
            optimization_type: Type of optimization
            options: Additional optimization options
            
        Returns:
            Dictionary containing all data needed for optimization
        """
        # Collect all unique locations
        locations = []
        location_to_idx = {}
        
        # Add vehicle start/end locations
        for vehicle in vehicles:
            # Add start location
            loc_key = f"{vehicle.id}_start"
            if loc_key not in location_to_idx:
                location_to_idx[loc_key] = len(locations)
                locations.append((vehicle.start_location.lat, vehicle.start_location.lng))
                
            # Add end location if different from start
            if vehicle.end_location and vehicle.end_location != vehicle.start_location:
                loc_key = f"{vehicle.id}_end"
                if loc_key not in location_to_idx:
                    location_to_idx[loc_key] = len(locations)
                    locations.append((vehicle.end_location.lat, vehicle.end_location.lng))
        
        # Add job locations
        job_indices = {}
        for job in jobs:
            loc_key = f"job_{job.id}"
            if loc_key not in location_to_idx:
                location_to_idx[loc_key] = len(locations)
                locations.append((job.location.lat, job.location.lng))
            job_indices[job.id] = location_to_idx[loc_key]
        
        # Get distance and duration matrices
        profile = options.get('profile', 'car')
        matrices = await self._get_matrices(locations, profile=profile)
        
        return {
            'vehicles': vehicles,
            'jobs': jobs,
            'vehicle_schedules': vehicle_schedules,
            'optimization_type': optimization_type,
            'options': options,
            'locations': locations,
            'location_to_idx': location_to_idx,
            'job_indices': job_indices,
            'distance_matrix': matrices['distances'],
            'duration_matrix': matrices['times']
        }
    
    async def _solve_optimization(
        self,
        optimization_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Solve the optimization problem using OR-Tools.
        
        Args:
            optimization_data: Prepared optimization data
            
        Returns:
            Raw optimization result with routes and metrics
        """
        try:
            # Extract data
            vehicles = optimization_data['vehicles']
            jobs = optimization_data['jobs']
            vehicle_schedules = optimization_data['vehicle_schedules']
            distance_matrix = optimization_data['distance_matrix']
            duration_matrix = optimization_data['duration_matrix']
            job_indices = optimization_data['job_indices']
            location_to_idx = optimization_data['location_to_idx']
            
            # Create routing index manager
            num_locations = len(location_to_idx)
            num_vehicles = len(vehicles)
            
            # Create routing index manager
            manager = RoutingIndexManager(
                num_locations,
                num_vehicles,
                [location_to_idx[f"{v.id}_start"] for v in vehicles],  # starts
                [location_to_idx.get(f"{v.id}_end", location_to_idx[f"{v.id}_start"]) for v in vehicles]  # ends
            )
            
            # Create routing model
            routing = RoutingModel(manager)
            
            # Add distance and duration callbacks
            def distance_callback(from_index: int, to_index: int) -> int:
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return int(distance_matrix[from_node][to_node])
            
            def duration_callback(from_index: int, to_index: int) -> int:
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return int(duration_matrix[from_node][to_node])
            
            # Register callbacks
            transit_callback_index = routing.RegisterTransitCallback(
                duration_callback if optimization_data['optimization_type'] == OptimizationType.DURATION 
                else distance_callback
            )
            
            # Set arc cost evaluator
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
            
            # Add time dimension
            max_slack = 30 * 60  # 30 minutes max slack time
            max_time = 24 * 3600  # 24 hours in seconds
            
            def time_callback(from_index: int, to_index: int) -> int:
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return int(duration_matrix[from_node][to_node])
            
            time_callback_index = routing.RegisterTransitCallback(time_callback)
            
            # Add time dimension with time windows
            routing.AddDimension(
                time_callback_index,
                max_slack,  # allow waiting time
                max_time,  # maximum time per vehicle
                False,  # don't force start cumul to zero
                'Time'
            )
            time_dimension = routing.GetDimensionOrDie('Time')
            
            # Add time window constraints for jobs
            for job in jobs:
                if job.time_window:
                    idx = job_indices[job.id]
                    index = manager.NodeToIndex(idx)
                    time_dimension.CumulVar(index).SetRange(
                        job.time_window.start_seconds,
                        job.time_window.end_seconds
                    )
            
            # Add vehicle time windows and breaks
            for vehicle_idx, vehicle in enumerate(vehicles):
                # Set time window for vehicle's start/end nodes
                start_idx = manager.NodeToIndex(location_to_idx[f"{vehicle.id}_start"])
                end_idx = manager.NodeToIndex(location_to_idx.get(f"{vehicle.id}_end", location_to_idx[f"{vehicle.id}_start"]))
                
                # Set time window for vehicle's start location
                time_dimension.CumulVar(start_idx).SetRange(
                    vehicle.time_window.start_seconds if vehicle.time_window else 0,
                    vehicle.time_window.end_seconds if vehicle.time_window else max_time
                )
                
                # Set time window for vehicle's end location
                time_dimension.CumulVar(end_idx).SetRange(
                    vehicle.time_window.start_seconds if vehicle.time_window else 0,
                    vehicle.time_window.end_seconds if vehicle.time_window else max_time
                )
                
                # Add breaks
                if vehicle.breaks:
                    for break_def in vehicle.breaks:
                        break_intervals = []
                        for time_window in break_def.time_windows:
                            break_intervals.append(
                                routing.solver().FixedDurationIntervalVar(
                                    time_window.start_seconds,
                                    time_window.end_seconds,
                                    break_def.duration,
                                    False,  # optional
                                    f'vehicle_{vehicle.id}_break_{break_def.id}'
                                )
                            )
                        if break_intervals:
                            routing.AddDisjunction([break_intervals[0].PerformedExpr().Var()], 0)
                            routing.solver().Add(
                                routing.ActiveVar(vehicle_idx) == 1
                            )
            
            # Set search parameters
            search_parameters = DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_parameters.time_limit.seconds = MAX_OPTIMIZATION_TIME_SECONDS
            
            # Solve the problem
            solution = routing.SolveWithParameters(search_parameters)
            
            if not solution:
                return {
                    'status': 'failed',
                    'message': 'No solution found',
                    'routes': []
                }
            
            # Extract solution
            routes = []
            total_distance = 0
            total_duration = 0
            
            for vehicle_idx in range(num_vehicles):
                route = []
                index = routing.Start(vehicle_idx)
                route_distance = 0
                route_duration = 0
                
                while not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    next_node_index = manager.IndexToNode(solution.Value(routing.NextVar(index)))
                    route_distance += distance_matrix[node_index][next_node_index]
                    route_duration += duration_matrix[node_index][next_node_index]
                    
                    route.append({
                        'location': next_node_index,
                        'arrival_time': solution.Min(time_dimension.CumulVar(index)),
                        'departure_time': solution.Min(time_dimension.CumulVar(index))
                    })
                    
                    index = solution.Value(routing.NextVar(index))
                
                routes.append({
                    'vehicle_id': vehicles[vehicle_idx].id,
                    'distance': route_distance,
                    'duration': route_duration,
                    'stops': route
                })
                
                total_distance += route_distance
                total_duration += route_duration
            
            return {
                'status': 'success',
                'routes': routes,
                'total_distance': total_distance,
                'total_duration': total_duration,
                'total_cost': total_duration  # Simple cost model - could be enhanced
            }
            
        except Exception as e:
            self.logger.error(f"Error in optimization solver: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e),
                'routes': []
            }
    
    def _format_optimization_result(
        self,
        result: Dict[str, Any],
        optimization_data: Dict[str, Any]
    ) -> OptimizationResult:
        """
        Format the optimization result into a standard format.
        
        Args:
            result: Raw optimization result
            optimization_data: Optimization data
            
        Returns:
            Formatted optimization result
        """
        return OptimizationResult(
            status=OptimizationStatus.COMPLETED,
            routes=result.get('routes', []),
            total_distance=result.get('total_distance', 0.0),
            total_duration=result.get('total_duration', 0.0),
            total_cost=result.get('total_cost', 0.0),
            optimization_type=optimization_data.get('optimization_type', OptimizationType.DURATION),
            metadata={
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'num_vehicles': len(optimization_data.get('vehicles', [])),
                'num_jobs': len(optimization_data.get('jobs', []))
            }
        )
    
    def _create_data_model(
        self,
        vehicles: List[Vehicle],
        jobs: List[Job],
        distance_matrix: List[List[float]],
        duration_matrix: List[List[float]],
        optimization_type: str = 'duration'
    ) -> Dict[str, Any]:
        """
        Create the data model for the OR-Tools solver.
        
        Args:
            vehicles: List of Vehicle objects
            jobs: List of Job objects
            distance_matrix: Distance matrix in meters
            duration_matrix: Duration matrix in seconds
            optimization_type: 'distance' or 'duration'
            
        Returns:
            Data model for OR-Tools
        """
        # The first location is the depot (vehicle start location)
        data = {}
        data['distance_matrix'] = distance_matrix
        data['duration_matrix'] = duration_matrix
        data['num_vehicles'] = len(vehicles)
        data['depot'] = 0  # First location is the depot
        
        # Time windows for jobs (convert datetime to seconds since midnight)
        def time_to_seconds(dt: datetime) -> int:
            return dt.hour * 3600 + dt.minute * 60 + dt.second
            
        data['time_windows'] = []
        for job in jobs:
            if job.time_window:
                start = time_to_seconds(job.time_window[0])
                end = time_to_seconds(job.time_window[1])
                data['time_windows'].append((start, end))
            else:
                # Default time window if not specified
                data['time_windows'].append((0, 24 * 3600))  # 24 hours
                
        # Service times (in seconds)
        data['service_times'] = [job.duration for job in jobs]
        
        # Vehicle capacities (if needed)
        data['vehicle_capacities'] = [1] * len(vehicles)  # Default capacity of 1 per vehicle
        
        # Demands (if needed)
        data['demands'] = [1] * len(jobs)  # Each job has a demand of 1
        
        # Optimization type
        data['optimization_type'] = optimization_type
        
        return data
    
    def _format_solution(
        self,
        data: Dict[str, Any],
        manager: RoutingIndexManager,
        routing: RoutingModel,
        solution: Any,  # pywrapcp.Assignment
        vehicles: List[Vehicle],
        jobs: List[Job]
    ) -> Dict[str, Any]:
        """
        Format the OR-Tools solution into a more usable format.
        
        Args:
            data: Data model used for the optimization
            manager: OR-Tools routing index manager
            routing: OR-Tools routing model
            solution: OR-Tools solution
            vehicles: List of Vehicle objects
            jobs: List of Job objects
            
        Returns:
            Formatted solution
        """
        time_dimension = routing.GetDimensionOrDie('Time')
        routes = []
        total_distance = 0
        total_duration = 0
        
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            route = {
                'vehicle_id': vehicles[vehicle_id].id,
                'stops': [],
                'total_distance': 0,
                'total_duration': 0,
                'start_time': None,
                'end_time': None
            }
            
            prev_index = index
            route_distance = 0
            route_duration = 0
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                next_index = solution.Value(routing.NextVar(index))
                next_node_index = manager.IndexToNode(next_index)
                
                # Add distance and duration
                route_distance += data['distance_matrix'][node_index][next_node_index]
                route_duration += data['duration_matrix'][node_index][next_node_index]
                
                # Add stop to route
                if node_index > 0:  # Skip depot
                    # Calculate job index accounting for multiple depots
                    num_depots = len(vehicles)
                    job_idx = node_index - num_depots
                    
                    # Only process if it's a valid job index
                    if 0 <= job_idx < len(jobs):
                        # Ensure indices are within matrix bounds
                        from_node = manager.IndexToNode(prev_index)
                        to_node = manager.IndexToNode(index)
                        
                        # Ensure we don't go out of bounds
                        max_node = len(data['distance_matrix']) - 1
                        from_node = min(from_node, max_node)
                        to_node = min(to_node, max_node)
                        
                        stop = {
                            'job_id': jobs[job_idx].id,
                            'location': jobs[job_idx].location,
                            'distance_from_prev': data['distance_matrix'][from_node][to_node],
                            'duration_from_prev': data['duration_matrix'][from_node][to_node],
                            'service_time': jobs[job_idx].duration,
                            'arrival_time': route_duration,
                            'departure_time': route_duration + jobs[job_idx].duration
                        }
                        route['stops'].append(stop)
                
                prev_index = index
                index = next_index
            
            route['total_distance'] = route_distance
            route['total_duration'] = route_duration
            routes.append(route)
            
            total_distance += route_distance
            total_duration += route_duration
        
        return {
            'status': 'success',
            'routes': routes,
            'total_distance': total_distance,
            'total_duration': total_duration,
            'optimization_type': data['optimization_type'],
            'optimization_timestamp': datetime.utcnow().isoformat()
        }
    
    async def optimize_routes(
        self,
        jobs: List[Job],
        optimization_type: str = 'duration',
        vehicles: List[Vehicle] = None,
        profile: str = 'car',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimize routes for the given jobs using GraphHopper and OR-Tools.
        
        Args:
            jobs: List of Job objects to be assigned to vehicles
            optimization_type: Type of optimization ('distance' or 'duration')
            vehicles: Optional list of Vehicle objects (default: single vehicle at origin)
            profile: Vehicle profile (car, bike, foot, etc.)
            **kwargs: Additional optimization parameters
            
        Returns:
            Dict containing the optimization solution with routes and metrics
            
        Raises:
            RouteOptimizationError: If optimization fails
        """
        if optimization_type not in ['distance', 'duration']:
            raise ValueError("optimization_type must be either 'distance' or 'duration'")
            
        if not jobs:
            raise RouteOptimizationError("No jobs provided for optimization")
            
        # If no vehicles provided, create a default one
        if not vehicles:
            # Use the first job's location as the depot
            depot_location = jobs[0].location if jobs else (0, 0)
            vehicles = [
                Vehicle(
                    id="default_vehicle",
                    start_location=depot_location,
                    capacity=10  # Default capacity
                )
            ]
        
        try:
            # Prepare locations for distance matrix (vehicles + jobs)
            locations = [v.start_location for v in vehicles]
            locations.extend(job.location for job in jobs)
            
            # Get distance and duration matrices
            logger.info(f"Fetching matrices for {len(locations)} locations...")
            matrices = await self._get_matrices(locations, profile=profile)
            
            # Create data model for OR-Tools
            data = self._create_data_model(
                vehicles=vehicles,
                jobs=jobs,
                distance_matrix=matrices['distances'],
                duration_matrix=matrices['times'],
                optimization_type=optimization_type
            )
            
            # Create routing index manager
            manager = RoutingIndexManager(
                len(data['distance_matrix']),
                data['num_vehicles'],
                [data['depot']] * data['num_vehicles'],  # All vehicles start at depot
                [data['depot']] * data['num_vehicles']    # All vehicles end at depot
            )
            
            # Create routing model
            routing = RoutingModel(manager)
            
            # Define cost of each arc based on optimization type
            def distance_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return data['distance_matrix'][from_node][to_node]
                
            def duration_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return data['duration_matrix'][from_node][to_node]
            
            # Register callbacks
            transit_callback_index = routing.RegisterTransitCallback(
                duration_callback if optimization_type == 'duration' else distance_callback
            )
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
            
            # Add time dimension
            time_callback_index = routing.RegisterTransitCallback(duration_callback)
            routing.AddDimension(
                time_callback_index,
                30,  # allow waiting time
                24 * 3600,  # maximum time per vehicle (24 hours)
                False,  # Don't force start cumul to zero
                'Time'
            )
            
            # Add time window constraints
            time_dimension = routing.GetDimensionOrDie('Time')
            for location_idx, time_window in enumerate(data['time_windows']):
                if location_idx < len(vehicles):  # Skip depot/vehicle locations
                    continue
                index = manager.NodeToIndex(location_idx)
                time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
            
            # Set solution strategy
            search_parameters = DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            search_parameters.time_limit.seconds = self.timeout
            
            # Solve the problem
            logger.info("Solving routing problem with OR-Tools...")
            solution = routing.SolveWithParameters(search_parameters)
            
            if not solution:
                raise RouteOptimizationError("No solution found for the given constraints")
                
            # Format and return the solution
            return self._format_solution(data, manager, routing, solution, vehicles, jobs)
            
        except Exception as e:
            logger.error(f"Error in route optimization: {str(e)}", exc_info=True)
            raise RouteOptimizationError(f"Route optimization failed: {str(e)}")
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
