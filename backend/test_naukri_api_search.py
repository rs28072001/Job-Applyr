"""Test script for Naukri API search functionality."""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from platforms.naukri.api_search import search_jobs_api, _build_search_url


class MockRateLimiter:
    """Mock rate limiter for testing."""
    def wait(self):
        pass
    def wait_page_load(self):
        pass


def test_url_building():
    """Test that search URLs are built correctly."""
    print("Testing URL building...")
    
    url = _build_search_url(
        keywords=["qa testing"],
        location="gurugram",
        page=1,
        experience=3,
        no_of_results=20
    )
    
    print(f"Generated URL: {url}")
    
    # Verify key components
    assert "jobapi/v3/search" in url
    assert "location=gurugram" in url
    # URL encoding can use + or %20 for spaces
    assert ("keyword=qa%20testing" in url or "keyword=qa+testing" in url)
    assert "pageNo=1" in url
    assert "experience=3" in url
    assert "noOfResults=20" in url
    
    print("✓ URL building test passed")


def test_api_search():
    """Test actual API search (requires internet)."""
    print("\nTesting API search...")
    
    rate_limiter = MockRateLimiter()
    
    try:
        listings = search_jobs_api(
            keywords=["qa testing"],
            location="gurugram",
            max_jobs=5,
            rate_limiter=rate_limiter,
            experience=3
        )
        
        print(f"Found {len(listings)} job listings")
        
        if listings:
            print("\nSample listing:")
            listing = listings[0]
            print(f"  Title: {listing.title}")
            print(f"  Company: {listing.company}")
            print(f"  Location: {listing.location}")
            print(f"  URL: {listing.url}")
            print(f"  Platform: {listing.platform}")
            
            assert listing.title
            assert listing.company
            assert listing.url
            assert listing.platform == "naukri"
            
            print("\n✓ API search test passed")
        else:
            print("⚠ No listings found (might be API issue or no jobs match)")
            
    except Exception as e:
        print(f"✗ API search test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_url_building()
    test_api_search()
    print("\nTest complete")
