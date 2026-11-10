const { compose } = require("./compose");

try {
  const state = process.env.STATE_compose_config;
  if (state) {
    const config = JSON.parse(Buffer.from(state, "base64").toString("utf8"));
    if (process.env.JOB_STATUS !== "success" || process.env.RUNNER_DEBUG === "1") {
      try {
        compose(config, ["logs", "--no-color", ...config.services]);
      } catch (error) {
        console.error(`Could not collect Compose logs: ${error.message}`);
      }
    }
    compose(config, ["down"]);
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
