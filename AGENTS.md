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
- Python CI quality jobs run on Python 3.12 (`api/.python-version`). Test matrices differ: API 3.10-3.13; client, Evidence, and Sentinel 3.10-3.12; Sync and MCP 3.12 only.
- The UI's `.nvmrc` says Node 20, while current UI CI uses Node 24 and pnpm 11. Use pnpm, never npm, and honor `ui/pnpm-lock.yaml`.
- After changing a lockfile or dependency declaration, reinstall that package with its lockfile before validating it.

## API Development And Validation

Run these from `api/` after `poetry install --with test,dev,types`:

```bash
poetry run ruff format howler --diff
poetry run ruff check howler --output-format=github
poetry run type_check
poetry run pyright --project pyproject.toml --level warning
poetry run test <specific_test_file_paths>
```

### API Code Organization And Compatibility

- Files that contain Flask routes should contain only route definitions; keep business logic and helper implementations out of route files.
- Expose specific functionality that is used frequently through the relevant service files.
- Put reusable code that is not specific to a particular service or domain in a utility file.
- API endpoints are the only compatibility contract that must be maintained. Internal function signatures may change freely.
- If a change would significantly simplify the code but require a breaking change, ask the user before proceeding; that tradeoff will often be worthwhile.
- Avoid running the full API unit test suite during routine validation; it takes a long time. Prefer targeted tests for the affected code, and run the full suite only when explicitly requested or necessary.
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
pnpm test <specific_test_file_paths>
```

- Avoid running the full UI unit test suite during routine validation; it takes a long time. Prefer targeted tests for the affected code, and run the full suite only when explicitly requested or necessary.
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
- Evidence and Sentinel: from the plugin directory, install with `poetry install --with dev,types`, run Ruff against `evidence` or `sentinel`, run `poetry run type_check`, and use direct pytest for tests, for example `poetry run pytest test/unit -vv`. Their tests import the API package and may need the API config files and services.
- Sync: install from `plugins/sync/` with `poetry install --with dev,types`; unit tests are local, but integration tests require Elasticsearch and create/clean randomized Howler users and hits.
- MCP: from `mcp/`, run `poetry install --with dev`, `poetry run ruff format howler_mcp --diff`, `poetry run ruff check howler_mcp --output-format=github`, and `poetry run test`. Use `poetry run test test/test_tools.py -k name` for a focused unit test.
- MCP live tests in `test/test_network.py` are skipped unless `RUN_MCP_NETWORK_TESTS=1`, `TEST_AUTH_USERNAME`, `TEST_AUTH_PASSWORD`, and `TEST_AUTH_EMAIL` are set. They require the `mcp/docker-compose.yml` full stack, seeded API data, and a running MCP server; see `.github/workflows/mcp-workflow.yml` for the exact orchestration.

## Python CI Workflows

The Python workflows in `.github/workflows/` are the source of truth for CI. To reproduce a job, run its steps in order from the package directory unless a step names another one. Publish jobs run only for stable release tags, so never run `poetry publish` or Docker pushes locally.

### API (`api-workflow.yml`)

- Quality job (Python 3.12, `api/`): `poetry install --with test,dev`, then the commands in "API Development And Validation". Also run hadolint on the Dockerfile with `hadolint --ignore DL3018 --failure-threshold warning api/Dockerfile`; CI uses `hadolint/hadolint-action`.
- Test job (Python 3.10-3.13, `api/`):
  1. Run `docker compose -f api/dev/docker-compose.yml up --build -d`, then apply the config setup from the API section.
  2. Run `poetry install --with test,dev`, then `poetry run mitre /etc/howler/lookups` and `poetry run sigma`.
  3. Run `poetry run python build_scripts/docker_health.py`.
  4. Run `poetry run test <paths>`. The wrapper starts its own Flask server, so do not also run `poetry run server`. CI runs the full suite; locally, use targeted paths.
  5. After a passing run, run `poetry run coverage_report`.

### Client (`client-workflow.yml`)

- Quality job (Python 3.12, `client/`): CI installs only `--with test`, but ruff and mypy live in the `dev` group. Locally, use `poetry install --with dev,test,types`, then the ruff and `type_check` commands above.
- Test job (Python 3.10-3.12, `client/`):
  1. From `api/`, apply the API config setup, but copy `../client/test/config/config.ci.yml` to `/etc/howler/conf/config.yml` instead of `test/unit/config.yml`.
  2. From `api/`, run `poetry install --with test,dev`, then `poetry run mitre /etc/howler/lookups` and `poetry run sigma`.
  3. Run `docker compose -f client/test/docker-compose.yml up -d` for Elasticsearch and Redis.
  4. From `api/`, start the API in the background with `TESTING=true poetry run flask --app howler.app run --no-reload &`, and wait until `curl --fail http://localhost:5000/api/apispec_v1.json` succeeds.
  5. From `api/`, run `poetry run python -m howler.odm.random_data`.
  6. From `client/`, run `poetry install --with test`, then `poetry run test`. Passing paths gives a focused run without coverage.
  7. Stop the background Flask process when finished.

