# Testing Architecture

Tests are split into two independent tiers. Each tier can run without the
tiers above it.

```bash
make test          →  unit + stub  (always safe, no infra)
make test-e2e      →  live Pi      (requires Pi reachable over SSH)
```

---

## Tier 1 — Unit & Stub (`tests/`)

Fast tests that run in the local virtualenv with no external dependencies.

**What's tested:**

| File | Covers |
| --- | --- |
| `test_models.py` | Pydantic validation, defaults, and field constraints for the shared models |
| `test_storage_utils.py` | Mount filtering, device classification, and SSH-stub variants of `get_real_mounts` / `get_block_devices` |
| `test_storage_flows.py` | `parse_path_hints` (pure function; interactive flows are E2E territory) |

SSH-dependent functions use `FakeConnection`, which returns canned JSON without opening a socket.

### Framework vs tests

The test framework lives in `tests/support/` and has no pytest dependency of
its own — it is plain Python that tests import:

```text
tests/support/
  connections.py   FakeConnection, FakeResult
  data.py          Canonical lsblk / findmnt JSON payloads
  builders.py      mnt(), disk(), partition() factory functions
```

`tests/conftest.py` is a thin adapter over `support/`.

---

## Tier 2 — E2E (`make test-e2e`)

Tests in `tests/e2e/` run against a real Pi over SSH. They are tagged
`@pytest.mark.e2e` and excluded from `make test` by default.

The `live_conn` fixture reads `HOST` from the environment and returns a live
Fabric `Connection`:

```bash
make test-e2e            # tests against rpi (default)
HOST=rpi2 make test-e2e  # tests against rpi2
```

Current E2E tests verify that `findmnt` and `lsblk` return plausible output
from a real Pi.

---

## Adding new tests

| I want to test… | Put it in… |
| --- | --- |
| A pure function or Pydantic model | `tests/test_*.py` |
| A function that calls `conn.run()` | `tests/test_*.py` with `FakeConnection` |
| A function that reads/writes files | `tests/test_*.py` with `tmp_path` + `monkeypatch` |
| Full SSH behavior against real hardware | `tests/e2e/` with `@pytest.mark.e2e` |
