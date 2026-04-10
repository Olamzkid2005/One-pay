"""Tests for pre-commit hooks configuration (Requirement 18)."""

import os

import pytest
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".pre-commit-config.yaml")
SETUP_SH_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "setup.sh")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def test_precommit_config_exists() -> None:
    """Verify .pre-commit-config.yaml exists."""
    assert os.path.isfile(CONFIG_PATH), ".pre-commit-config.yaml not found"


def test_precommit_config_contains_ruff() -> None:
    """Verify ruff linting and formatting hooks are configured."""
    config = load_config()
    hook_ids = [
        hook["id"]
        for repo in config["repos"]
        for hook in repo["hooks"]
    ]
    assert "ruff" in hook_ids, "ruff linting hook not found"
    assert "ruff-format" in hook_ids, "ruff-format hook not found"


def test_precommit_config_contains_trailing_whitespace() -> None:
    """Verify trailing-whitespace check is configured."""
    config = load_config()
    hook_ids = [
        hook["id"]
        for repo in config["repos"]
        for hook in repo["hooks"]
    ]
    assert "trailing-whitespace" in hook_ids, "trailing-whitespace hook not found"


def test_setup_sh_references_precommit() -> None:
    """Verify scripts/setup.sh references pre-commit installation."""
    assert os.path.isfile(SETUP_SH_PATH), "scripts/setup.sh not found"
    with open(SETUP_SH_PATH) as f:
        content = f.read()
    assert "pre-commit" in content, "setup.sh does not reference pre-commit"
