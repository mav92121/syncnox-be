import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# Local imports
from .clients.graphhopper import graphhopper_client, GraphHopperClient, GraphHopperClientError
from app.core.config import settings

# Type aliases
Location = Tuple[float, float]  # (latitude, longitude)
TimeWindow = Tuple[datetime, datetime]  # (start_time, end_time)

logger = logging.getLogger(__name__)

class RouteOptimizationError(Exception):
    """Custom exception for route optimization errors"""
    pass

class Job:
    """Represents a job or stop that needs to be visited by a vehicle."""
    def __init__(self, 
                 job_id: str, 
                 location: Location, 
                 duration: int = 300, 
                 time_window: Optional[TimeWindow] = None,
                 priority: int = 1):
        """
        Initialize a job.
        
        Args:
            job_id: Unique identifier for the job
            location: Tuple of (latitude, longitude)
            duration: Service duration in seconds (default: 300)
            time_window: Optional time window as (start_time, end_time)
            priority: Job priority (1-10, higher is more important)
        """
        self.id = job_id
        self.location = location  # (lat, lon)
        self.duration = duration  # in seconds
        self.time_window = time_window
        self.priority = priority

class Vehicle:
    """Represents a vehicle that can perform jobs."""
    def __init__(self, 
                 id: str, 
                 start_location: Location,
                 capacity: int = 1,
                 time_window: Optional[TimeWindow] = None):
        """
        Initialize a vehicle.
        
        Args:
            id: Unique identifier for the vehicle
            start_location: Starting location as (latitude, longitude)
            capacity: Vehicle capacity (default: 1)
            time_window: Optional time window as (start_time, end_time)
        """
        self.id = id
        self.start_location = start_location  # (lat, lon)
        self.capacity = capacity
        self.time_window = time_window

class RouteOptimizer:
    """
    A service for optimizing routes using GraphHopper and OR-Tools.
    Handles the optimization logic while delegating API calls to the GraphHopper client.
    """
    
    def __init__(self, graphhopper_client: GraphHopperClient = None, timeout: int = 30):
        """
        Initialize the route optimizer.
        
        Args:
            graphhopper_client: Instance of GraphHopperClient (default: global instance)
            timeout: Optimization timeout in seconds
        """
        from .clients.graphhopper import graphhopper_client as default_gh_client
        self.graphhopper = graphhopper_client if graphhopper_client is not None else default_gh_client
        self.timeout = timeout
    
    async def _get_matrices(
        self,
        locations: List[Tuple[float, float]],
        profile: str = 'car'
    ) -> Dict[str, List[List[float]]]:
        """
        Get both distance and duration matrices from GraphHopper.
        
        Args:
            locations: List of (lat, lon) tuples
            profile: Vehicle profile (car, bike, foot, etc.)
            
        Returns:
            Dict containing 'distances' and 'times' matrices
        """
        try:
            return await self.graphhopper.get_distance_matrix(
                locations=locations,
                profile=profile,
                out_arrays=['distances', 'times']
            )
        except GraphHopperClientError as e:
            logger.error(f"Error getting matrices from GraphHopper: {str(e)}")
            raise RouteOptimizationError(f"Failed to get distance/duration matrices: {str(e)}")
    
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
        manager: pywrapcp.RoutingIndexManager,
        routing: pywrapcp.RoutingModel,
        solution: pywrapcp.Assignment,
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
            manager = pywrapcp.RoutingIndexManager(
                len(data['distance_matrix']),
                data['num_vehicles'],
                [data['depot']] * data['num_vehicles'],  # All vehicles start at depot
                [data['depot']] * data['num_vehicles']    # All vehicles end at depot
            )
            
            # Create routing model
            routing = pywrapcp.RoutingModel(manager)
            
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
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
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
