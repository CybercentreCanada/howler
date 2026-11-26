# AI query generation

The search bars on the hit search, grid, view, dossier, and action pages can show
an AI button that turns a natural-language request into a Lucene query. The
generated query is streamed into the search bar as the provider produces it.
Users review it before running the search. If a query is already present, it is
sent so the model can refine it. A progress bar runs along the search bar while
the query is generated, and agent progress messages, such as tool calls, appear
in the stop button's tooltip. Editing or clearing the query during generation
stops it and keeps the analyst's change.

The provider is asked to return the query in a fenced `lucene` code block,
followed by an explanation of the fields, values, and time ranges it chose. Only
the code block is placed in the search bar. While the search bar still contains
the generated query, a "Why this query?" button opens the provider's full
response, rendered as untrusted markdown, so analysts can review and rework the
query. Responses without a code block are used as the query as a whole. A
custom `core.ai.lucene.system_prompt` should keep asking for this format.

Query generation does not require `system.encryption_key`, because tokens are
used immediately and never queued. Generation runs within a Howler API request,
so each active generation keeps the request and a connection to the provider
open until the provider finishes or its inactivity timeout elapses.
`core.ai.lucene.max_concurrent` (default 2) limits concurrent generations in
each API process to bound the load sent to the provider; further requests
receive HTTP 429 until a generation finishes or its client disconnects.

When generation finishes, Howler asks Elasticsearch to validate the query. If it
is not valid Lucene, the query is still placed in the search bar, with a warning
so the analyst can correct it. Prompts are recorded in the audit log.

The button is hidden when the configured provider cannot be used, and the API
logs a warning at startup. Two providers are supported.

## OpenAI-compatible provider

The default `openai` provider reuses the [`core.ai`](ai_triage.md#configuration)
endpoint, credentials, headers, timeouts, and size limits, and requires
`core.ai.enabled`, which also enables the AI triage action:

```yaml
core:
  ai:
    enabled: true
    endpoint: https://ai.example.invalid/v1/chat/completions
    model: triage-model
    lucene:
      enabled: true
      model: query-model # optional, defaults to core.ai.model
      max_prompt_chars: 2000
      max_concurrent: 2
```

The provider must support OpenAI-compatible streaming (`"stream": true`)
server-sent events, ending with a `data: [DONE]` marker. Streams that end without
it, report an error, or stop because of a length or content filter limit are
rejected rather than producing a partial query. A provider that returns one
complete JSON response is also accepted, but the query then appears all at once.
Each request sends the configured `system_prompt`, followed by every indexed hit
field from the Elasticsearch mapping and its type, including allowed values for
enumerated fields such as `howler.status`. Namespaces that accept arbitrary
subfields, such as `labels`, are listed as `labels.*`.

## AI agent provider

The `agent` provider calls an [A2A](https://a2a-protocol.org/) AI agent with
the analyst's delegated identity, through a token broker that issues
agent-scoped tokens. It does not require `core.ai.enabled` or the `core.ai`
endpoint:

```yaml
core:
  ai:
    lucene:
      enabled: true
      provider: agent
      agent:
        agent_url: https://agents.example.invalid/agent/howler-lucene/
        broker_url: https://token-broker.example.invalid
        broker_token_field: subject_token
        scope: api://<agent-platform-app-id>/user_impersonation
        timeout_seconds: 120
```

For each request:

1. The analyst's Howler bearer token is exchanged for a delegated token for the
   agent platform. A plugin that declares an `ai_agent` entry in
   `modules.token_functions` is used first, like the existing `clue` and
   `notebook` token functions. Otherwise, Howler performs an Azure
   on-behalf-of exchange with `scope`, using the configured `azure` or
   `entraid` OAuth provider. The Howler token is never sent to the agent
   platform as-is. Successful exchanges are cached for 15 minutes.
2. The delegated token and the agent URL, without its trailing slash, are
   posted to `<broker_url>/v1/auth/broker/exchange` as
   `{"<broker_token_field>": ..., "mcp_server_url": ...}`. Set
   `broker_token_field` to the field name your broker expects. The returned
   `access_token` is used only for this agent request and never returned to
   the browser.
3. Howler sends an A2A JSON-RPC `message/stream` request to `agent_url` and
   streams artifact text into the search bar. If the agent produces no
   artifact, its final message is used.

Analysts must sign in with OAuth: Basic, API-key, and internal Howler token
credentials cannot be delegated. Exchange and broker failures are returned as
HTTP 502 errors before streaming starts. Agent failures, failed, rejected, or
canceled tasks, and JSON-RPC errors are reported in the stream without upstream details. If the
agent asks for more input, its question is shown so the analyst can rephrase the
request. Redirects are not followed, and no tokens or upstream responses are
logged.

Only the `system_prompt` and the request are sent to the agent; the field list
is omitted because the agent is expected to use Howler MCP tools such as
`get_index_fields` and `get_field_values`. The agent must have access to the
Howler MCP server, and Howler's Azure application needs delegated permission
for the agent platform's scope.
