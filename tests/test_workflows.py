"""Release and CI workflow contract tests."""

import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).parents[1]
RELEASE_SCRIPT = PROJECT_ROOT / ".github/scripts/update_release_version.py"
RELEASE_WORKFLOW = PROJECT_ROOT / ".github/workflows/release.yml"
PYTEST_WORKFLOW = PROJECT_ROOT / ".github/workflows/pytest_coverage.yml"


def test_release_version_script_updates_both_packaging_sources(tmp_path: Path) -> None:
    """Run the release helper as the workflow does and assert its output is package-consistent."""
    component_dir = tmp_path / "custom_components/healthchecksio"
    component_dir.mkdir(parents=True)
    manifest_path = component_dir / "manifest.json"
    const_path = component_dir / "const.py"
    manifest_path.write_text('{"domain": "healthchecksio", "version": "v0.0.0"}\n')
    const_path.write_text('"""Version source."""\n\nVERSION = "v0.0.0"\n')
    environment = os.environ | {"RELEASE_TAG": "v2.3.4"}

    result = subprocess.run(
        [sys.executable, str(RELEASE_SCRIPT)],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(manifest_path.read_text())["version"] == "v2.3.4"
    assert 'VERSION = "v2.3.4"' in const_path.read_text()


def test_release_and_pytest_workflows_keep_their_packaging_and_test_contracts() -> None:
    """Guard the CI paths that publish the integration and execute this suite."""
    release_workflow = RELEASE_WORKFLOW.read_text()
    pytest_workflow = PYTEST_WORKFLOW.read_text()

    assert "python .github/scripts/update_release_version.py" in release_workflow
    assert "zip healthchecksio.zip -r ./" in release_workflow
    assert "files: ./custom_components/healthchecksio/healthchecksio.zip" in release_workflow
    assert "pip install --group pytest ." in pytest_workflow
    assert "run: pytest" in pytest_workflow
