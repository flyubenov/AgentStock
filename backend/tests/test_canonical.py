from fastapi.testclient import TestClient

from main import create_app


def _client(host: str = "intrinsica.io") -> TestClient:
    return TestClient(create_app(public_mode=True, static_dir="", canonical_host=host))


def test_www_is_permanently_redirected_to_the_apex_keeping_path_and_query():
    r = _client().get("/t/AMZN?ref=x", headers={"host": "www.intrinsica.io"},
                      follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://intrinsica.io/t/AMZN?ref=x"


def test_www_with_a_port_is_still_redirected():
    r = _client().get("/", headers={"host": "www.intrinsica.io:443"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://intrinsica.io/"


def test_the_apex_is_served_not_redirected():
    r = _client().get("/api/health", headers={"host": "intrinsica.io"}, follow_redirects=False)
    assert r.status_code == 200


def test_no_canonical_host_means_no_redirect():
    r = _client(host="").get("/api/health", headers={"host": "www.intrinsica.io"},
                             follow_redirects=False)
    assert r.status_code == 200
