# Copilot Coding Agent Onboarding: Howler

---

## Repository Overview

**Howler** is a modern, open-source alert triage platform designed for Security Operations Centers (SOCs) to optimize, automate, and accelerate incident response. It enables analysts and detection engineers to efficiently ingest, evaluate, and manage security alerts using standardized schemas, rule/logic-based automation, and rich UI/UX tooling.

- **Key Features:**
  - Customizable alert triage with Elastic Common Schema (ECS) compatibility.
  - Extensive automation via filter rules, Elastic Query Language, and Sigma.
  - Intelligent alert grouping/management with context-driven bundles.
  - Integration with tools like ElasticSearch, Redis, Kibana, and various plugins.
  - Web-based frontend and REST API backend.

**Primary Technologies:**
- Python (51.4%): Backend API (Flask), plugins, orchestration scripts.
- TypeScript (48.4%): Web frontend (React, Vite, Vitest, pnpm).
- Docker, Docker Compose: Local development, dev/demo, and deployment environments.
- Helm/Kubernetes: Option for production deployments using Helm charts.
- CI via GitHub Actions (multi-workflow: API, UI, Plugins, Docs).

**Repo Size:** Medium-large, multi-package monorepo.

**Documentation:** See https://cybercentrecanada.github.io/howler/ for detailed docs and developer guides.

---

## Build & Validation: Command Matrix

The repository is split into logical components: `api/` (Python backend), `ui/` (TypeScript React frontend), `client/` (Python client SDK), and plugins (e.g., `plugins/evidence`, `plugins/sentinel`).

#### **General Prerequisites**

- **Python 3.12** (backend, client, plugins)
- **Node.js v20** + **pnpm v10** (frontend)
- **Poetry** (`pipx install poetry`)
- Docker, Docker Compose (for dependencies/dev envs)
- Optional: Visual Studio Code (recommended in docs)

Always ensure the correct versions are used. Inconsistent Python versions (<3.12) **will** break builds.

### **Backend API (`api/`)**

**Setup**
1. Ensure `/etc/howler/conf`, `/var/cache/howler`, `/var/lib/howler`, `/var/log/howler` exist and are `$USER`-owned.
2. Configure Python (3.12+/venv), Poetry, Docker and Docker Compose as above.
3. Run:
   ```bash
   cd api
   poetry install --with test,dev,types
   poetry shell
   pre-commit install
   ./generate_howler_conf.sh
   ```

**Env Setup**
- Start backing services:
  ```bash
  (cd api/dev && docker-compose up)
  ```

**Run API Server**
  ```bash
  poetry run server
  ```

**Test**
  ```bash
  # install test deps if not already
  poetry install --with test
  poetry run mitre /etc/howler/lookups
  poetry run test
  ```

**Lint/Typecheck**
  ```bash
  poetry run ruff format howler --diff
  poetry run ruff check howler --output-format=github
  poetry run type_check
  poetry run pyright --level warning
  ```

### **Frontend UI (`ui/`)**

**Setup**
1. Install dependencies:
   ```bash
   cd ui
   pnpm install --frozen-lockfile
   ```

**Lint/Check**
  ```bash
  pnpm run lint        # Prettier
  pnpm eslint src      # ESLint
  pnpm tsc --noEmit    # TypeScript type-check
  ```

**Test**
  ```bash
  pnpm test
  ```

**Dev Server**
  ```bash
  pnpm start           # (or consult vite/README)
  ```

#### **Client (`client/`)**

```bash
cd client
poetry install --with dev,test,types
poetry run test
```

#### **Plugins (`plugins/{evidence,sentinel}/`)**

```bash
cd plugins/<plugin>
poetry install --with dev
poetry run test
```

---

## Clean Build Tips & Issues

- **ALWAYS** run `poetry install` or `pnpm install` if dependencies, lockfiles, or Python/Node versions change.
- Only Python 3.12+ is supported throughout.
- Use VSCode and recommended extensions for consistent linting/formatting.
- Derived conf files (`config.yml`, `classification.yml`) are generated via scripts or copied from test/unit/config.yml and api/build_scripts as appropriate.
- Docker Compose healthchecks gate service startup.
- Some plugin and client checks require their own poetry install/lint/test cycles.

---

## Architecture & Layout

### **Monorepo Root**

