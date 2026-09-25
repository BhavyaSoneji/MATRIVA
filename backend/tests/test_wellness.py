from fastapi.testclient import TestClient


def test_create_daily_wellness_log(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "water_intake_ml": 1500, "sleep_hours": 7.5, "activity_minutes": 30},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date"] == "2026-09-25"
    assert body["water_intake_ml"] == 1500
    assert body["sleep_hours"] == 7.5
    assert body["activity_minutes"] == 30


def test_upsert_same_day_updates_not_duplicates(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "water_intake_ml": 1000, "sleep_hours": 6, "activity_minutes": 10},
    )
    second = client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "water_intake_ml": 2000, "sleep_hours": 8, "activity_minutes": 45},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["water_intake_ml"] == 2000
    assert body["sleep_hours"] == 8
    assert body["activity_minutes"] == 45

    summary = client.get("/wellness/summary?days=30", headers=auth_headers)
    matching = [d for d in summary.json()["days"] if d["date"] == "2026-09-25"]
    assert len(matching) == 1


def test_partial_update_only_touches_given_field(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "water_intake_ml": 1000, "sleep_hours": 6, "activity_minutes": 10},
    )
    response = client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "water_intake_ml": 1800},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["water_intake_ml"] == 1800
    assert body["sleep_hours"] == 6
    assert body["activity_minutes"] == 10


def test_get_daily_with_no_data_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/wellness/daily?date=2026-01-01", headers=auth_headers)
    assert response.status_code == 404


def test_summary_returns_requested_number_of_days(client: TestClient, auth_headers: dict[str, str]) -> None:
    for day in ("2026-09-20", "2026-09-21", "2026-09-22"):
        client.put(
            "/wellness/daily",
            headers=auth_headers,
            json={"date": day, "water_intake_ml": 1000, "sleep_hours": 7, "activity_minutes": 20},
        )
    response = client.get("/wellness/summary?days=7", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["days"]) <= 7
    dates = [d["date"] for d in body["days"]]
    assert dates == sorted(dates)


def test_invalid_values_are_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    negative_water = client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "water_intake_ml": -100},
    )
    assert negative_water.status_code == 422

    too_much_sleep = client.put(
        "/wellness/daily",
        headers=auth_headers,
        json={"date": "2026-09-25", "sleep_hours": 30},
    )
    assert too_much_sleep.status_code == 422


def test_user_cannot_read_another_users_wellness_data(client: TestClient) -> None:
    first = client.post(
        "/auth/register",
        json={"email": "wellness-a@example.com", "password": "StrongPass123", "full_name": "A"},
    )
    assert first.status_code == 201
    headers_a = {"Authorization": f"Bearer {first.json()['access_token']}"}

    second = client.post(
        "/auth/register",
        json={"email": "wellness-b@example.com", "password": "StrongPass123", "full_name": "B"},
    )
    assert second.status_code == 201
    headers_b = {"Authorization": f"Bearer {second.json()['access_token']}"}

    client.put(
        "/wellness/daily",
        headers=headers_a,
        json={"date": "2026-09-25", "water_intake_ml": 2500, "sleep_hours": 9, "activity_minutes": 60},
    )

    response_b = client.get("/wellness/daily?date=2026-09-25", headers=headers_b)
    assert response_b.status_code == 404

    summary_b = client.get("/wellness/summary?days=30", headers=headers_b)
    assert summary_b.status_code == 200
    assert summary_b.json()["days"] == []
