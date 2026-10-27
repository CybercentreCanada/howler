# AI triage unit tests

These tests exercise local AI triage behavior with mocked queue, storage,
authentication, worker, and HTTP boundaries. They do not require Redis,
Elasticsearch, a provider, a server, or background workers.

From `api/`, run the suite directly with pytest (the `poetry run test` wrapper
starts an API server and is not needed here):

```sh
TESTING=true HWL_START_BACKGROUND_SERVICES=false poetry run pytest --import-mode=importlib \
  test/unit/ai_triage test/unit/test_app.py \
  test/unit/endpoints/test_action_endpoint.py test/unit/services/test_enqueue_action.py
```
