# Howler Agent Guide

## Repository Shape

- This is a multi-package repository; each Python package has its own Poetry environment and lockfile.
- `api/` is the Flask backend and owns the shared ODM, datastore, API tests, and local dependency stack.
- `ui/` is the React/Vite TypeScript frontend; its generated entity types live in `ui/src/models/entities/generated/`.
- `client/` is the Python SDK and its integration tests use a running Howler API plus Elasticsearch and Redis.
- `plugins/evidence`, `plugins/sentinel`, and `plugins/sync` are separate Python packages that depend on the API package.
- `mcp/` is the authenticated FastMCP server; unit tests are isolated, while network tests need the full local stack.
- `documentation/` is the MkDocs site. `docs/RELEASES.md` is the product changelog.

## Toolchains And Setup

- Use Poetry for every Python package; do not install Python dependencies from the repository root.
- The API quality environment is Python 3.12 (`api/.python-version`); CI also tests the API, client, and plugins on Python 3.10-3.13 as applicable.
- The UI's `.nvmrc` says Node 20, while current UI CI uses Node 24 and pnpm 11. Use pnpm, never npm, and honor `ui/pnpm-lock.yaml`.
- After changing a lockfile or dependency declaration, reinstall that package with its lockfile before validating it.

## API Development And Validation

Run these from `api/` after `poetry install --with test,dev,types`:

```bash
poetry run ruff format howler --diff
poetry run ruff check howler --output-format=github
poetry run type_check
poetry run pyright --project pyproject.toml --level warning
poetry run test
```

- API tests expect writable `/etc/howler/conf`, `/etc/howler/lookups`, and `/var/log/howler` directories. Copy `build_scripts/classification.yml`, `build_scripts/mappings.yml`, and `test/unit/config.yml` to the corresponding config paths, then run `poetry run mitre /etc/howler/lookups` and `poetry run sigma` before testing.
- Start local dependencies with `docker compose -f api/dev/docker-compose.yml up --build -d`; Elasticsearch, Redis, Kibana, and Keycloak are defined there. `poetry run python build_scripts/docker_health.py` checks their health.
- Run the backend with `poetry run server`.
- The test wrapper starts a temporary test API and forwards pytest arguments, so a focused test can use `poetry run test test/unit/services/test_case_service.py -k rule`.
- `api/build_scripts/generate_classes.py` generates `ui/src/models/entities/generated/`; do not edit those files manually. Generation requires a running API at `localhost:5000` with suitable randomized data.

## UI Development And Validation

Run these from `ui/`:

```bash
pnpm install --frozen-lockfile
python ../hooks/check_translation.py
python ../hooks/find_bad_imports.py
pnpm tsc --noEmit
pnpm oxfmt src --check
pnpm oxlint src
pnpm test
```

- `pnpm run lint` fixes files; use the read-only commands above when checking a change.
- Use `pnpm exec vitest run path/to/file.test.tsx` for a focused test. The default Vitest and oxlint scopes exclude `src/commons/**`; pass a `src/commons/...` path explicitly to test it.
- `pnpm build` performs the production build; `pnpm start` runs Vite on port 3000 and proxies `/api` and `/socket` according to `VITE_API_TARGET`.
- Testing Library is configured with `testIdAttribute: 'id'`; elements targeted by `getByTestId`/`queryByTestId` need an `id`, not `data-testid`.
- Use the mock matching the package imported by the component: router hooks here come from `react-router`, not `react-router-dom`. Await `userEvent` directly rather than wrapping it in `act`; flush fake timers inside `act` with `vi.advanceTimersByTimeAsync`.
- `MockLocalStorage` defines a non-writable `key` method; do not use `key` as a storage key in tests. Clear the mock and its spies in `beforeEach` when using `setupLocalStorageMock()`.
- Import the explicit `@fontsource/roboto/index.css` entry; the package-root side-effect import can fail TypeScript resolution.
- UI lint requires type-only imports and prefers expression/arrow-style functions. Keep braces around control-flow bodies.
- Keep UI API endpoints in modules that mirror their URL/resource hierarchy: nested resources get their own directory with an `index.ts` barrel, and deeper endpoints live in their own modules (for example, `api/v2/case/rules/backfill/index.ts` and `count.ts`). Export nested modules as namespaces so callers use paths such as `api.v2.case.rules.backfill.post(...)` and `api.v2.case.rules.backfill.count.post(...)`; avoid adding nested endpoint methods inline to a parent module.

