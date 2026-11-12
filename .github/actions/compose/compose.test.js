const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

function fixture(t) {
  const tmpRoot = fs.existsSync("/tmp/opencode") ? "/tmp/opencode" : os.tmpdir();
  const root = fs.mkdtempSync(path.join(tmpRoot, "howler-compose-action-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const bin = path.join(root, "bin");
  fs.mkdirSync(bin);
  const docker = path.join(bin, "docker");
  fs.writeFileSync(
    docker,
    `#!/usr/bin/env node
const fs = require('node:fs');
const args = process.argv.slice(2);
fs.appendFileSync(process.env.COMMANDS, JSON.stringify({ args, cwd: process.cwd() }) + '\\n');
if (args.includes(process.env.FAIL_COMMAND)) process.exit(1);
`,
  );
  fs.chmodSync(docker, 0o755);
  const env = {
    ...process.env,
    PATH: `${bin}${path.delimiter}${process.env.PATH}`,
    GITHUB_WORKSPACE: root,
    GITHUB_STATE: path.join(root, "state"),
    COMMANDS: path.join(root, "commands"),
    "INPUT_COMPOSE-FILE": "api/dev/docker-compose.yml",
    INPUT_BUILD: "true",
    INPUT_PROFILE: "",
    INPUT_SERVICES: "",
    JOB_STATUS: "success",
    RUNNER_DEBUG: "",
    FAIL_COMMAND: "",
  };
  const run = (script, overrides = {}) =>
    spawnSync(process.execPath, [path.join(__dirname, script)], {
      env: { ...env, ...overrides },
      encoding: "utf8",
    });
  const state = () => fs.readFileSync(env.GITHUB_STATE, "utf8").trim().split("=")[1];
  const commands = () =>
    fs.existsSync(env.COMMANDS)
      ? fs.readFileSync(env.COMMANDS, "utf8").trim().split("\n").map(JSON.parse)
      : [];
  return { root, run, state, commands };
}

test("starts a built stack from the workspace and tears it down after success", (t) => {
  const f = fixture(t);
  assert.equal(f.run("main.js").status, 0);
  assert.equal(f.run("post.js", { STATE_compose_config: f.state() }).status, 0);
  assert.deepEqual(f.commands(), [
    { args: ["compose", "-f", "api/dev/docker-compose.yml", "up", "-d", "--build"], cwd: f.root },
    { args: ["compose", "-f", "api/dev/docker-compose.yml", "down"], cwd: f.root },
  ]);
});

test("saves the profile and services before a failed startup, then logs and cleans up", (t) => {
  const f = fixture(t);
  const main = f.run("main.js", {
    "INPUT_COMPOSE-FILE": "mcp/docker-compose.yml",
    INPUT_BUILD: "false",
    INPUT_PROFILE: "full",
    INPUT_SERVICES: "howler-api elasticsearch\nredis keycloak",
    FAIL_COMMAND: "up",
  });
  assert.equal(main.status, 1);
  assert.equal(
    f.run("post.js", { STATE_compose_config: f.state(), JOB_STATUS: "failure" }).status,
    0,
  );
  const prefix = ["compose", "-f", "mcp/docker-compose.yml", "--profile", "full"];
  const services = ["howler-api", "elasticsearch", "redis", "keycloak"];
  assert.deepEqual(
    f.commands().map(({ args }) => args),
    [
      [...prefix, "up", "-d", ...services],
      [...prefix, "logs", "--no-color", ...services],
      [...prefix, "down"],
    ],
  );
});

test("logs on cancellation or debug and continues cleanup if logs fail", (t) => {
  for (const overrides of [
    { JOB_STATUS: "cancelled" },
    { JOB_STATUS: "success", RUNNER_DEBUG: "1" },
  ]) {
    const f = fixture(t);
    assert.equal(f.run("main.js").status, 0);
    const post = f.run("post.js", {
      STATE_compose_config: f.state(),
      FAIL_COMMAND: "logs",
      ...overrides,
    });
    assert.equal(post.status, 0);
    assert.match(post.stderr, /Could not collect Compose logs/);
    assert.deepEqual(
      f.commands().map(({ args }) => args[3]),
      ["up", "logs", "down"],
    );
  }
});

test("reports cleanup failures", (t) => {
  const f = fixture(t);
  assert.equal(f.run("main.js").status, 0);
  const post = f.run("post.js", { STATE_compose_config: f.state(), FAIL_COMMAND: "down" });
  assert.equal(post.status, 1);
  assert.match(post.stderr, /docker compose down failed/);
});

test("rejects invalid input without starting a stack", (t) => {
  for (const overrides of [
    { "INPUT_COMPOSE-FILE": "" },
    { INPUT_SERVICES: "--remove-orphans" },
    { INPUT_PROFILE: "--bad" },
    { INPUT_BUILD: "yes" },
  ]) {
    const f = fixture(t);
    assert.equal(f.run("main.js", overrides).status, 1);
    assert.equal(f.run("post.js").status, 0);
    assert.deepEqual(f.commands(), []);
  }
});