Key directories:
- `.github/`: GitHub Actions workflows, dependabot, API tokens/GraphQL.
- `api/`: Python backend API (Flask), builds, plugins, test infra.
- `ui/`: TypeScript React frontend (Vite project).
- `client/`: Python client SDK.
- `plugins/`: Plugin modules (evidence, sentinel).
- `docs/`, `documentation/`: Documentation via MkDocs.
- Build assets and configs, e.g., Helm charts in `howler-helm/`, Ansible in `ansible/`.

**Root files:**
```
README.md, LICENSE, .gitignore, .pre-commit-config.yaml, pyrightconfig.json
```

**API Directory (`api/`):**
- `howler/`: main source
- `build_scripts/`: utility/test/typecheck/generate scripts
- `dev/`: Docker Compose, Keycloak, Elastic, Redis for local dev
- `test/`: test suite

**UI Directory (`ui/`):**
- `src/`: main TypeScript source (React)
- `build_scripts/`: e.g., lint_staged.sh
- `public/`
- `node_modules/`, `target/`, etc.

**Plugins structure:** Follows Python package/plugin conventions.

### **Configuration & Linting**
- **Pre-commit** via `.pre-commit-config.yaml` (Ruff, formatters, commit message, poetry lock check).
- **Type checks** for Python (Ruff, mypy, pyright).
- **Type checks** for frontend (TypeScript).
- **Formatting**: Prettier for UI, Ruff for Python.

### **Frontend UI Unit Tests**

- **Framework**: Vitest + `@testing-library/react` (`renderHook`, `act`, `waitFor`), jsdom environment.
- **Setup file**: `ui/src/setupTests.ts` (referenced in `vite.config.ts` `test.setupFiles`).
- **Scope exclusion**: `vite.config.ts` excludes `src/commons/**` from the default test run. To test a file inside `src/commons/`, pass the path explicitly:
  ```bash
  npx vitest run src/commons/path/to/file.test.tsx
  ```
- **Shared test helpers** live in `ui/src/tests/`:
  - `setupLocalStorageMock()` — replaces `window.localStorage` with a `MockLocalStorage` instance whose `getItem`/`setItem`/`removeItem`/`clear` methods are Vitest spies. Call `mockLocalStorage.clear()` and clear the spies in `beforeEach`.
  - `setupContextSelectorMock()` — re-wires `use-context-selector` to use React's native context so providers work without the full library in tests.
  - `setupReactRouterMock()` — stubs `react-router-dom` (location, params, navigate, etc.).
- **`MockLocalStorage` caveat**: `setItem` stores values as strings (`this[key] = \`${val}\``). The key `'key'` is a reserved property name on the object and is read-only — **do not use `'key'` as a storage key in tests**; use descriptive names like `'testkey'`.
- **Cross-tab events**: jsdom does not propagate `StorageEvent` automatically. Dispatch them manually:
  ```ts
  window.dispatchEvent(new StorageEvent('storage', { key: 'mykey', newValue: JSON.stringify(value) }));
  ```
  The `key` field of the event **must exactly match** the key string the hook was initialized with.
- **Hook state updates** must be wrapped in `act()`; assertions go after the `act()` call.

### **CI/CD, Pre-merge Validation**

- **GitHub Actions** workflows for API, UI, plugins, and docs. See:
  - `.github/workflows/api-workflow.yml`
  - `.github/workflows/ui-workflow.yml`
  - `.github/workflows/client-workflow.yml`
  - `.github/workflows/evidence-plugin-workflow.yml`
  - `.github/workflows/sentinel-plugin-workflow.yml`

**Checks include:**
- Install deps (with lockfile validation).
- Typecheck (Ruff/mypy/pyright for Python, tsc for TypeScript).
- Lint/format (Ruff, Prettier, ESLint).
- Complete test suite.
- PR title validation (.github/workflows/pr-title-check.yml).
- All jobs **must pass** for UI/API/plugins—PRs will be blocked otherwise.

### **Documentation**

