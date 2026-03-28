import app as app_module


def test_health_endpoint():
    client = app_module.app.test_client()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "provider" in data


def test_chat_endpoint_with_mocked_agent(monkeypatch):
    def fake_handle_user_message(text: str):
        return {"text": f"echo:{text}", "tool_events": []}

    monkeypatch.setattr(app_module.agent, "handle_user_message", fake_handle_user_message)
    client = app_module.app.test_client()
    resp = client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["text"] == "echo:hello"

