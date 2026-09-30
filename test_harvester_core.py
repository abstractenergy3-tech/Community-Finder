"""
Safe test for the reusable Community Finder harvesting core.

This test does NOT connect to Supabase and does NOT modify any data.
"""

import harvester_core as core

from harvester_core import (
    HarvestError,
    canonical_json,
    extract_rows,
    normalize_record,
    source_hash,
    synchronize_resources,
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
            "source_id": "example-food-bank-001",
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
        source_record_id_fields=("source_id",),
        description_fields=("description",),
        address_fields=("address",),
        phone_fields=("phone",),
        website_fields=("website",),
        latitude_fields=("latitude",),
        longitude_fields=("longitude",),
    )

    assert normalized["title"] == "Example Food Bank"
    assert normalized["source_record_id"] == "example-food-bank-001"
    assert normalized["city_id"] == (
        "b47e66a8-465b-49a9-bc81-3d6e48a022fd"
    )
    assert normalized["category"] == "Food Assistance"
    assert normalized["latitude"] == 47.6062
    assert normalized["longitude"] == -122.3321
    print("PASS: normalize_record")

    # A stable source ID is mandatory.
    try:
        normalize_record(
            row={"name": "Missing ID Example"},
            source_url="https://example.org/data.json",
            publisher="Example Publisher",
            city_id="b47e66a8-465b-49a9-bc81-3d6e48a022fd",
            category="Food Assistance",
            title_fields=("name",),
        )
    except HarvestError:
        print("PASS: missing source_record_id fails closed")
    else:
        raise AssertionError(
            "normalize_record accepted a record without source_record_id"
        )

        # Test stable source-record synchronization.
    #
    # This uses fake Supabase responses and performs no real database writes.

    fake_existing = [
        {
            "id": "resource-123",
            "source_record_id": "example-food-bank-001",
            "source_hash": "hash-old",
        }
    ]

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def json(self):
            return self.rows

    def fake_supabase_request(
        method,
        url,
        *,
        service_role_key,
        params=None,
        **kwargs,
    ):
        assert method == "GET"
        return FakeResponse(fake_existing)

    upsert_calls = []

    def fake_upsert_resource(
        *,
        supabase_url,
        service_role_key,
        resource,
        existing_id=None,
    ):
        upsert_calls.append(existing_id)
        return existing_id or "new-resource"

    original_supabase_request = core.supabase_request
    original_upsert_resource = core.upsert_resource

    core.supabase_request = fake_supabase_request
    core.upsert_resource = fake_upsert_resource

    try:
        updated_resource = {
            "source_record_id": "example-food-bank-001",
            "source_hash": "hash-new",
            "title": "Example Food Bank",
        }

        stats = synchronize_resources(
            supabase_url="https://example.supabase.co",
            service_role_key="test-key",
            source_url="https://example.org/data.json",
            resources=[updated_resource],
        )

        assert stats["updated"] == 1
        assert stats["inserted"] == 0
        assert stats["unchanged"] == 0
        assert upsert_calls == ["resource-123"]

        print("PASS: stable source ID updates existing resource")

        upsert_calls.clear()

        unchanged_resource = {
            "source_record_id": "example-food-bank-001",
            "source_hash": "hash-old",
            "title": "Example Food Bank",
        }

        stats = synchronize_resources(
            supabase_url="https://example.supabase.co",
            service_role_key="test-key",
            source_url="https://example.org/data.json",
            resources=[unchanged_resource],
        )

        assert stats["updated"] == 0
        assert stats["inserted"] == 0
        assert stats["unchanged"] == 1
        assert upsert_calls == []

        print("PASS: stable source ID leaves unchanged resource alone")

    finally:
        core.supabase_request = original_supabase_request
        core.upsert_resource = original_upsert_resource
    print("")
    print("ALL TESTS PASSED.")
    print("No Supabase writes were performed.")


if __name__ == "__main__":
    main()
