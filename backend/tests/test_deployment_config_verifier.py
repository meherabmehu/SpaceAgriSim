"""The deployment-configuration verifier must report its preconditions, not crash on them.

The script constructs the settings object under a Vercel environment as one of its checks, and on
Vercel a missing `SPACEAGRISIM_AUTH_SECRET` is a validation error by design. That intended refusal
used to escape as a pydantic traceback from the middle of the security checks, so the script died
before it could print a single result - a gate that cannot report its own failure. It now states the
requirement and exits 2, which is what this test pins.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_verifier_states_the_missing_secret_instead_of_raising() -> None:
    env = {key: value for key, value in os.environ.items()
           if key != "SPACEAGRISIM_AUTH_SECRET"}
    env["SPACEAGRISIM_TEST_POSTGRES_URL"] = ""
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_deployment_config.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert "SPACEAGRISIM_AUTH_SECRET must be set" in completed.stdout
    assert "Traceback" not in completed.stderr
