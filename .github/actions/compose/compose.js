const { spawnSync } = require("node:child_process");

const splitServices = (value) => value.trim().split(/\s+/).filter(Boolean);

function configFromInputs(env) {
  const file = (env["INPUT_COMPOSE-FILE"] || "").trim();
  const profile = (env.INPUT_PROFILE || "").trim();
  const services = splitServices(env.INPUT_SERVICES || "");
  const build = (env.INPUT_BUILD || "false").trim();
  const name = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/;

  if (!file) throw new Error("compose-file is required");
  if (profile && !name.test(profile)) throw new Error("Invalid Compose profile");
  if (services.some((service) => !name.test(service))) throw new Error("Invalid Compose service");
  if (build !== "true" && build !== "false") throw new Error("build must be true or false");

  return { file, profile, services, build: build === "true" };
}

function compose(config, args) {
  const globalArgs = ["compose", "-f", config.file];
  if (config.profile) globalArgs.push("--profile", config.profile);
  const result = spawnSync("docker", [...globalArgs, ...args], {
    cwd: process.env.GITHUB_WORKSPACE,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(
      `docker compose ${args[0]} failed${result.signal ? ` (${result.signal})` : ` (exit ${result.status})`}`,
    );
  }
}

module.exports = { compose, configFromInputs };
