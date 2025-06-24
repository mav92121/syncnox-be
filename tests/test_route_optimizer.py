import pytest
import asyncio
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch, MagicMock

from app.schemas.optimization import (
    VehicleBreak, VehicleCosts, VehicleSkills, JobRequirements
)
from app.api.v1.endpoints.optimization import Location, VehicleRequest, JobRequest, TimeWindow
from app.services.route_optimizer import RouteOptimizer

# Type alias for location tuples
LocationTuple = tuple[float, float]  # (latitude, longitude)

# Test data
TEST_API_KEY = "test_api_key"
TEST_LOCATIONS = [
    (51.534377, -0.087891),  # London
    (51.5074, -0.1278),     # Central London
    (51.4536, -2.5979),     # Bristol
    (53.4808, -2.2426),     # Manchester
]

# Fixtures
@pytest.fixture
def route_optimizer():
    # Create a mock GraphHopperClient
    mock_gh_client = AsyncMock()
    mock_gh_client.get_distance_matrix = AsyncMock(return_value={
        'distances': [[0, 1000, 2000], [1000, 0, 1000], [2000, 1000, 0]],
        'times': [[0, 60, 120], [60, 0, 60], [120, 60, 0]]
    })
    
    return RouteOptimizer(api_key="test_api_key", graphhopper_client=mock_gh_client)

@pytest.fixture
def test_vehicles():
    return [
        VehicleRequest(
            id="v1",
            type="car",
            start_location=Location(lat=51.534377, lng=-0.087891),
            costs=VehicleCosts(
                fixed=1000.0,
                distance=0.1,
                time=0.5,
                early=0.0
            ),
            skills=VehicleSkills(
                required_licenses=["standard"],
                can_carry_hazardous=False,
                can_carry_refrigerated=False
            ),
            breaks=[
                VehicleBreak(
                    id="lunch",
                    duration=3600,  # 1 hour
                    time_windows=[
                        TimeWindow(
                            start=time(12, 0, 0),  # 12:00 PM
                            end=time(14, 0, 0)      # 2:00 PM
                        )
                    ]
                )
            ]
        )
    ]

@pytest.fixture
def test_jobs():
    return [
        JobRequest(
            id="j1",
            location=Location(lat=51.5074, lng=-0.1278),
            duration=1800,  # 30 minutes
            time_window=TimeWindow(
                start=time(9, 0, 0),   # 9:00 AM
                end=time(17, 0, 0)     # 5:00 PM
            ),
            requirements=JobRequirements(
                skills=["standard"],
                max_weight=500,
                max_volume=2.0
            )
        ),
        JobRequest(
            id="j2",
            location=Location(lat=51.4536, lng=-2.5979),
            duration=2700,  # 45 minutes
            time_window=TimeWindow(
                start=time(10, 0, 0),  # 10:00 AM
                end=time(16, 0, 0)     # 4:00 PM
            ),
            requirements=JobRequirements(
                skills=["standard"],
                max_weight=300,
                max_volume=1.5
            )
        )
    ]

# Tests
@pytest.mark.asyncio
async def test_optimize_routes_success(route_optimizer, test_vehicles, test_jobs):
    """Test successful route optimization."""
    # Mock the GraphHopper client
    with patch('app.services.route_optimizer.GraphHopperClient') as mock_gh:
        # Setup mock response
        mock_client = AsyncMock()
        mock_client.get_distance_matrix.return_value = {
            'distances': [
                [0, 5000, 100000, 200000],
                [5000, 0, 95000, 195000],
                [100000, 95000, 0, 100000],
                [200000, 195000, 100000, 0]
            ],
            'times': [
                [0, 600, 3600, 7200],
                [600, 0, 3000, 6600],
                [3600, 3000, 0, 3600],
                [7200, 6600, 3600, 0]
            ]
        }
        mock_gh.return_value.__aenter__.return_value = mock_client
        
        # Create a new RouteOptimizer with the mocked client
        optimizer = RouteOptimizer(api_key="test_api_key", graphhopper_client=mock_gh.return_value)
        
        # Run optimization with explicit parameter names
        result = await optimizer.optimize_routes(
            vehicles=test_vehicles,
            jobs=test_jobs,
            optimization_type=OptimizationType.DURATION
        )
        
        # Assertions
        assert result.status == OptimizationStatus.COMPLETED
        assert len(result.routes) > 0
        assert result.total_distance > 0
        assert result.total_duration > 0
        assert result.total_cost > 0
        
        # Verify the route includes all jobs
        assigned_job_ids = {job['id'] for route in result.routes for job in route.get('jobs', [])}
        assert all(job.id in assigned_job_ids for job in test_jobs)

