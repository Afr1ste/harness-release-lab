from fastapi.testclient import TestClient

from harness_release_lab.webapp import create_app


def test_local_dashboard_and_input_validation(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/runs").json() == []
        assert client.get("/api/runs/../../secret").status_code == 404
        assert client.get("/api/jobs/nope").status_code == 404
        assert client.post("/api/runs", json={"target": "evil.module:run"}).status_code == 422
        assert (
            client.post(
                "/api/runs",
                json={"target": "reference-fixed"},
                headers={"Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        assert client.get("/", headers={"Host": "attacker.example"}).status_code == 403
        assert client.post("/api/runs", content="target=reference-fixed").status_code == 415


def test_job_lifecycle_and_admission(tmp_path):
    import time

    with TestClient(create_app(tmp_path)) as client:
        first = client.post("/api/runs", json={"target": "reference-fixed"})
        assert first.status_code == 202
        assert client.post("/api/runs", json={"target": "reference-fixed"}).status_code == 409
        job_id = first.json()["job_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = client.get("/api/jobs/" + job_id).json()
            if result["status"] != "running":
                break
            time.sleep(0.1)
        assert result["status"] == "completed"
        run_id = result["run_id"]
        report = client.get("/api/runs/" + run_id).json()
        assert report["passed"], [case for case in report["cases"] if not case["passed"]]
        assert len(client.get("/api/runs").json()) == 1
        assert (
            "attachment;"
            in client.get("/api/runs/" + run_id + "/report.html").headers["content-disposition"]
        )
        assert client.get("/api/compare", params={"baseline": run_id, "candidate": run_id}).json()[
            "release_allowed"
        ]
