"""Single-origin frontend serving and deployment-safety checks."""

from __future__ import annotations

import pytest

from app import config
from app.database import _ensure_sqlite_directory


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/style.css", "text/css"),
        ("/script.js", "text/javascript"),
        ("/careers-data.js", "text/javascript"),
        ("/recommendation-engine.js", "text/javascript"),
    ],
)
def test_frontend_assets_are_served_from_the_api_origin(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert len(response.content) > 100


def test_root_serves_the_existing_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CareerAI" in response.text
    assert 'src="script.js"' in response.text
    assert 'href="style.css"' in response.text
    assert "api/health" not in response.text


def test_index_html_is_also_available_directly(client):
    response = client.get("/index.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CareerAI" in response.text


def test_root_is_not_the_old_json_service_banner(client):
    response = client.get("/")
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.lstrip().startswith("<!DOCTYPE html>")


def test_api_and_docs_survive_the_frontend_catch_all(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/careers").json()["careers"]
    assert client.get("/api/careers/software-developer").status_code == 200

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/health" in openapi.json()["paths"]


@pytest.mark.parametrize(
    "path",
    [
        "/backend/app/main.py",
        "/backend/app/data/careers.json",
        "/backend/careerai.db",
        "/README.md",
        "/.gitignore",
        "/careerai.db",
    ],
)
def test_repository_files_are_not_exposed(client, path):
    assert client.get(path).status_code == 404


def test_unknown_api_paths_are_not_served_as_frontend_files(client):
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/missing-page").status_code == 404


def test_sqlite_parent_directory_is_created(tmp_path):
    target = tmp_path / "nested" / "careerai.db"
    _ensure_sqlite_directory("sqlite:///" + target.as_posix())
    assert target.parent.is_dir()


def test_render_uses_an_ephemeral_database_by_default(monkeypatch):
    monkeypatch.delenv("CAREERAI_DATABASE_URL", raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert config.database_url() == "sqlite:////tmp/careerai.db"


def test_local_database_default_is_outside_the_repository_asset_path(monkeypatch):
    monkeypatch.delenv("CAREERAI_DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    url = config.database_url()
    assert url.startswith("sqlite:///")
    assert url.endswith("career-ai/backend/careerai.db")
