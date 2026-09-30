"""
Safe test for the reusable Community Finder harvesting core.

This test does NOT connect to Supabase and does NOT modify any data.
"""

from harvester_core import (
    canonical_json,
    extract_rows,
    normalize_record,
    source_hash,
)


def main():
    print("Starting harvester_core safety test...")

    # Test deterministic JSON.
    sample_a = {"name": "Food Bank", "city": "Seattle"}
    sample_b = {"city": "Seattle", "name": "Food Bank"}

    json_a = canonical_json(sample_a)
    json_b = canonical_json(sample_b)

    assert json_a == json_b
    print("PASS: canonical_json")

    # Test deterministic source hashing.
    hash_a = source_hash(sample_a)
    hash_b = source_hash(sample_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64
    print("PASS: source_hash")

    # Test common API response extraction.
    rows = extract_rows(
        {
            "data": [
                {"name": "Example Food Bank"},
                {"name": "Example Meal Program"},
            ]
        }
    )

    assert len(rows) == 2
    assert rows[0]["name"] == "Example Food Bank"
    print("PASS: extract_rows")

    # Test resource normalization.
    normalized = normalize_record(
        row={
            "name": "Example Food Bank",
            "description": "Food assistance for the community.",
            "address": "123 Example St, Seattle, WA",
            "phone": "206-555-0100",
            "website": "https://example.org",
            "latitude": "47.6062",
            "longitude": "-122.3321",
        },
        source_url="https://example.org/data.json",
        publisher="Example Publisher",
        city_id="b47e66a8-465b-49a9-bc81-3d6e48a022fd",
        category="Food Assistance",
        title_fields=("name",),
        description_fields=("description",),
        address_fields=("address",),
        phone_fields=("phone",),
        website_fields=("website",),
        latitude_fields=("latitude",),
        longitude_fields=("longitude",),
    )

    assert normalized["title"] == "Example Food Bank"
    assert normalized["city_id"] == (
        "b47e66a8-465b-49a9-bc81-3d6e48a022fd"
    )
    assert normalized["category"] == "Food Assistance"
    assert normalized["latitude"] == 47.6062
    assert normalized["longitude"] == -122.3321
    print("PASS: normalize_record")

    print("")
    print("ALL TESTS PASSED.")
    print("No Supabase writes were performed.")


if __name__ == "__main__":
    main()
