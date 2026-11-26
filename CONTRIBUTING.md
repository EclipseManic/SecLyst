# Contributing to Seclyst

Seclyst is one platform with five analysis engines. Contributions are welcome,
but the repository has a shape and changes are expected to respect it.

## The one rule

An engine directory (`engines/<id>/`) contains analysis code and its tests.
Nothing else.

No README, no requirements file, no license, no screenshots, no logo, no
configuration template, and no separate interface. If a change needs
documentation, it goes in `docs/`. If it needs a dependency, it goes in the root
`requirements.txt` under that engine's heading.

Two files are deliberate exceptions and both are explained in
[docs/ENGINES.md](docs/ENGINES.md): `engines/<id>/run.py` is the entrypoint the
supervisor spawns, and `engines/ioc/pyproject.toml` carries pytest configuration
the IOC suite needs.

## Setting up

```bash
python scripts/setup.py --dev
```

That creates `.venv`, installs Python dependencies, installs locked Node
dependencies, and builds the interfaces. On Windows use
`.venv\Scripts\python.exe` wherever this document says `.venv/bin/python`.

## Running the platform

```bash
.venv/bin/python run.py
```

It opens at <http://127.0.0.1:7000/>. Useful flags: `--no-browser`,
`--no-engines`, `--port`, `--host`.

## Tests and checks

Run the full chain before opening a pull request:

```bash
.venv/bin/python scripts/verify.py
```

That runs the platform suite, lint, all five engine suites, both frontend suites,
both frontend builds, dependency audits, and the browser verification. It is the
same chain CI runs.

Faster loops while working:

| Scope | Command |
| --- | --- |
| Platform tests | `.venv/bin/python -m pytest` |
| Platform lint | `.venv/bin/python -m ruff check .` |
| One engine | `.venv/bin/python -m pytest -q` from inside `engines/<id>/` |
| Shell tests | `npm --prefix web test` |
| Shell typecheck | `npm --prefix web run typecheck` |

Do not weaken a test to make a change pass. If a test is wrong, say so in the
pull request and change the test in its own commit with the reasoning.

## Commit messages

Conventional prefixes, matching the existing history:

```
feat(web): keep tool frames mounted across navigation
fix(events): load Vue from the bundled copy instead of unpkg
docs: consolidate engine documentation
chore: drop duplicate manifests and dead config
ci: run the web test suites
```

The scope is the area that changed: `web`, `api`, `jobs`, `auth`, an engine id,
or `docs`.

## Pull requests

- One concern per pull request. A refactor and a behaviour change in the same
  branch are two pull requests.
- Describe what changed and why, not only what files moved.
- Include the verification output, or state plainly which checks you could not
  run and why.
- Update the documentation in the same pull request as the change. A page that
  describes behaviour which no longer exists is a bug.
- Add a `CHANGELOG.md` entry under `Unreleased` for anything a user can notice.

## Documentation

- User-facing documentation lives in `docs/` and the root `README.md`.
- Historical design records live in `docs/internal/` and are not updated.
- Every relative link must resolve. A broken link in a README is a broken repo.

## Adding or replacing an engine

The full procedure is at the end of [docs/ENGINES.md](docs/ENGINES.md#adding-or-replacing-an-engine).
In short: implement the engine, serve `GET /api/health`, honour the access token,
register a `ToolSpec` in `seclyst/server.py`, add a `TOOLS_REGISTRY` entry in
`web/src/data/workspace.ts`, add dependencies to the root manifest, and
document it.

## Reporting a security issue

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contribution is licensed under the MIT
license in [LICENSE](LICENSE).
