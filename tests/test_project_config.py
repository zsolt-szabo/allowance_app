"""Checks on the project's own configuration files.

A broken CI workflow or a stale lock file is otherwise only discovered
after a push or, worse, during a deploy.
"""
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
LOCK = os.path.join(REPO_ROOT, "requirements-lock.txt")
REQUIREMENTS = os.path.join(REPO_ROOT, "py_requirements.txt")


def workflow():
    with open(WORKFLOW) as handle:
        return yaml.safe_load(handle)


def test_ci_workflow_is_valid_yaml():
    assert workflow()["jobs"]["test"]["steps"]


def test_ci_runs_every_gate():
    """Lint, both test suites, and the OpenAPI drift check."""
    commands = " ".join(
        step.get("run", "") for step in workflow()["jobs"]["test"]["steps"])
    assert "flake8" in commands
    assert "pytest" in commands
    assert "test_group_01.py" in commands
    assert "dump_openapi.py --check" in commands


def test_ci_installs_the_dev_requirements():
    commands = " ".join(
        step.get("run", "") for step in workflow()["jobs"]["test"]["steps"])
    assert "requirements-dev.txt" in commands


# --- dependency declarations ----------------------------------------------

def normalise(name):
    """PEP 503 normalisation.

    pip writes email_validator as email-validator in freeze output, so a
    naive comparison reports it missing from the lock when it is present.
    """
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def declared_names(path):
    names = set()
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        names.add(normalise(re.split(r"[<>=!\[]", line)[0]))
    return names


def test_lock_covers_every_declared_requirement():
    """Every direct production dependency must appear in the lock.

    Catches the case where py_requirements.txt gains an entry and nobody
    reruns scripts/lock_requirements.sh -- which is how a deploy ends up
    missing a package.
    """
    missing = declared_names(REQUIREMENTS) - declared_names(LOCK)
    assert not missing, (
        "requirements-lock.txt is missing %s -- rerun "
        "scripts/lock_requirements.sh" % sorted(missing))


def test_lock_is_fully_pinned():
    """A lock with a floor in it is not a lock."""
    unpinned = []
    for line in open(LOCK):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            unpinned.append(line)
    assert not unpinned, "not pinned: %s" % unpinned


def test_production_requirements_exclude_test_tooling():
    """Test tooling must not ship to the server."""
    production = declared_names(REQUIREMENTS)
    for tool in ("pytest", "hypothesis", "flake8", "time-machine", "pyyaml"):
        assert normalise(tool) not in production, \
            "%s is a dev dependency but is declared in production" % tool
