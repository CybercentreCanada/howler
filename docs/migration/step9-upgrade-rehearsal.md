# Step 9: isolated 8.19 restore, same-volume upgrade, and rollback rehearsal

The runner performs: isolated 8.19.11 donor restore → donor snapshot → fresh 8.19.11
restore/preflight → stop 8.19 container → restart the **same cutover data volume** on
9.5.2 → verify cluster/index UUIDs, aliases, mappings, counts, and all document identities
and content → independent fresh 8.19.11 rollback restore.

All ES calls use raw `urllib`; the API package's 9.5 client is never used against 8.19.
The workflow accepts no arbitrary cluster URL or credentials, calls no Reindex API, and
does not remove data volumes. It uses local Docker resources and is a sanitized mechanics
exercise, not production evidence.

## Canonical synthetic fixture

The `--synthetic-fixture` contract is intentionally strict. Recreate this canonical corpus
rather than weakening checks for an earlier ad hoc fixture. Required indices, aliases, IDs,
sources, classifications, and case links are encoded in the script and checked after each
restore/upgrade/rollback phase:

- `howler-hit_hot`, with `howler-hit` explicitly marked `is_write_index: true`, has exactly two documents:
  `step9-hit-unrestricted-001` (`UNRESTRICTED`) and `step9-hit-restricted-002`
  (`RESTRICTED`). Both use the `STEP9-SHARED` query token; sequence values are 1/2 and
  visibility values are unrestricted/restricted.
- `howler-case_hot`, with `howler-case` explicitly marked `is_write_index: true`, has one RESTRICTED case with ID
  `00000000-0000-4000-8000-000000000901`. Its two `hit` items link to both hit IDs.
- The `_access_*` fields are frozen in the fixture source. They make the intended
  classification expectations explicit, but do not replace the application ACL test.

The seed-preparation mode creates the exact mappings, documents, write aliases, repository,
and 8.19.11 snapshot. It validates Docker ownership and the empty cluster before the first
ES write. A snapshot whose metadata says `8.19.9-8.19.11` with `version_id: 8537000` is
accepted as compatible with the 8.19.11 restore target; both metadata values are recorded.
Every running ES node must still report the exact expected version.

## Safe seed creation

This recipe creates a dedicated seed container named `howler-step9-canonical-seed` on a
local internal bridge. The seed repository host path is
`/tmp/opencode/step9-seed-canonical-20260929`; give Elasticsearch UID 1000 read/write access.
Do **not** substitute a production or shared-dev Docker context, data volume, snapshot
repository, or ES endpoint.

```bash
set -euo pipefail
RUN=canonical-seed-20260929
NETWORK=howler-step9-canonical-seed-network
CONTAINER=howler-step9-canonical-seed
VOLUME=howler-step9-canonical-seed-data
SEED_CLUSTER=howler-step9-seed-canonical-20260929
HOST_SEED_REPO=/tmp/opencode/step9-seed-canonical-20260929

# Pre-mutation local-daemon/resource gates. Never continue on a remote Docker endpoint or
# resource collision. Keep this directory empty before the seed is prepared.
ENDPOINT=$(docker --context default context inspect default --format '{{json .Endpoints.docker.Host}}')
python3 -c 'import json,sys; assert json.loads(sys.argv[1]).startswith("unix://")' "$ENDPOINT"
! docker --context default ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER"
! docker --context default volume ls --format '{{.Name}}' | grep -Fxq "$VOLUME"
! docker --context default network ls --format '{{.Name}}' | grep -Fxq "$NETWORK"
mkdir -p "$HOST_SEED_REPO"
test -z "$(find "$HOST_SEED_REPO" -mindepth 1 -print -quit)"

docker --context default network create --internal \
  --label howler.step9.rehearsal=true --label "howler.step9.run=$RUN" \
  --label howler.step9.role=network "$NETWORK"
docker --context default volume create \
  --label howler.step9.rehearsal=true --label "howler.step9.run=$RUN" \
  --label howler.step9.role=seed "$VOLUME"
docker --context default run -d --name "$CONTAINER" \
  --label howler.step9.rehearsal=true --label "howler.step9.run=$RUN" --label howler.step9.role=seed \
  --network "$NETWORK" \
  --mount "type=volume,source=$VOLUME,target=/usr/share/elasticsearch/data" \
  --mount "type=bind,source=$HOST_SEED_REPO,target=/usr/share/elasticsearch/snapshots" \
  -e discovery.type=single-node -e "cluster.name=$SEED_CLUSTER" -e xpack.security.enabled=false \
  -e path.repo=/usr/share/elasticsearch/snapshots -e 'ES_JAVA_OPTS=-Xms1g -Xmx1g' \
  docker.elastic.co/elasticsearch/elasticsearch:8.19.11
```

