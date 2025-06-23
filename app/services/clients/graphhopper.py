import httpx
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class GraphHopperClientError(Exception):
    """Custom exception for GraphHopper client errors"""
    pass

class GraphHopperClient:
    """
    A client for interacting with the GraphHopper API.
    Handles all communication with the GraphHopper services.
    """
    
    def __init__(self, api_key: str = None, base_url: str = None, timeout: int = 30):
        """
        Initialize the GraphHopper client.
        
        Args:
            api_key: GraphHopper API key
            base_url: Base URL for the GraphHopper API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or settings.GRAPHHOPPER_API_KEY
        self.base_url = base_url or settings.GRAPHHOPPER_BASE_URL
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError("GraphHopper API key is required")
        if not self.base_url:
            raise ValueError("GraphHopper base URL is required")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP request to the GraphHopper API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            JSON response from the API
            
        Raises:
            GraphHopperClientError: If the request fails
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        params = kwargs.get('params', {})
        params['key'] = self.api_key
        kwargs['params'] = params
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"GraphHopper API error ({e.response.status_code}): {e.response.text}"
            logger.error(error_msg)
            raise GraphHopperClientError(error_msg)
        except Exception as e:
            error_msg = f"Error making request to GraphHopper API: {str(e)}"
            logger.error(error_msg)
            raise GraphHopperClientError(error_msg)
    
    async def get_distance_matrix(
        self,
        locations: List[Tuple[float, float]],
        profile: str = 'car',
        out_arrays: List[str] = None
    ) -> Dict[str, List[List[float]]]:
        """
        Get distance and duration matrix from GraphHopper's Matrix API.
        
        Args:
            locations: List of (lat, lon) tuples
            profile: Vehicle profile (car, bike, foot, etc.)
            out_arrays: List of matrix types to return (distances, times, weights)
            
        Returns:
            Dict containing the requested matrices
            
        Raises:
            GraphHopperClientError: If the request fails
        """
        if out_arrays is None:
            out_arrays = ['distances', 'times']
            
        # Convert locations to strings
        point_params = [f"{lat},{lon}" for lat, lon in locations]
        
        params = {
            'profile': profile,
            'out_array': out_arrays,
            'point': point_params,
            'type': 'json'
        }
        
        try:
            response = await self._make_request(
                'GET',
                'matrix',
                params=params
            )
            
            # Ensure we have the expected response format
            if not all(key in response for key in out_arrays):
                raise GraphHopperClientError("Unexpected response format from GraphHopper Matrix API")
                
            return {key: response[key] for key in out_arrays}
            
        except Exception as e:
            logger.error(f"Error getting distance matrix: {str(e)}")
            raise GraphHopperClientError(f"Failed to get distance matrix: {str(e)}")


# Global instance of the GraphHopper client
graphhopper_client = GraphHopperClient()
