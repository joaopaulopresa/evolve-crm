from tests.conftest import auth


def create_deal(client, user, **overrides):
    payload = {"title": "Annual plan", "value": 12000, "stage": "lead"} | overrides
    response = client.post("/api/deals", json=payload, headers=auth(user))
    assert response.status_code == 201, response.text
    return response.json()


def test_new_deal_is_owned_by_its_creator(client, alice):
    deal = create_deal(client, alice)

    assert deal["owner_id"] == alice.id
    assert deal["owner_name"] == "Alice"
    assert deal["value"] == 12000
    assert deal["closed_at"] is None


def test_moving_a_deal_to_won_sets_closed_at_and_reopening_clears_it(client, alice):
    deal = create_deal(client, alice)
    headers = auth(alice)

    won = client.patch(f"/api/deals/{deal['id']}", json={"stage": "won"}, headers=headers).json()
    assert won["stage"] == "won"
    assert won["closed_at"] is not None

    reopened = client.patch(
        f"/api/deals/{deal['id']}", json={"stage": "proposal"}, headers=headers
    ).json()
    assert reopened["closed_at"] is None


def test_unknown_stage_is_rejected(client, alice):
    response = client.post("/api/deals", json={"title": "x", "stage": "maybe"}, headers=auth(alice))

    assert response.status_code == 422


def test_sales_user_sees_only_own_deals_and_admin_sees_all(client, admin, alice, bob):
    create_deal(client, alice, title="Alice deal")
    bob_deal = create_deal(client, bob, title="Bob deal")

    def titles(user, **params):
        rows = client.get("/api/deals", params=params, headers=auth(user)).json()
        return sorted(row["title"] for row in rows)

    assert titles(alice) == ["Alice deal"]
    assert titles(admin) == ["Alice deal", "Bob deal"]
    assert titles(admin, owner_id=bob.id) == ["Bob deal"]
    assert titles(admin, stage="won") == []
    assert client.get(f"/api/deals/{bob_deal['id']}", headers=auth(alice)).status_code == 404
    assert (
        client.patch(
            f"/api/deals/{bob_deal['id']}", json={"stage": "won"}, headers=auth(alice)
        ).status_code
        == 404
    )


def test_only_admin_can_reassign_a_deal(client, admin, alice, bob):
    deal = create_deal(client, alice)

    by_owner = client.patch(
        f"/api/deals/{deal['id']}", json={"owner_id": bob.id}, headers=auth(alice)
    )
    by_admin = client.patch(
        f"/api/deals/{deal['id']}", json={"owner_id": bob.id}, headers=auth(admin)
    )

    assert by_owner.status_code == 403
    assert by_admin.json()["owner_name"] == "Bob"


def test_delete_deal(client, alice):
    deal = create_deal(client, alice)

    assert client.delete(f"/api/deals/{deal['id']}", headers=auth(alice)).status_code == 204
    assert client.get("/api/deals", headers=auth(alice)).json() == []
