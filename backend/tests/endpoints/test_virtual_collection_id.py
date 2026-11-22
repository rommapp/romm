import pytest
from fastapi import status
from fastapi.testclient import TestClient

MALFORMED_ID = "!!!"


@pytest.mark.parametrize(
    "path",
    ["/api/roms", "/api/roms/random", "/api/roms/download"],
    ids=["gallery", "random", "bulk download"],
)
def test_a_malformed_virtual_collection_id_is_refused(
    client: TestClient, headers: dict[str, str], path: str
):
    response = client.get(
        path, headers=headers, params={"virtual_collection_id": MALFORMED_ID}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert any(
        "virtual_collection_id" in error["loc"] for error in response.json()["detail"]
    )


def test_a_malformed_virtual_collection_is_not_found(
    client: TestClient, headers: dict[str, str]
):
    response = client.get(f"/api/collections/virtual/{MALFORMED_ID}", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