### MCP (`mcp-workflow.yml`)

- Quality job (Python 3.12, `mcp/`): `poetry install --with dev`, then the ruff format and check commands above. MCP has no type-check job.
- Test job (Python 3.12, `mcp/`) needs the full stack:
  1. From `mcp/`, run `docker compose -f docker-compose.yml --profile full up -d howler-api elasticsearch redis keycloak`.
  2. Seed the API with `docker compose -f docker-compose.yml exec -T howler-api python -m howler.odm.random_data users hits`.
  3. Start the server in the background with `HOWLER_API_HOST=localhost`, `HOWLER_API_BASE_URL=http://localhost:5000/api/v1`, `AUTH_HOST=localhost`, `AUTH_TOKEN_URL=http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/token`, `COVERAGE_FILE=.coverage.server`, and `poetry run coverage run -m howler_mcp.server`. Wait until `curl http://localhost:8000/mcp` responds.
  4. Run `poetry run test` with `RUN_MCP_NETWORK_TESTS=1`, `HOWLER_API_BASE_URL=http://localhost:5000/api/v1`, `COVERAGE_FILE=.coverage.tests`, and the `AUTH_*` and `TEST_AUTH_*` values from the job env in `mcp-workflow.yml`.
  5. Stop the server, then run `poetry run coverage combine`.

### Evidence, Sentinel, and Sync Plugins

- Quality jobs (Python 3.12, plugin directory): run `poetry check --lock`, `poetry install --with dev,types`, then ruff format and check on the package. Evidence and Sentinel then run `poetry run type_check`. Sync runs `poetry run python -m mypy --disable-error-code=import-untyped sync` instead; the workflow comment says this is for PyYAML's missing stubs.
- Evidence test job (Python 3.10-3.12, `plugins/evidence/`): apply the API config setup, run `poetry install --with dev,types`, `poetry run mitre /etc/howler/lookups`, and `poetry run sigma`, then `poetry run pytest --cov=evidence --cov-branch -rP -vv` and `poetry run python build_scripts/coverage_reports.py`. No services are needed.
- Sentinel test job (Python 3.10-3.12, `plugins/sentinel/`): run `docker compose -f api/dev/docker-compose.yml up --build -d`, apply the API config setup, and install with mitre and sigma as above. Wait up to 180 seconds for Elasticsearch `_cluster/health` (green or yellow) and Redis `PING`, then run `poetry run pytest --cov=sentinel --cov-branch -rP -vv test/unit` and the coverage report script.
- Sync test job (Python 3.12, `plugins/sync/`): install JDK 17 (CI uses Temurin, which Spark needs), then use the same services, config, and readiness wait as Sentinel. Run `poetry run pytest --cov=sync --cov-branch -rP -vv test/unit test/integration` and the coverage report script. Integration tests create and clean randomized Howler users and hits in Elasticsearch.

### Release Validation And Documentation

- `release-validation.yml` is a reusable, read-only job. It runs `python scripts/validate_release.py` on Python 3.12 to resolve the preview or stable channel from native package metadata and tags. Run it only when changing release logic, and only with the GitHub Actions environment variables listed in the script docstring.
- `deploy-documentation.yml` runs on `main` pushes that change `documentation/` or `docs/`. It installs `mkdocs-material`, `mkdocs-static-i18n`, and `mkdocs-glightbox` with pip, then runs `mkdocs gh-deploy --force` in `documentation/`. For a local preview, run `mkdocs serve` in `documentation/`. Do not run `gh-deploy` unless asked, because it pushes the built site to the `gh-pages` branch.

