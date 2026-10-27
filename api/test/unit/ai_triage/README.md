# Independent AI triage regression suite

The unit suite scripts HTTP responses and clocks. Runtime probes add a
slow-trickle loopback HTTP server; no test calls an external AI provider.
Dispatch and socket tests run authentication decorators, substituting only the
identity-provider boundary. Protocol tests execute the production HTTP adapters
and parsers, including malformed/partial response and no-replay cases.

`test/integration/service/test_ai_triage_recovery.py` runs actual Redis queue
operations and actual Elasticsearch selection, version conflicts, and full-record
saves. It allocates unique Redis key prefixes and Elasticsearch collections,
removes only those resources, and fails rather than skips if infrastructure is
unavailable. No database-wide flush or shared test fixture changes are used.

From `api/`:

```sh
AI_TRIAGE_TEST_REDIS_URL=redis://127.0.0.1:16389/15 \
AI_TRIAGE_TEST_ES_URL=http://127.0.0.1:19289 \
poetry run test --import-mode=importlib \
  test/unit/ai_triage test/integration/service/test_ai_triage_recovery.py
```

Defaults are local Redis port 6379/database 15 and Elasticsearch port 9200.
For worktree verification, set `PYTHONPATH` to the implementation worktree's
`api/` directory and `VIRTUAL_ENV` to the existing locked API Poetry environment.
Set `PYTHONSAFEPATH=1` so the wrapper's subprocess entrypoint also imports the
implementation rather than the QA worktree's unchanged backend.
The normal test wrapper's relative `--cov=howler` source can report zero coverage
in that cross-worktree setup; this is not evidence that the exercised sibling
modules were untested. Test tracebacks identify the imported source paths.

## Coverage boundaries

- Real Redis: atomic oversize rejection; concurrent global permits; durable
  per-alert deadlines, provider attempts, task checkpoints; lease recovery, stale nonces,
  heartbeat cancellation, terminal credential scrubbing.
- Real Elasticsearch: 10/50 selection after eligibility/ACL filtering; frozen
  targets/current worker input; reassessment/resolution races; old opinion and
  analyst-edit preservation; genuine version conflicts; immutable canonical
  candidate replay after a stale committer resumes beyond its final check.
- Full worker paths: transient/auth HTTP failures, completion/save/ack crash
  windows, checkpoint recovery without resubmission, disabled configuration,
  missing user/corrupt credential handling; third-attempt candidate/task recovery
  without another inference; read-only reconciliation beyond the active deadline;
  truthful bounded `write_outcome_unknown` rather than pretending rollback;
  delayed reconciliation reads and real CAS retries cannot extend the original
  alert deadline; resolved/assessed alerts without the exact submitted candidate
  remain pending (including the same owner/run/text with stale digests or valid,
  different generation provenance). Set-once candidate tests likewise reject
  same-text/run candidates with valid different generation/source metadata.
- Authenticated API and socket paths: owner/current-classification access,
  read privilege, filtered pagination, public schema, no-store, event recipient
  filtering and payload allowlisting, private persistence-before-notification.
- Strict transports: completed text, SSE append/replace, malformed JSON-RPC,
  bounded input/output/streams, explicit unsupported-only fallback, immutable
  request budget, no auth/partial-response replay, no redirects/netrc. A worker
  boundary test uses distinct epoch/monotonic origins and delayed reads to prove
  the provider receives the original absolute monotonic deadline, not a renewed
  budget or epoch timestamp.

Crash tests use deterministic `BaseException` injections at persistence
boundaries, not OS-level process termination. Concurrent claim tests use
independent native threads sharing a real Redis server, including a paused
claimer resumed after actual lock expiration while four replacements are live.
Subprocess probes import the production early-patched entrypoint, verify safe
rejection of enabled unpatched serving, and exercise provider-free disabled
maintenance (including late arrivals after an initially empty queue). An actual
`poetry run server` process verifies debug startup with four consumers and no
`TESTING`, `WERKZEUG_RUN_MAIN`, or `HWL_START_BACKGROUND_SERVICES` overrides. Its
temporary configuration disables unrelated scheduled jobs, and a safety check
requires the isolated Redis DB0 production queue namespace to be empty. Poetry
reads the implementation package's script declaration in cross-worktree runs;
it must not read the QA worktree's pre-feature declaration. Child processes use
an allowlisted environment plus explicit isolated configuration, not inherited
Howler settings. Hostile mixed-case/top-level/nested configuration and startup
indicator tests point only to disposable loopback sentinels; they verify that
imports start no consumers and never contact those sentinels. The probes also
exercise the triggered-action queue with the scheduled job system disabled.
They use real Redis/Elasticsearch and fixed-length HTTP bodies exceeding 8192
bytes, trickled one byte at a time, checking cancellation and socket cleanup at
the 500ms item deadline and on lease-renewal failure. Both real OpenAI and A2A
adapters must also interrupt frequent single-byte Content-Length trickles at a
one-second provider timeout while the immutable item deadline remains five
seconds away, closing both response and session contexts. A2A includes both
JSON and real `text/event-stream` responses. Idempotent repeated `close()` calls
are permitted; local socket closure remains mandatory. No late monkey-patching of
the main pytest process is used.
Current-user/socket revocation, unrefreshed classification changes, retention
shorter than the active deadline, and postcommit read reconciliation are tested.
Browser rendering and multi-pod deployment/network partition injection remain
outside this backend scope. Unmet assertions remain failures, not xfails/skips.

This suite does not promise atomic Redis/Elasticsearch fencing or exactly-once
requests. A resumed same-job stale CAS is allowed only with the identical full
persisted candidate; ES version conflicts must protect unrelated edits, and
the dossier must contain one managed lead. Candidate digests and generation
metadata are fixed before the write and verified across recovery.
