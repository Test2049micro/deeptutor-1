"""A Git-valid release tag must stay data throughout release validation."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


@pytest.mark.skipif(
    not shutil.which("bash") or not shutil.which("git"), reason="requires bash and git"
)
def test_release_tag_cannot_execute_shell_commands(tmp_path):
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/pypi-release.yml").read_text()
    )
    step = next(
        item
        for item in workflow["jobs"]["build-and-publish"]["steps"]
        if item.get("name") == "Verify release tag is on main"
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = tmp_path / "injected-command"
    tag = 'v1.0.0";touch${IFS}${MARKER};#'
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "MARKER": str(marker),
    }

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)

    git("init", "-b", "main")
    git(
        "-c",
        "user.name=Security Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "fixture",
    )
    git("remote", "add", "origin", str(repo))
    git("check-ref-format", f"refs/tags/{tag}")
    git("tag", tag)
    # Simulate Actions' expression rendering, then run the actual production step.
    script = step["run"].replace("${{ github.event.release.tag_name }}", tag)
    env.update(
        {
            key: value.replace("${{ github.event.release.tag_name }}", tag)
            for key, value in step.get("env", {}).items()
        }
    )
    result = subprocess.run(
        ["bash", "-c", script], cwd=repo, env=env, capture_output=True, text=True
    )
    assert not marker.exists(), "Release metadata executed a shell command"
    assert result.returncode == 0, result.stderr