### Remote Runs And Generated Files

- Every Python workflow has a `workflow_dispatch` trigger. Dispatch only when asked, for example `gh workflow run api-workflow.yml --ref <branch>`. Leave `publish_release` at `false`, because `true` publishes stable artifacts. Check results with `gh run list --workflow api-workflow.yml` and `gh run view <run-id> --log-failed`.
- Test and coverage reports (`test-results.md`, `coverage-results.md`, and any `diff.txt` used for diff coverage) are written into package directories and are not gitignored. Remove them before committing.

## Cross-Cutting Workflow

- Root pre-commit hooks cover Ruff, Actionlint, oxfmt, changed-file oxlint/TypeScript checks, Poetry lock integrity, translation/import checks, and commit messages. Install with `pre-commit install` and run all hooks with `pre-commit run --all-files`.
- Commit messages use the Conventional Commit types configured in `.release-please-config.json` and the commit-message hook. Valid scopes are `api`, `client`, `ui`, `ci`, `demo`, `helm`, `mcp`, `evidence`, `sentinel`, `sync`, and `main` (for Release Please titles); the hook links issue-like branch names and lowercases the summary.
- GPG signing is broken in this environment. Whenever the agent creates a local commit, explicitly bypass signing for that invocation, e.g. `git -C <repo-or-worktree> -c commit.gpgsign=false commit ...`; never run bare `git commit` and do not change global or repository signing configuration.
- PR titles are semantic and their subjects must be lowercase; accepted types are defined in `.github/workflows/pr-title-check.yml`.
- Release Please creates independent package release PRs from `main` and generates each package's `CHANGELOG.md`. Do not manually add new entries to `docs/RELEASES.md`; it is a read-only archive of historical releases. Keep each package's initial native baseline note and archive link in its local changelog.

## Agentic Development And Git Worktrees