- In-code docs and `/docs`, `/documentation` (Markdown/MkDocs).
- [Full developer and getting started guides](https://cybercentrecanada.github.io/howler/developer/getting_started/).
- Plugins: extensible via documented plugin architecture (`docs/ui/plugins.md`).

---

## Reviewing Pull Requests

- All code changes **must** be reviewed through a pull request (PR).
- PRs **require passing all automated checks** (build, lint, type checks, unit tests) before merging.
- Every PR is subject to the following manual review criteria:
  - Clear, descriptive title (checked automatically by CI).
  - Meaningful description of intent and context.
  - Reasonable scope: avoid mixing unrelated changes.
  - Code conforms to the repo’s style, formatting, and testing standards:
    - Python: check type safety, linting, and tests.
    - TypeScript: verify type safety, lint, and completeness of test coverage.
    - Docker/K8s/infra: verify against deployment/operational best practices.
  - Backwards compatibility and non-breaking changes unless justified.
  - Documentation updated if relevant (README, in-code, etc.).
  - No sensitive data or secrets are committed.
- Requested changes **must** be addressed before merging.
- Major features or refactors often require additional sign-off from the core maintainers or designated domain experts.
- Reviewers may request additional/clarified tests, updated docs, or architectural discussion for complex changes.

---

## Summary Guidance for Coding Agents

- **Trust these instructions** for bootstrap, build, test, run, and lint in each subproject. Do NOT explore with search unless these are demonstrably incorrect or insufficient.
- **Validate lockfiles and use pinned tool versions.**
- **Never skip lint/type/unit tests.**
- Always follow PR/commit guidance (`pre-commit` and PR title checks).
- Use Docker Compose for local dev dependencies (Elastic, Redis, Keycloak).
- Plugins, client, and main API each need their environment/lint/test steps.
- Most common failure: Python version mismatch, missing conf files, skipped install, or dependency update.
- Check documentation/ for deep developer and CI/CD guidance.
- **For PRs**: Ensure all automated and manual review requirements are satisfied prior to merge to reduce rejection risk.

---

## Agent Notes & Learned Pitfalls

> **IMPORTANT FOR ALL FUTURE AGENTS**: When you learn something new, encounter a pitfall, or discover a non-obvious convention in this repository, **add a note to this section** before finishing your task. This keeps institutional knowledge available across conversations.

---

### Changelog Entries for Bug Fixes

When both of the following are true:
1. The agent is relatively confident in a bug fix (i.e. root cause identified, fix verified by tests), AND
2. The current branch is a trunk branch (`develop`, `main`) or a patch/RC branch (e.g. `patch/*`, `rc/*`)

...then a changelog entry **must** be added to `docs/RELEASES.md` under the appropriate version heading before finishing the task. Follow the existing format:

```markdown
- **Short Title** *(bugfix)*: One-sentence description of what was broken and what was fixed.
```

---

### TypeScript: Always Use Braces on `if` Statements

Never use single-line, braceless `if` statements. Always add braces and a newline for the body:

```ts
// Preferred
if (!value) {
  return;
}

// Avoid
if (!value) return;
```

This applies to `for`/`while` loop bodies as well.

---

### TypeScript: Prefer `const` Arrow Functions

Use `const` arrow functions instead of named `function` declarations for all TypeScript/React code in `ui/`:

```ts
// Preferred
const myFn = <T>(arg: T): T => { ... };

// Avoid
function myFn<T>(arg: T): T { ... }
```

For overloaded functions, express overload signatures as a typed `const`:
```ts
const myFn: {
  (key: string, list?: false): Scalar;
  (key: string, list: true): List;
} = (key, list = false) => { ... };
```

---

### Frontend UI Tests: Use `id` as the Test ID Attribute

Vitest/testing-library queries that target elements by test ID (e.g. `getByTestId`, `queryByTestId`) use the `id` attribute, **not** `data-testid`. This is configured via `vite.config.ts`:

```ts
// vite.config.ts (test section)
testIdAttribute: 'id'
```

Always set `id="..."` on elements you need to query by test ID. Do not use `data-testid`.

---

### Terminal Output Restriction

**This repository's VS Code settings suppress terminal output from being returned to the agent.** Running commands via the terminal tool will yield no output — the terminal appears to complete with exit code 0 but all stdout/stderr is suppressed.

**Workaround**: Ask the user to run the command and paste the result back. Phrase it clearly:
> "I can't read terminal output due to repository settings. Please run `<command>` and share the result."

The correct test command for the API is `poetry run test <path>` (not `pytest` directly), run from the `api/` directory.

---
