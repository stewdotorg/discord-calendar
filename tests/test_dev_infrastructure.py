"""Tests for dev container infrastructure — docker-compose, auto-shutdown, auto-update."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
_COMPOSE_PATH = REPO_ROOT / "docker-compose.dev.yml"
_AUTOSHUTDOWN_PATH = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
_AUTOUPDATE_PATH = REPO_ROOT / "scripts" / "dev-autoupdate.sh"


def _extract_volume_names(volumes: list) -> list[str]:
    """Extract volume names from a Docker Compose volumes list.

    Compose volumes support short syntax ("vol_name:/path") and long syntax
    ({"vol_name": {...}}). This returns just the volume name portion.
    """
    names: list[str] = []
    for vol in volumes:
        names.append(vol if isinstance(vol, str) else next(iter(vol)))
    return names


@pytest.fixture(scope="class")
def dev_compose() -> dict:
    """Load docker-compose.dev.yml once per test class."""
    with open(_COMPOSE_PATH) as f:
        return yaml.safe_load(f)


class TestDevComposeFile:
    """Validate docker-compose.dev.yml structure."""

    def test_compose_file_exists(self) -> None:
        assert _COMPOSE_PATH.exists(), f"Expected {_COMPOSE_PATH} to exist"

    def test_compose_is_valid_yaml(self, dev_compose: dict) -> None:
        assert dev_compose is not None, "docker-compose.dev.yml should not be empty"

    def test_has_bot_dev_service(self, dev_compose: dict) -> None:
        assert "services" in dev_compose, "compose file must have services"
        assert "bot-dev" in dev_compose["services"], "compose file must have bot-dev service"

    def test_bot_dev_uses_dev_profile(self, dev_compose: dict) -> None:
        service = dev_compose["services"]["bot-dev"]
        profiles: list[str] = service.get("profiles", [])
        assert "dev" in profiles, "bot-dev must use profiles: [dev] for isolation"

    def test_bot_dev_uses_env_dev(self, dev_compose: dict) -> None:
        service = dev_compose["services"]["bot-dev"]
        env_files: list[str] = service.get("env_file", [])
        assert ".env.dev" in env_files, "bot-dev must use .env.dev"

    def test_bot_dev_has_separate_volume(self, dev_compose: dict) -> None:
        service = dev_compose["services"]["bot-dev"]
        volumes: list = service.get("volumes", [])
        volume_names = _extract_volume_names(volumes)
        assert any("bot_dev_data" in v for v in volume_names), (
            "bot-dev must use bot_dev_data volume"
        )
        assert "volumes" in dev_compose, "compose file must declare volumes"
        assert "bot_dev_data" in dev_compose["volumes"], (
            "bot_dev_data volume must be declared"
        )

    def test_no_port_conflict_with_prod(self, dev_compose: dict) -> None:
        service = dev_compose["services"]["bot-dev"]
        ports: list = service.get("ports", [])
        host_ports = [str(p).split(":")[0] for p in ports]
        assert "8001" in host_ports, "Dev must expose on host port 8001"
        assert "8000" not in host_ports, (
            "Dev must not expose on host port 8000 (reserved for prod)"
        )

    def test_dev_compose_does_not_affect_prod(self, dev_compose: dict) -> None:
        services = list(dev_compose.get("services", {}).keys())
        assert "bot" not in services, "Dev compose must not define prod bot service"
        assert "caddy" not in services, "Dev compose must not define prod caddy service"
        volume_names = list(dev_compose.get("volumes", {}).keys())
        assert "bot_data" not in volume_names, "Dev compose must not use prod bot_data volume"
        assert "caddy_data" not in volume_names, "Dev compose must not use prod caddy_data volume"


class TestDevAutoshutdownScript:
    """Validate dev-autoshutdown.sh script."""

    def test_script_exists(self) -> None:
        assert _AUTOSHUTDOWN_PATH.exists(), f"Expected {_AUTOSHUTDOWN_PATH} to exist"

    def test_script_is_executable(self) -> None:
        assert os.access(_AUTOSHUTDOWN_PATH, os.X_OK), f"{_AUTOSHUTDOWN_PATH} must be executable"

    def test_script_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(_AUTOSHUTDOWN_PATH)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"bash syntax error in dev-autoshutdown.sh:\n{result.stderr}"
        )

    def test_script_has_shebang(self) -> None:
        first_line = _AUTOSHUTDOWN_PATH.read_text().split("\n")[0]
        assert first_line.startswith("#!/"), (
            f"Script must have shebang, got: {first_line}"
        )

    def test_script_references_dev_compose(self) -> None:
        content = _AUTOSHUTDOWN_PATH.read_text()
        assert "docker-compose.dev.yml" in content, (
            "Script must reference docker-compose.dev.yml"
        )

    def test_script_references_bot_dev(self) -> None:
        content = _AUTOSHUTDOWN_PATH.read_text()
        assert "bot-dev" in content, "Script must reference bot-dev service"


class TestDevAutoupdateScript:
    """Validate dev-autoupdate.sh script."""

    def test_script_exists(self) -> None:
        assert _AUTOUPDATE_PATH.exists(), f"Expected {_AUTOUPDATE_PATH} to exist"

    def test_script_is_executable(self) -> None:
        assert os.access(_AUTOUPDATE_PATH, os.X_OK), f"{_AUTOUPDATE_PATH} must be executable"

    def test_script_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(_AUTOUPDATE_PATH)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"bash syntax error in dev-autoupdate.sh:\n{result.stderr}"
        )

    def test_script_has_shebang(self) -> None:
        first_line = _AUTOUPDATE_PATH.read_text().split("\n")[0]
        assert first_line.startswith("#!/"), (
            f"Script must have shebang, got: {first_line}"
        )

    def test_script_uses_git_fetch_before_pull(self) -> None:
        content = _AUTOUPDATE_PATH.read_text()
        assert "git fetch" in content, (
            "Script must git fetch before checking for updates"
        )

    def test_script_references_dev_compose(self) -> None:
        content = _AUTOUPDATE_PATH.read_text()
        assert "docker-compose.dev.yml" in content, (
            "Script must reference docker-compose.dev.yml"
        )

    def test_script_references_bot_dev(self) -> None:
        content = _AUTOUPDATE_PATH.read_text()
        assert "bot-dev" in content, "Script must reference bot-dev service"
