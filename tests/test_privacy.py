import math

from services.common.privacy import mask_location


def test_mask_location_coarsens_coordinates_without_mutating_source():
    source = {"lat": 10.123456, "lon": 78.987654, "count": 4}
    masked = mask_location(source)
    assert masked == {"lat": 10.12, "lon": 78.99, "count": 4}
    assert source["lat"] == 10.123456


def test_mask_location_preserves_non_numeric_and_non_mapping_details():
    assert mask_location(None) is None
    assert mask_location("not-json") == "not-json"
    masked = mask_location({"lat": float("nan"), "lon": "unknown"})
    assert math.isnan(masked["lat"])
    assert masked["lon"] == "unknown"
