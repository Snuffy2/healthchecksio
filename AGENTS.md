# AGENTS

## Purpose

- Provide clear, repository-specific instructions for autonomous agents working in this Home Assistant custom integration.

## General Guidelines

- Follow the [Home Assistant developer documentation](https://developers.home-assistant.io/docs/).
- Be concise and explain code changes briefly. For non-trivial edits, provide a short plan; for small, low-risk edits, implement them and give a one-line summary.
- Focus on one conceptual change at a time when public behavior or multiple modules are affected.
- Maintain Python 3.14+ compatibility and support the latest Home Assistant Core.
- Keep changes minimal, preserve established behavior, and explicitly explain any necessary deviation from these guidelines.

## Agent Permissions and Virtual Environment

- Agents may create and use a repository-local virtual environment at `./.venv`.
- Use `./.venv/bin/python`, `./.venv/bin/pytest`, and `./.venv/bin/prek` for local commands. A worktree may use the main checkout's `./.venv` when dependencies are unchanged.
- Dependencies are declared in `pyproject.toml` groups: `ha`, `lint`, `pytest`, and `dev`.
- Installing dependencies from the repository manifest into `./.venv` is allowed for local tooling and tests after approval. Do not perform unrelated network operations without explicit consent.

## Repository Structure

- `custom_components/healthchecksio`: integration code.
- `custom_components/healthchecksio/translations`: Home Assistant config-flow translations.
- `custom_components/healthchecksio/manifest.json`: integration metadata and release version.
- `README.md`: primary installation and usage documentation.
- `.github/workflows`: CI, release, and prek maintenance workflows.
- `pyproject.toml`: package metadata, dependency groups, and tool configuration.
- `prek.toml`: git hook configuration.

## Integration Design

- Keep Healthchecks.io API I/O asynchronous through Home Assistant's shared `aiohttp` client sessions.
- Keep setup and unload behavior in `__init__.py`, configuration and reconfiguration behavior in `config_flow.py`, and remote polling in `coordinator.py`.
- Add user-facing constants to `const.py`; do not scatter duplicated strings or timing values across platforms.
- Use the coordinator as the shared data boundary for sensor and binary-sensor platforms. Avoid each entity independently polling Healthchecks.io.
- Preserve config-entry migration behavior and entity identifiers. Registry changes or changed unique IDs affect existing installations and require explicit migration coverage.
- Keep `custom_components/healthchecksio/manifest.json`'s `version` and `custom_components/healthchecksio/const.py`'s `VERSION` aligned. The release workflow updates both from the GitHub release tag.
- Keep manifest metadata valid for HACS and Home Assistant validation. Do not add unsupported runtime dependencies without updating `pyproject.toml` and the manifest when required by Home Assistant.

## Coding Standards

- Add type annotations to functions and classes, including return types.
- Add or update Google-style docstrings for changed files, classes, and methods, including private methods when their behavior is non-obvious.
- Preserve existing comments, keep imports at the top of files, and let Ruff sort imports and format code.
- Do not use `assert` or `cast` in integration code.
- Catch specific exceptions; do not catch `Exception` broadly.
- Python 3.14 syntax is allowed when it makes the code clearer.
- Use Home Assistant's logging conventions. Avoid logging API keys, ping UUIDs, or full configuration-entry data.

## Local Tooling and Validation

- Run `./.venv/bin/prek run --all-files` for a complete lint, formatting, spelling, mypy, and workflow check.
- Run the complete pytest suite by default with `./.venv/bin/pytest`. Explain why if a targeted run is more appropriate.
- This repository currently has no test suite. When changing behavior, add focused Home Assistant tests under `tests/` with fixtures in `tests/conftest.py` rather than relying only on manual testing.
- Use `uv build --out-dir /private/tmp/healthchecksio-build-check` when package metadata or distribution contents change.
- Do not recommend `tox`; it is not used here.

## Testing Expectations

- Use `pytest` and Home Assistant helpers such as `MockConfigEntry` for integration behavior.
- Add one focused test module per changed source module when practical. Prefer parameterization to duplicated test cases.
- Mock Healthchecks.io HTTP behavior at the coordinator or config-flow boundary; do not make live API calls in tests.
- Cover config-flow validation, coordinator error handling, config-entry migration, and entity identity behavior whenever those areas change.

## Workflows and Releases

- `linters.yml` runs the repository's `prek` configuration.
- `validate.yml` runs Hassfest and HACS validation.
- `prek_autoupdate.yml` maintains hook revisions. Keep its permissions and `Snuffy2/prek-autoupdate@v2` contract intact.
- `prek-autofix-review.yml` analyzes pull requests with read-only permissions. `prek-autofix-fix.yml` is the separately trusted workflow-run consumer that can apply an approved artifact using `PREK_AUTOFIX_TOKEN`; do not combine their trust boundaries or run PR code in the privileged workflow.
- `release.yml` packages `custom_components/healthchecksio/healthchecksio.zip`, uploads it to a non-draft release, and updates version files for stable releases. Preserve the checkout, release-tag, and target-branch behavior when editing it.

## Git, Branches, and Pull Requests

- Create branches, commits, pushes, and pull requests only when authorized by the current user request.
- Feature branches must track same-named branches on `origin`, never `upstream/main`.
- Before reporting a branch as ready or published, verify `git status --short --branch`, `git branch -vv`, and `git rev-parse --abbrev-ref --symbolic-full-name @{u}`.
- Do not open a pull request autonomously.

## Documentation and Change Scope

- Prefer root-cause fixes over surface patches.
- Update `README.md` and translations when user-visible configuration, entity behavior, or installation steps change.
- Keep changes focused; do not mix unrelated refactors, formatting churn, or dependency upgrades into a bug fix.
