#!/usr/bin/env python3
"""Test script for arztsuche.116117.de API client.

This script demonstrates how to:
1. Search for locations
2. Search for therapists by specialty and location
3. Handle the API authentication and dynamic headers
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from therapist_finder.parsers.arztsuche_api import (
        Arztsuche116117Client,
        SearchParams,
    )
except ImportError:
    print("Error: httpx is required. Install with: poetry add httpx")
    sys.exit(1)


def test_location_search():
    """Test location search functionality."""
    print("\n" + "=" * 60)
    print("Testing Location Search")
    print("=" * 60)

    with Arztsuche116117Client() as client:
        # Test with city name
        print("\nSearching for: Berlin")
        results = client.search_location("Berlin")
        print(f"Found {len(results)} results")
        for i, loc in enumerate(results[:3], 1):
            print(f"{i}. {loc.get('name', 'N/A')} - Lat: {loc.get('lat')}, Lon: {loc.get('lon')}")

        # Test with postal code
        print("\nSearching for: 10115")
        results = client.search_location("10115")
        print(f"Found {len(results)} results")
        for i, loc in enumerate(results[:3], 1):
            print(f"{i}. {loc.get('name', 'N/A')} - Lat: {loc.get('lat')}, Lon: {loc.get('lon')}")


def test_therapist_search():
    """Test therapist search functionality."""
    print("\n" + "=" * 60)
    print("Testing Therapist Search")
    print("=" * 60)

    params = SearchParams(
        specialty="Psychotherapeut",
        location="Berlin",
        radius=10,
        max_results=5,
    )

    print(f"\nSearch parameters:")
    print(f"  Specialty: {params.specialty}")
    print(f"  Location: {params.location}")
    print(f"  Radius: {params.radius} km")
    print(f"  Max results: {params.max_results}")

    with Arztsuche116117Client() as client:
        try:
            therapists = client.search_therapists(params)
            print(f"\nFound {len(therapists)} therapists:")
            print("-" * 60)

            for i, t in enumerate(therapists, 1):
                print(f"\n{i}. {t.name}")
                if t.street:
                    print(f"   Address: {t.street}")
                if t.postal_code or t.city:
                    print(f"            {t.postal_code or ''} {t.city or ''}")
                if t.phone:
                    print(f"   Phone: {t.phone}")
                if t.email:
                    print(f"   Email: {t.email}")
                if t.distance is not None:
                    print(f"   Distance: {t.distance:.1f} km")

        except Exception as e:
            print(f"\nError during search: {e}")
            import traceback
            traceback.print_exc()


def test_authentication():
    """Test API authentication."""
    print("\n" + "=" * 60)
    print("Testing API Authentication")
    print("=" * 60)

    client = Arztsuche116117Client()
    print(f"\nUsername (decoded): {client.username[:8]}...")
    print(f"Password (decoded): {client.password[:8]}...")
    print(f"Base URL: {client.BASE_URL}")
    print(f"API Path: {client.API_PATH}")
    
    # Test req-val generation
    req_val = client._generate_req_val()
    print(f"Generated req-val token: {req_val}")
    
    client.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Arztsuche 116117 API Client Test Suite")
    print("=" * 60)

    try:
        # Run tests
        test_authentication()
        test_location_search()
        test_therapist_search()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
