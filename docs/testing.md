# Testing Architecture

Tests are split into three independent tiers. Each tier can run without the
tiers above it — you don't need a Pi to run the unit tests, and you don't need
Docker to run the E2E tests.

```
make test          →  unit + stub  (always safe, no infra)
make test-roles    →  Molecule     (requires Docker)
make test-e2e      →  live Pi      (requires Pi reachable over SSH)
```

---

## Tier 1 — Unit & Stub (`tests/`)

Fast tests that run in the local virtualenv with no external dependencies.
They cover all Python logic: models, utility functions, and file I/O.

**What's tested:**

| File | Covers |
|---|---|
| `test_models.py` | Pydantic validation, defaults, and field constraints for all five models |
| `test_storage_utils.py` | Mount filtering, device classification, and SSH-stub variants of `get_real_mounts` / `get_block_devices` |
| `test_ansible_utils.py` | `read_host_vars`, `write_host_vars`, `update_host_vars`, `read_role_defaults` — all via `tmp_path` |
| `test_storage_flows.py` | `parse_path_hints` (pure function; interactive flows are E2E territory) |

SSH-dependent functions are tested with `FakeConnection` — a stub that returns
pre-configured JSON without opening a socket. File-system helpers are tested
with pytest's built-in `tmp_path` fixture and `monkeypatch` to redirect
`ANSIBLE_DIR` away from the real inventory.

### Framework vs tests

The test framework lives in `tests/support/` and has no pytest dependency of
its own — it is plain Python that tests import:

```
tests/support/
  connections.py   FakeConnection, FakeResult
  data.py          Canonical lsblk / findmnt JSON payloads
  builders.py      mnt(), disk(), partition() factory functions
```

`tests/conftest.py` is a thin adapter: it declares pytest fixtures that wrap
`support/`, nothing more. This keeps framework code reusable and the fixture
file easy to scan.

---

## Tier 2 — Role Tests (`make test-roles`)

Ansible roles are tested with [Molecule](https://molecule.readthedocs.io).
Molecule creates an ephemeral Docker container, converges the role against it,
runs a verify playbook, then destroys the container.

Currently configured for the `storage` role
(`ansible/roles/storage/molecule/default/`):

- **converge.yml** — runs the role with `minio_data_path: /tmp/minio-test/data`
  and `brew_user: root`
- **verify.yml** — uses `ansible.builtin.stat` to assert the directory exists,
  is mode `0750`, and is owned by `root`

The Docker image (`geerlingguy/docker-debian12-ansible`) matches the Raspberry
Pi's Debian base and has Ansible pre-installed, so no setup tasks are needed in
converge.

Roles that depend on systemd (minio, podman) cannot be fully tested this way
without a systemd-capable container and belong in the E2E tier instead.

---

## Tier 3 — E2E (`make test-e2e`)

Tests in `tests/e2e/` run against a real Pi over SSH. They are tagged
`@pytest.mark.e2e` and excluded from `make test` by default
(`addopts = "-m 'not e2e'"` in `pyproject.toml`).

The `live_conn` fixture (defined in `tests/e2e/conftest.py`) reads `HOST` from
the environment — the same convention used by the Makefile — and returns a live
Fabric `Connection`:

```bash
make test-e2e            # tests against rpi (default)
HOST=rpi2 make test-e2e  # tests against rpi2
```

Current E2E tests verify that `findmnt` and `lsblk` return plausible output
from a real Pi: a root mount exists, all mounts have a source and fstype, and
the SD card is correctly classified as a system device.

---

## Adding new tests

| I want to test… | Put it in… |
|---|---|
| A pure function or Pydantic model | `tests/test_*.py` |
| A function that calls `conn.run()` | `tests/test_*.py` with `FakeConnection` |
| A function that reads/writes files | `tests/test_*.py` with `tmp_path` + `monkeypatch` |
| An Ansible role | `ansible/roles/<role>/molecule/default/` |
| Full SSH behaviour against real hardware | `tests/e2e/` with `@pytest.mark.e2e` |
