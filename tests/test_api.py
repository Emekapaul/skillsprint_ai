from backend.api import app, STATE


def setup_function():
    STATE["documents"].clear()
    STATE["matrix"].clear()
    STATE["plans"].clear()
    STATE["validations"].clear()


def test_health():
    client = app.test_client()
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


def test_roles():
    client = app.test_client()
    response = client.get('/api/roles')
    assert response.status_code == 200
    assert len(response.get_json()['roles']) >= 10
