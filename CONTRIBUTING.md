# Contributing

Thanks for helping improve the HealthChecks.io Home Assistant integration. Contributions can include bug reports, documentation improvements, tests, and focused code changes.

## Report a bug or request a feature

- Search existing [issues](../../issues) before opening a new one.
- Use the available issue template and include Home Assistant version, integration version, relevant logs with secrets removed, and clear steps to reproduce the problem.
- Describe the expected behavior and what happened instead.

## Make a change

1. Fork the repository and create a branch from `main`.
2. Keep the change focused. Update documentation and translations when user-facing behavior changes.
3. Set up the development environment:

   ```sh
   uv venv .venv
   uv sync --group dev
   ```

4. Add or update focused tests for behavior changes. Test files belong in `tests/`.
5. Run the repository checks:

   ```sh
   ./.venv/bin/prek run --all-files
   ```

   For behavior changes, run the test suite after adding or updating tests:

   ```sh
   ./.venv/bin/pytest
   ```

6. Open a pull request with a concise summary, the reason for the change, and the validation you ran.

## Code and documentation expectations

- Support Python 3.14 and the latest Home Assistant Core.
- Keep Healthchecks.io requests asynchronous and use Home Assistant's shared `aiohttp` sessions.
- Add type annotations and Google-style docstrings for changed code.
- Use the configured `prek` hooks for formatting, linting, spelling, mypy, and GitHub Actions validation. Do not run Black; Ruff provides the repository's formatting.
- Do not include API keys, ping UUIDs, or full config-entry data in commits, logs, screenshots, or issue reports.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
