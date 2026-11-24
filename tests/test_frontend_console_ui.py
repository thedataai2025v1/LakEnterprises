"""Tests for Phase 12 Console UI shell and frontend integration."""

import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.ui import get_frontend_dir, run_frontend_server


class TestConsoleUIShell:
    """Validate Next.js console UI shell file structure, API endpoints, and runner."""

    def test_frontend_directory_and_structure_exists(self):
        """Ensure Next.js shell and components exist in frontend directory."""
        fe_dir = get_frontend_dir()
        assert os.path.isdir(fe_dir)

        # Config files
        assert os.path.isfile(os.path.join(fe_dir, "package.json"))
        assert os.path.isfile(os.path.join(fe_dir, "tsconfig.json"))
        assert os.path.isfile(os.path.join(fe_dir, "next.config.js"))
        assert os.path.isfile(os.path.join(fe_dir, "tailwind.config.js"))

        # App & components
        src_dir = os.path.join(fe_dir, "src")
        assert os.path.isdir(src_dir)
        assert os.path.isfile(os.path.join(src_dir, "types", "api.ts"))
        assert os.path.isfile(os.path.join(src_dir, "lib", "api-client.ts"))
        assert os.path.isfile(os.path.join(src_dir, "context", "auth-context.tsx"))
        assert os.path.isfile(os.path.join(src_dir, "app", "layout.tsx"))
        assert os.path.isfile(os.path.join(src_dir, "app", "page.tsx"))
        assert os.path.isfile(os.path.join(src_dir, "app", "login", "page.tsx"))
        assert os.path.isfile(os.path.join(src_dir, "app", "processes", "page.tsx"))
        assert os.path.isfile(os.path.join(src_dir, "app", "approvals", "page.tsx"))
        assert os.path.isfile(os.path.join(src_dir, "app", "documents", "page.tsx"))

    @patch("subprocess.run")
    def test_run_frontend_server(self, mock_subprocess_run):
        """Verify launcher command executes npm script properly."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        code = run_frontend_server(port=3001, dev=True)
        assert code == 0
        assert mock_subprocess_run.called
        call_args, call_kwargs = mock_subprocess_run.call_args
        cmd = call_args[0]
        assert any("npm" in part for part in cmd)
        assert "run" in cmd
        assert "dev" in cmd
        assert "3001" in cmd

    def test_backend_api_surface_for_frontend(self):
        """Ensure all endpoints required by the frontend client are operational."""
        app = create_app()
        client = TestClient(app)

        # 1. Health endpoint
        res = client.get("/health/ready")
        assert res.status_code == 200
        assert "status" in res.json()

        # 2. Demo auth token endpoint
        res = client.post("/api/v1/auth/demo/analyst")
        assert res.status_code == 200
        token_data = res.json()
        assert "access_token" in token_data
        token = token_data["access_token"]
        auth_header = {"Authorization": f"Bearer {token}"}

        # 3. Current user profile
        res = client.get("/api/v1/auth/me", headers=auth_header)
        assert res.status_code == 200
        me = res.json()
        assert "analyst" in me.get("roles", []) or me.get("role") == "analyst"

        # 4. Processes list
        res = client.get("/api/v1/processes/instances", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 5. Approvals list
        res = client.get("/api/v1/approvals", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # 6. Documents list
        res = client.get("/api/v1/documents", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)