@pytest.mark.asyncio
async def test_optimize_routes_with_planning_horizon(route_optimizer, test_vehicles, test_jobs):
    """Test route optimization with a planning horizon."""
    # Create a planning horizon for the next 7 days
    today = date.today()
    planning_horizon = PlanningHorizon(
        start_date=today,
        end_date=today + timedelta(days=6),  # 1 week
        working_days=[0, 1, 2, 3, 4],  # Monday to Friday
        working_hours=(9 * 3600, 17 * 3600)  # 9 AM to 5 PM
    )
    
    # Mock the GraphHopper client
    with patch('app.services.route_optimizer.GraphHopperClient') as mock_gh:
        # Setup mock response
        mock_client = AsyncMock()
        mock_client.get_distance_matrix.return_value = {
            'distances': [
                [0, 5000, 100000, 200000],
                [5000, 0, 95000, 195000],
                [100000, 95000, 0, 100000],
                [200000, 195000, 100000, 0]
            ],
            'times': [
                [0, 600, 3600, 7200],
                [600, 0, 3000, 6600],
                [3600, 3000, 0, 3600],
                [7200, 6600, 3600, 0]
            ]
        }
        mock_gh.return_value.__aenter__.return_value = mock_client
        
        # Create a new RouteOptimizer with the mocked client
        optimizer = RouteOptimizer(api_key="test_api_key", graphhopper_client=mock_gh.return_value)
        
        # Run optimization with planning horizon and explicit parameter names
        result = await optimizer.optimize_routes(
            vehicles=test_vehicles,
            jobs=test_jobs,
            optimization_type=OptimizationType.DURATION,
            planning_horizon=planning_horizon
        )
        
        # Assertions
        assert result.status == OptimizationStatus.COMPLETED
        assert len(result.routes) > 0
        
        # Verify the planning horizon was respected
        for route in result.routes:
            route_date = datetime.fromisoformat(route['date']).date()
            assert route_date >= planning_horizon.start_date
            assert route_date <= planning_horizon.end_date
            assert route_date.weekday() in planning_horizon.working_days

@pytest.mark.asyncio
async def test_optimize_routes_no_vehicles(route_optimizer, test_jobs):
    """Test optimization with no vehicles raises an error."""
    with pytest.raises(ValueError, match="At least one vehicle must be provided"):
        await route_optimizer.optimize_routes(vehicles=[], jobs=test_jobs, optimization_type="distance")

@pytest.mark.asyncio
async def test_optimize_routes_no_jobs(route_optimizer, test_vehicles):
    """Test optimization with no jobs returns empty result."""
    result = await route_optimizer.optimize_routes(vehicles=test_vehicles, jobs=[])
    
    assert len(result.routes) == 0
    assert result.total_distance == 0
    assert result.total_duration == 0
    assert result.status == "success"

@pytest.mark.asyncio
async def test_optimize_routes_api_error(route_optimizer, test_vehicles, test_jobs):
    """Test handling of GraphHopper API errors."""
    with patch('app.services.route_optimizer.GraphHopperClient') as mock_gh:
        # Setup mock to raise an error
        mock_client = AsyncMock()
        mock_client.get_distance_matrix.side_effect = Exception("API Error")
        mock_gh.return_value.__aenter__.return_value = mock_client
        
        # Create a new RouteOptimizer with the mocked client
        optimizer = RouteOptimizer(api_key="test_api_key", graphhopper_client=mock_gh.return_value)
        
        # Run optimization with explicit parameter names
        result = await optimizer.optimize_routes(
            vehicles=test_vehicles,
            jobs=test_jobs,
            optimization_type=OptimizationType.DURATION
        )
        
        # Assertions
        assert result.status == OptimizationStatus.FAILED
        assert len(result.errors) > 0
        assert isinstance(result.errors[0], str)

@pytest.mark.asyncio
async def test_get_matrices_caching(route_optimizer):
    """Test that distance/duration matrices are properly cached."""
    locations = [(51.0, -0.1), (51.1, -0.1), (51.2, -0.1)]
    profile = 'car'
    
    # Get the mock client from the fixture
    mock_gh_client = route_optimizer._gh_client
    
    # First call - should hit the API
    result1 = await route_optimizer._get_matrices(locations, profile)
    mock_gh_client.get_distance_matrix.assert_awaited_once_with(
        locations=locations,
        profile=profile,
        out_arrays=['distances', 'times']
    )
    
    # Reset the mock call count
    mock_gh_client.get_distance_matrix.reset_mock()
    
    # Second call with same parameters - should use cache
    result2 = await route_optimizer._get_matrices(locations, profile)
    mock_gh_client.get_distance_matrix.assert_not_awaited()
    assert result1 == result2
    
    # Call with force_refresh=True - should hit the API again
    result3 = await route_optimizer._get_matrices(locations, profile, force_refresh=True)
    mock_gh_client.get_distance_matrix.assert_awaited_once_with(
        locations=locations,
        profile=profile,
        out_arrays=['distances', 'times']
    )
    
    # Different locations - should hit the API again
    mock_gh_client.get_distance_matrix.reset_mock()
    new_locations = locations + [(51.3, -0.1)]
    await route_optimizer._get_matrices(new_locations, profile)
    mock_gh_client.get_distance_matrix.assert_awaited_once_with(
        locations=new_locations,
        profile=profile,
        out_arrays=['distances', 'times']
    )

# Run tests
if __name__ == "__main__":
    pytest.main(["-v", "tests/test_route_optimizer.py"])