## Client, Plugins, And MCP

- Client: from `client/`, run `poetry install --with dev,test,types`, then `poetry run ruff format howler_client --diff`, `poetry run ruff check howler_client --output-format=github`, `poetry run type_check`, and `poetry run test`. A focused test is `poetry run test test/unit/test_case.py -k name`.
- Client integration tests need the API environment configured as above, an API server, and `docker compose -f client/test/docker-compose.yml up -d` for Elasticsearch and Redis. CI seeds API data with `poetry run python -m howler.odm.random_data`.
- Evidence and Sentinel: from the plugin directory, install with `poetry install --with dev`, run Ruff against `evidence` or `sentinel`, run `poetry run type_check`, and use direct pytest for tests, for example `poetry run pytest test/unit -vv`. Their tests import the API package and may need the API config files and services.
- Sync: install from `plugins/sync/` with `poetry install --with dev`; unit tests are local, but integration tests require Elasticsearch and create/clean randomized Howler users and hits.
- MCP: from `mcp/`, run `poetry install --with dev`, `poetry run ruff format howler_mcp --diff`, `poetry run ruff check howler_mcp --output-format=github`, and `poetry run test`. Use `poetry run test test/test_tools.py -k name` for a focused unit test.
- MCP live tests in `test/test_network.py` are skipped unless `RUN_MCP_NETWORK_TESTS=1`, `TEST_AUTH_USERNAME`, `TEST_AUTH_PASSWORD`, and `TEST_AUTH_EMAIL` are set. They require the `mcp/docker-compose.yml` full stack, seeded API data, and a running MCP server; see `.github/workflows/mcp-workflow.yml` for the exact orchestration.

## Cross-Cutting Workflow

- Root pre-commit hooks cover Ruff, Actionlint, oxfmt, changed-file oxlint/TypeScript checks, Poetry lock integrity, translation/import checks, and commit messages. Install with `pre-commit install` and run all hooks with `pre-commit run --all-files`.
- Commit messages are Conventional Commits. Valid scopes enforced by the hook are `api`, `client`, `ui`, `ci`, `demo`, `helm`, and `mcp`; the hook links issue-like branch names and lowercases the summary.
- PR titles are semantic and their subjects must be lowercase; accepted types are defined in `.github/workflows/pr-title-check.yml`.
- If a verified bug fix is made on `main`, `develop`, `patch/*`, or `rc/*`, add a matching entry under the appropriate version in `docs/RELEASES.md` using `- **Short Title** _(bugfix)_: description.`

## High-Risk Invariants

- Flask treats an unwrapped `(Response, version)` return as `(Response, status_code)`. Any endpoint returning a response plus an Elasticsearch version must use `@add_etag()`; getter-backed endpoints use `@add_etag(getter=...)`.
- Direct tests of getter-backed ETag endpoints should provide `record` when testing endpoint logic; decorator prefetch is exercised only when the route ID is supplied in the decorator's expected keyword form.
- Case correlation rules cannot set `expire_after_resolved=True` when `timeframe` is `None`; enforce this in both add and update service flows.
- Client v2 case-item calls use a required `name` on append, UUID item `id` values in `{"ids": [...]}` for delete, and `{"id": ..., "name": ...}` and/or `parent` for update.
- Elasticsearch ILM maintenance must enumerate `index_list_full`, exclude `__reindex` temporary indexes, preserve source lifecycle metadata, and leave only the latest ILM index as the write target. Legacy aliases must be swapped atomically when creating indexes.
- `SocketProvider.addListener` replaces a listener with the same key; case consumers must retain a stable per-instance suffix rather than keying only by case ID.
- MCP process-wide async HTTP clients belong to the returned Starlette application's lifespan, not FastMCP's per-session lifespan; close only clients owned by the application.
