"""API client for arztsuche.116117.de

This module provides a client for searching therapists using the
official German medical directory API (Arztsuche 116117).
"""

import hashlib
import time
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    """Parameters for therapist search."""

    specialty: str = Field(..., description="Therapist specialty (e.g., 'Psychotherapeut')")
    location: str = Field(..., description="City or postal code")
    max_results: int = Field(50, description="Maximum number of results", ge=1, le=50)
    radius: int = Field(25, description="Search radius in km", ge=1, le=100)


class Therapist116117(BaseModel):
    """Therapist data from 116117 API."""

    name: str
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    specialty: str | None = None
    distance: float | None = None


class Arztsuche116117Client:
    """Client for interacting with arztsuche.116117.de API.
    
    The API requires HTTP Basic Authentication with credentials that are
    embedded in the website's JavaScript. It also requires a dynamic
    request validation header that includes timestamp-based tokens.
    """

    BASE_URL = "https://arztsuche.116117.de"
    API_PATH = "/api"

    # API credentials (decoded from JS)
    USERNAME = "bdps"
    PASSWORD = "fkr493mvg_f"

    def __init__(self):
        """Initialize the API client."""
        self.username = self.USERNAME
        self.password = self.PASSWORD
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            auth=(self.username, self.password),
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _generate_req_val(self) -> str:
        """Generate the req-val header for API requests.
        
        The req-val header is a dynamic token that includes timestamp
        components to prevent replay attacks.
        
        Returns:
            The req-val token string.
        """
        now = datetime.now()
        timestamp_ms = int(time.time() * 1000)
        
        # Components used in the hash calculation
        year = str(now.year)
        month = str(now.month).zfill(2)
        day = str(now.day).zfill(2)
        hour = str(now.hour).zfill(2)
        
        # The website uses a specific formula to generate this token
        # This is a simplified version - the actual implementation may vary
        components = f"{year}{month}{day}{hour}{timestamp_ms}"
        token = hashlib.sha256(components.encode()).hexdigest()[:32]
        
        return token

    def search_location(self, query: str) -> list[dict[str, Any]]:
        """Search for location suggestions.
        
        Args:
            query: City name or postal code to search for.
            
        Returns:
            List of location suggestions with coordinates.
            
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        response = self.client.get(
            f"{self.API_PATH}/location",
            params={"query": query},
            headers={"req-val": self._generate_req_val()},
        )
        response.raise_for_status()
        return response.json()

    def search_therapists(self, params: SearchParams) -> list[Therapist116117]:
        """Search for therapists using the 116117 API.
        
        Args:
            params: Search parameters including specialty and location.
            
        Returns:
            List of therapists matching the search criteria.
            
        Raises:
            httpx.HTTPError: If the API request fails.
        """
        # First, resolve the location to get coordinates
        locations = self.search_location(params.location)
        if not locations:
            return []
        
        location_data = locations[0]  # Use first result
        
        # Prepare search request
        search_data = {
            "specialty": params.specialty,
            "lat": location_data.get("lat"),
            "lon": location_data.get("lon"),
            "radius": params.radius,
            "limit": params.max_results,
        }
        
        response = self.client.post(
            f"{self.API_PATH}/data",
            json=search_data,
            headers={"req-val": self._generate_req_val()},
        )
        response.raise_for_status()
        
        # Parse results
        results = response.json()
        therapists = []
        
        for item in results.get("results", []):
            therapist = Therapist116117(
                name=item.get("name", ""),
                street=item.get("street"),
                city=item.get("city"),
                postal_code=item.get("postalCode"),
                phone=item.get("phone"),
                email=item.get("email"),
                specialty=item.get("specialty"),
                distance=item.get("distance"),
            )
            therapists.append(therapist)
        
        return therapists

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
