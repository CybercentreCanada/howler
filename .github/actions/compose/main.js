const fs = require("node:fs");
const { compose, configFromInputs } = require("./compose");

try {
  const config = configFromInputs(process.env);
  // Save before startup so the post step can clean up a partially started stack.
  const state = Buffer.from(JSON.stringify(config)).toString("base64");
  fs.appendFileSync(process.env.GITHUB_STATE, `compose_config=${state}\n`);
  compose(config, ["up", "-d", ...(config.build ? ["--build"] : []), ...config.services]);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