The seed-preparation command re-inspects the exact container ID/name, versioned image,
labels, local data volume and its labels, bind mount, no-published-port condition, private
IP/subnet, internal bridge/network labels, and exact network membership. It also checks
cluster name/UUID/version/health, `path.repo`, empty index inventory, an empty host snapshot
directory, and no existing seed repository **before** it sends a write request. A failed
gate means no fixture writes. After all Docker ownership gates, it performs a temporary
UID-1000 create/remove probe in the empty snapshot directory, then writes the fixture. A
failure after writes leaves only this dedicated seed for inspection—there is no automatic
delete/cleanup.

```bash
cd api
poetry run python build_scripts/upgrade_rehearsal.py \
  --prepare-synthetic-seed \
  --seed-container howler-step9-canonical-seed \
  --seed-network howler-step9-canonical-seed-network \
  --seed-volume howler-step9-canonical-seed-data \
  --seed-run-id canonical-seed-20260929 \
  --confirm-seed-cluster howler-step9-seed-canonical-20260929 \
  --seed-repository /tmp/opencode/step9-seed-canonical-20260929 \
  --seed-snapshot step9-canonical-20260929
```

The command exits only after verifying both explicit write aliases, frozen mappings, exact
document `_source` values/classifications, case links, successful snapshot state, snapshot
contents, and compatible version metadata. The canonical manifest (indices, write aliases,
mappings, IDs, and `_source`) SHA-256 is
`e8eccdeb9c1219ac50c7ad4e72e42991a08eccba39a3aa7aeb4d6604c0d5652e`.

## Run the rehearsal

The run copies (never modifies) the prepared repository into a new work directory. Both
paths must be local and readable by container UID 1000; do not nest the work directory in
the seed repository.

```bash
cd api
poetry run python build_scripts/upgrade_rehearsal.py \
  --seed-repository /tmp/opencode/step9-seed-canonical-20260929 \
  --seed-snapshot step9-canonical-20260929 \
  --work-dir /tmp/opencode/step9-run-canonical-20260929 \
  --run-id canonical-20260929 \
  --index-pattern 'howler-*' \
  --synthetic-fixture \
  --timeout 900
```

The rehearsal ES nodes have **no host-published ports**. The runner gets each exact
container's private IPv4 from `docker inspect`, verifies it against the network member/IPAM
entry and labelled internal bridge, then performs direct host-to-bridge-IP HTTP with
proxies disabled. The local Docker default context must use a Unix socket, and the Linux
host must route to its own internal bridge IPs. If a host cannot reach that IP, the run
aborts instead of publishing a port or switching to a non-internal network.

## Application ACL/query gate

Expected application behavior for a later executable verifier: an unrestricted Howler user
sees only the unrestricted hit; a restricted user sees both. Filtering the shared
`STEP9-SHARED` query token returns two hits for the restricted user; sorting by sequence
ascending returns unrestricted then restricted; the visibility aggregation has one bucket
document each. The RESTRICTED case links both hits.

This slice has no executable Howler authentication/ACL/query verifier or credentials.
Therefore the report always records `BLOCKED_UNAVAILABLE` and the command exits `3` with
`BLOCKED_APPLICATION_VERIFICATION_UNAVAILABLE`, even when every Elasticsearch phase passes.
There is no operator status/evidence file that can clear this gate. Do not claim application
or production PASS from the synthetic Elasticsearch rehearsal.

## Validation

```bash
cd api
poetry run pytest -q test/unit/test_upgrade_rehearsal.py
```

The mocked phase-order test verifies donor snapshot → fresh 8.19 restore/preflight →
same-volume 9.5.2 restart/UUID checks → independent fresh 8.19 rollback. Tests also cover
Docker seed ownership gates, no published ports/direct-IP verification, write-alias checks,
version-range metadata, malformed/failed restore responses, exact synthetic document
identity/case links, equal-count content substitution, and invalid cluster/UUID gates. They
do not start containers or access Elasticsearch.
