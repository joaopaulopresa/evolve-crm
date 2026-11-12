from tests.conftest import auth


def test_company_crud(client, alice):
    headers = auth(alice)
    created = client.post(
        "/api/companies", json={"name": "Northwind Labs", "industry": "Software"}, headers=headers
    )
    assert created.status_code == 201
    company_id = created.json()["id"]

    updated = client.patch(f"/api/companies/{company_id}", json={"city": "Lisbon"}, headers=headers)
    assert updated.json()["city"] == "Lisbon"
    assert updated.json()["industry"] == "Software"

    assert client.get(f"/api/companies/{company_id}", headers=headers).json()["name"] == (
        "Northwind Labs"
    )
    assert client.delete(f"/api/companies/{company_id}", headers=headers).status_code == 204
    assert client.get(f"/api/companies/{company_id}", headers=headers).status_code == 404


def test_company_search_and_industry_filter(client, alice):
    headers = auth(alice)
    for name, industry in [("Northwind Labs", "Software"), ("Blue Harbor", "Logistics")]:
        client.post("/api/companies", json={"name": name, "industry": industry}, headers=headers)

    by_name = client.get("/api/companies", params={"q": "harb"}, headers=headers).json()
    by_industry = client.get(
        "/api/companies", params={"industry": "Software"}, headers=headers
    ).json()

    assert [company["name"] for company in by_name] == ["Blue Harbor"]
    assert [company["name"] for company in by_industry] == ["Northwind Labs"]


def test_company_name_is_required(client, alice):
    response = client.post("/api/companies", json={"name": ""}, headers=auth(alice))

    assert response.status_code == 422


def test_contact_crud_includes_company_name(client, alice):
    headers = auth(alice)
    company = client.post("/api/companies", json={"name": "Northwind Labs"}, headers=headers).json()

    created = client.post(
        "/api/contacts",
        json={
            "first_name": "Maya",
            "last_name": "Okafor",
            "email": "maya@northwind.example",
            "company_id": company["id"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    contact = created.json()
    assert contact["company_name"] == "Northwind Labs"

    updated = client.patch(
        f"/api/contacts/{contact['id']}", json={"job_title": "CTO"}, headers=headers
    )
    assert updated.json()["job_title"] == "CTO"
    assert client.delete(f"/api/contacts/{contact['id']}", headers=headers).status_code == 204


def test_contact_search_matches_name_email_and_company_filter(client, alice):
    headers = auth(alice)
    company = client.post("/api/companies", json={"name": "Northwind Labs"}, headers=headers).json()
    client.post(
        "/api/contacts",
        json={"first_name": "Maya", "last_name": "Okafor", "company_id": company["id"]},
        headers=headers,
    )
    client.post(
        "/api/contacts",
        json={"first_name": "Jonas", "last_name": "Berg", "email": "jonas@blue.example"},
        headers=headers,
    )

    def names(**params):
        rows = client.get("/api/contacts", params=params, headers=headers).json()
        return [row["first_name"] for row in rows]

    assert names(q="okaf") == ["Maya"]
    assert names(q="blue.example") == ["Jonas"]
    assert names(company_id=company["id"]) == ["Maya"]
    assert names() == ["Jonas", "Maya"]
