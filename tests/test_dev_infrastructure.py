"""Tests for dev container infrastructure — docker-compose, auto-shutdown, auto-update."""

import os
import subprocess
from pathlib import Path

import yaml  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDevComposeFile:
    """Validate docker-compose.dev.yml structure."""

    def test_compose_file_exists(self) -> None:
        """docker-compose.dev.yml exists in repo root."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        assert compose_file.exists(), f"Expected {compose_file} to exist"

    def test_compose_is_valid_yaml(self) -> None:
        """docker-compose.dev.yml is valid YAML."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        assert data is not None, "docker-compose.dev.yml should not be empty"

    def test_has_bot_dev_service(self) -> None:
        """docker-compose.dev.yml defines a bot-dev service."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        assert "services" in data, "compose file must have services"
        assert "bot-dev" in data["services"], "compose file must have bot-dev service"

    def test_bot_dev_uses_dev_profile(self) -> None:
        """bot-dev service uses profiles: [dev] for isolation."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        service = data["services"]["bot-dev"]
        profiles = service.get("profiles", [])
        assert "dev" in profiles, "bot-dev must use profiles: [dev] for isolation"

    def test_bot_dev_uses_env_dev(self) -> None:
        """bot-dev service uses .env.dev for isolated env vars."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        service = data["services"]["bot-dev"]
        env_files = service.get("env_file", [])
        assert ".env.dev" in env_files, "bot-dev must use .env.dev"

    def test_bot_dev_has_separate_volume(self) -> None:
        """bot-dev service uses bot_dev_data volume (separate from prod)."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        service = data["services"]["bot-dev"]
        volumes = service.get("volumes", [])
        volume_names = [v if isinstance(v, str) else list(v.keys())[0] for v in volumes]
        assert any("bot_dev_data" in v for v in volume_names), (
            "bot-dev must use bot_dev_data volume"
        )
        # Also check the volume is declared at top level
        assert "volumes" in data, "compose file must declare volumes"
        assert "bot_dev_data" in data["volumes"], (
            "bot_dev_data volume must be declared"
        )

    def test_no_port_conflict_with_prod(self) -> None:
        """Dev host port (8001) does not conflict with prod host port (8000)."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        service = data["services"]["bot-dev"]
        ports = service.get("ports", [])
        # Check host-side port: the part before the colon in "HOST:CONTAINER"
        host_ports = [str(p).split(":")[0] for p in ports]
        assert "8001" in host_ports, (
            "Dev must expose on host port 8001"
        )
        assert "8000" not in host_ports, (
            "Dev must not expose on host port 8000 (reserved for prod)"
        )

    def test_dev_compose_does_not_affect_prod(self) -> None:
        """docker-compose.dev.yml does not reference prod services or volumes."""
        compose_file = REPO_ROOT / "docker-compose.dev.yml"
        with open(compose_file) as f:
            data = yaml.safe_load(f)
        services = list(data.get("services", {}).keys())
        # Should only have bot-dev (and maybe nothing else)
        assert "bot" not in services, "Dev compose must not define prod bot service"
        assert "caddy" not in services, "Dev compose must not define prod caddy service"
        volume_names = list(data.get("volumes", {}).keys())
        assert "bot_data" not in volume_names, "Dev compose must not use prod bot_data volume"
        assert "caddy_data" not in volume_names, "Dev compose must not use prod caddy_data volume"


class TestDevAutoshutdownScript:
    """Validate dev-autoshutdown.sh script."""

    def test_script_exists(self) -> None:
        """dev-autoshutdown.sh exists in scripts/."""
        script = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
        assert script.exists(), f"Expected {script} to exist"

    def test_script_is_executable(self) -> None:
        """dev-autoshutdown.sh is executable."""
        script = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
        assert os.access(script, os.X_OK), f"{script} must be executable"

    def test_script_syntax(self) -> None:
        """dev-autoshutdown.sh passes bash syntax check."""
        script = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"bash syntax error in dev-autoshutdown.sh:\n{result.stderr}"
        )

    def test_script_has_shebang(self) -> None:
        """dev-autoshutdown.sh starts with a shebang."""
        script = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
        first_line = script.read_text().split("\n")[0]
        assert first_line.startswith("#!/"), (
            f"Script must have shebang, got: {first_line}"
        )

    def test_script_references_dev_compose(self) -> None:
        """dev-autoshutdown.sh uses docker-compose.dev.yml."""
        script = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
        content = script.read_text()
        assert "docker-compose.dev.yml" in content, (
            "Script must reference docker-compose.dev.yml"
        )

    def test_script_references_bot_dev(self) -> None:
        """dev-autoshutdown.sh stops the bot-dev service."""
        script = REPO_ROOT / "scripts" / "dev-autoshutdown.sh"
        content = script.read_text()
        assert "bot-dev" in content, (
            "Script must reference bot-dev service"
        )


class TestDevAutoupdateScript:
    """Validate dev-autoupdate.sh script."""

    def test_script_exists(self) -> None:
        """dev-autoupdate.sh exists in scripts/."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        assert script.exists(), f"Expected {script} to exist"

    def test_script_is_executable(self) -> None:
        """dev-autoupdate.sh is executable."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        assert os.access(script, os.X_OK), f"{script} must be executable"

    def test_script_syntax(self) -> None:
        """dev-autoupdate.sh passes bash syntax check."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"bash syntax error in dev-autoupdate.sh:\n{result.stderr}"
        )

    def test_script_has_shebang(self) -> None:
        """dev-autoupdate.sh starts with a shebang."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        first_line = script.read_text().split("\n")[0]
        assert first_line.startswith("#!/"), (
            f"Script must have shebang, got: {first_line}"
        )

    def test_script_uses_git_fetch_before_pull(self) -> None:
        """dev-autoupdate.sh fetches before checking for main advancement."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        content = script.read_text()
        assert "git fetch" in content, (
            "Script must git fetch before checking for updates"
        )

    def test_script_references_dev_compose(self) -> None:
        """dev-autoupdate.sh uses docker-compose.dev.yml."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        content = script.read_text()
        assert "docker-compose.dev.yml" in content, (
            "Script must reference docker-compose.dev.yml"
        )

    def test_script_references_bot_dev(self) -> None:
        """dev-autoupdate.sh rebuilds the bot-dev service."""
        script = REPO_ROOT / "scripts" / "dev-autoupdate.sh"
        content = script.read_text()
        assert "bot-dev" in content, (
            "Script must reference bot-dev service"
        )