- Treat the user's request and this guide as the task contract. Start by checking `git status`, the current branch, and relevant code. Never overwrite unrelated work. Run Git/setup commands non-interactively and scoped to the intended worktree.
- First classify task size. Minor, localized work—such as a low-risk single-file bugfix, small documentation edit, or similarly bounded change—should be implemented directly in the primary working tree. Do not create subagents, worktrees, task manifests, or patch/review ceremony for these tasks; inspect the diff and run the focused checks appropriate to the change. A single-file task can still count as large when it is high-risk or requires substantial investigation.
- Use the full worktree/patch workflow only for large implementation tasks: substantial multi-file features or refactors, cross-package changes, migrations, broad test-suite work, or work with significant coordination risk. For these tasks, the orchestrator may provision and use the required worktrees and agent branches without asking for separate permission; this is part of carrying out the requested large implementation. The primary/root working tree is the final destination. Keep it on its existing branch; do not switch branches, check out or pull `main`, or create a feature integration branch as part of this flow. Implement large-task changes only in dedicated agent worktrees under `.worktrees/`.
- In the large-task workflow, split work only when slices are genuinely independent. Before dispatch, assign each subtask an explicit allowed-path set and forbidden-path set. These sets must be pairwise disjoint: no two agents may own, edit, or generate the same file, including tests, schemas, generated files, and lockfiles. If tasks need a shared file or contract change, give it one owner or make that work sequential. Verify actual changed paths against the manifest before review.
- Canonical role instructions live once in `.agents/agents/<role>/agent.md`. Use the architect role for data models, migrations, core logic, and API contracts; frontend for independent UI/client work; QA for an independently scoped test suite; implementer for a bounded general code/test slice; and reviewer for an adversarial, read-only audit. `.github/agents/`, `.opencode/agents/`, and `.opencode/opencode.jsonc` contain only host-specific discovery, model, tool, and permission bindings and must point to these canonical role instructions. Every large-task subtask receives an independent review before its patch is eligible for application. Any blocking/high-severity finding or unverified acceptance criterion means reject the patch and repeat implementation and review.
- For large tasks, pin the base to the current primary working tree's `HEAD` before dispatch. Use branch names `agent/<task-name>/<role>` and worktree paths `.worktrees/<task-name>-<role>`; do not create a `feature/<task-name>` integration branch/worktree. For example, after checking repository status, base SHA, and name/path availability: `git worktree add -b agent/<task-name>/<role> .worktrees/<task-name>-<role> <base-sha>`. Keep the root checkout on its current branch throughout.
- Before large-task code changes, place a `TASK.md` manifest at the root of each worktree describing task ID, pinned base commit, target worktree, exclusive allowed and forbidden path patterns, shared contract/interface, and package-specific verification command(s). Treat manifests as coordination artifacts; do not include them in the code patch.
- Open each large-task worktree as the active workspace for its implementation agent. OpenCode's project config uses `.worktrees` as the worktree parent; VS Code/Copilot should use worktree isolation when available or create the worktree explicitly. Agent model availability depends on host/plan; use the closest available host binding while keeping `.agents/agents/` as the role-instruction source of truth.
- After large-task implementation checks pass, have the independent reviewer inspect the complete patch from the pinned base and report specific findings and evidence. Only after approval, generate a binary-capable patch from that agent worktree. Inspect its file list and run `git apply --check` from the primary working tree before applying it there. Apply approved patches sequentially; because ownership sets are disjoint, patches can share the original base, but stop if a check fails or any path overlaps. Do not merge agent branches into the primary branch. After all patches are applied, inspect the primary working tree diff and rerun the relevant package checks there.
- Never hand-edit a lockfile during patch repair: assign each lockfile to one owner and use its package toolchain (Poetry within each Python package; pnpm in `ui/`), then generate and review a replacement patch. If a patch is rejected or fails to apply, do not force it; resolve the issue in the owning worktree, obtain a fresh adversarial review, and regenerate the patch. If root tests reveal integration-only issues, create a new scoped worktree from the current primary `HEAD` and repeat the review/apply cycle.
- Agent branch commits may be used as local patch-generation checkpoints only after the reviewer approves; they are not merged. This environment's GPG signing makes a bare `git commit` fail: for every authorized agent-branch checkpoint, explicitly bypass signing for that invocation with `git -C <worktree> -c commit.gpgsign=false commit ...`. Do not change global/repository signing configuration. Applying patches changes only the primary working tree, not its branch history. Worktree/branch teardown, root commits, branch switches, pushes, and PR creation are separate actions: do them only when requested, verify named worktrees are clean before removal, and never force-remove or blanket-prune user work.
- Model routing: GPT-6 Astra at high/xhigh for architecture and QA verification; GPT-6 Sol at high for orchestration and frontend/high-throughput tasks; GPT-6 Luna at xhigh (or the closest available high-reasoning implementation model) for implementation and tests. Review/resolution uses the active chat model unless the task calls for a different one. Host, plan, and model catalog may limit exact selection; use the closest enabled equivalent and do not claim an unavailable reasoning-effort setting was applied.
- For large-task worktree workflows, use the portable helpers and workflow in `.agents/skills/howler-worktrees/` (available to OpenCode and skills-compatible Copilot hosts). The helpers validate names, keep the primary checkout on its current branch, generate scoped task manifests and reviewed patches, check patch applicability, and refuse unsafe teardown.

## High-Risk Invariants

- Flask treats an unwrapped `(Response, version)` return as `(Response, status_code)`. Any endpoint returning a response plus an Elasticsearch version must use `@add_etag()`; getter-backed endpoints use `@add_etag(getter=...)`.
- Direct tests of getter-backed ETag endpoints should provide `record` when testing endpoint logic; decorator prefetch is exercised only when the route ID is supplied in the decorator's expected keyword form.
- Case correlation rules cannot set `expire_after_resolved=True` when `timeframe` is `None`; enforce this in both add and update service flows.
- Client v2 case-item calls use a required `name` on append, UUID item `id` values in `{"ids": [...]}` for delete, and `{"id": ..., "name": ...}` and/or `parent` for update.
- Elasticsearch ILM maintenance must enumerate `index_list_full`, exclude `__reindex` temporary indexes, preserve source lifecycle metadata, and leave only the latest ILM index as the write target. Legacy aliases must be swapped atomically when creating indexes.
- `SocketProvider.addListener` replaces a listener with the same key; case consumers must retain a stable per-instance suffix rather than keying only by case ID.
- MCP process-wide async HTTP clients belong to the returned Starlette application's lifespan, not FastMCP's per-session lifespan; close only clients owned by the application.
