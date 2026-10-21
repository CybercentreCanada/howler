# Clue UI integration

Clue replication stream authentication recovery requires a Clue UI release that
supports `DatabaseConfig.onReplicationError`. That Clue UI fix must be published
and the Howler dependency must be bumped to the published release separately;
the currently installed Clue UI 1.4.4 does not call this hook, so the Howler-side
wiring is not active until that rollout is complete. Do not use a local package
path or unreleased binary as a deployment dependency.

Clue compares the current token with the token used by the rejected stream XHR
and owns the final retry decision. Howler's default callback handles only stream
HTTP 401 errors, refreshes the current user through the standard
`api.user.whoami.get()` flow, and returns true only for a successful, defined
response with a nonempty default token. Concurrent refresh requests are
coalesced. Failed refreshes and other statuses do not trigger a retry.

A custom `getToken` remains in use. Howler does not refresh its own credentials
for custom token providers; supply `CluePluginOptions.onReplicationError` to
provide their recovery behavior. Clue will still require a nonempty token that
differs from the rejected XHR's token before retrying.
