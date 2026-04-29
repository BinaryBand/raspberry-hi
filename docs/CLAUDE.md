# Claude Code Context

This file is loaded at the start of every Claude session. Read it before making changes.

---

## What This Project Is

Ansible + Python tooling for provisioning rootless Podman containers on personal Linux systems. Apps run as a non-root user via systemd quadlets. The Python layer handles interactive pre-provisioning (prompts, vault writes, host_vars); Ansible handles idempotent convergence.

---

## Quick Reference

```bash
make test              # run full test suite (includes lint + policy checks)
make generate-apps     # regenerate group_vars/all/vars.yml from registry.yml (fast, idempotent)
make lint              # full static quality gate (ruff, ty, semgrep, cpd, vulture, lizard, ansible-lint, mbake, policy)
make check             # validate prerequisites (vault password, inventory)
HOST=debian make <app> # provision an app (runs preflight automatically)
```

**After any change to `ansible/registry.yml`:** run `make generate-apps` before running tests or provisioning.

---

## Architecture in One Paragraph

`ansible/registry.yml` is the single source of truth. `make generate-apps` reads it and emits `group_vars/all/vars.yml` (gitignored; regenerate after registry changes or fresh checkout). Per-app `playbook.yml` files are committed to git. The Python CLI layer (`linux_hi/`) handles the interactive pre-provisioning steps (preflight prompts, vault writes) and enforces structural policy (`linux_hi/policy/`). Ansible handles the actual convergence. The boundary between them is intentional and enforced by Semgrep.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architectural contract and rationale.

---

## File Layout

```text
ansible/
  registry.yml         single source of truth for all app metadata
  apps/<app>/          Ansible role per app
    defaults/main.yml  hand-authored defaults (nulls for required vars, app-specific values)
    tasks/main.yml     4-step pattern: guards → config/dirs → image → quadlet → service_adapter
    playbook.yml       committed; import_playbook chain + pre_tasks
  roles/               shared roles (service_adapter, rclone, podman, auto-updates)
  group_vars/all/
    vars.yml           GENERATED — shared non-secret vars (service names, ports, shared_vars)
    vault.yml          encrypted secrets (ansible-vault)
  inventory/
    hosts.yml          inventory (managed via `make config-hosts-*`)
    host_vars/         per-host vars (managed via preflight and `make config-hosts-*`)

linux_hi/cli/          operator-facing entry points (check, preflight, generate_apps, etc.)
linux_hi/policy/       structural repo checks (run as part of make test via TestRepoPolicy)
models/ansible/        typed access to registry and host_vars (ANSIBLE_DATA singleton)
tests/                 fast unit + lint tests; e2e/ requires a live host
```

---

## Key Conventions

### 4-step task pattern (ansible/apps/\<app\>/tasks/main.yml)

1. **Guards** — `assert` that required vars are set (`var is not none`)
2. **Config and directories** — create data dirs, write config templates, chown for rootless UID
3. **Image pull** — `podman pull` before deploying the quadlet (avoids systemd timeout on slow connections)
4. **Quadlet + service_adapter** — install the `.container` unit file, register with `service_adapter`

### Registry as source of truth

- `service_name`, `image`, `port`, `runtime_uid`, `runtime_gid`, `shared_vars`, and `global_vars` belong in `registry.yml`, not in `defaults/main.yml`
- `defaults/main.yml` holds only: nulled required vars (`~`), app-specific values not in the registry, and Jinja2 references to vars from other roles
- If a var is in both `registry preflight_vars` (with a default) and `defaults/main.yml`, the role default is redundant — remove it to avoid drift conflicts caught by `TestRepoPolicy`

### Rootless Podman specifics

- Containers run as the `ansible_user` (rootless Podman), not root
- Apps with a dedicated `runtime_uid` need `podman unshare chown -R <uid>:<gid>` on their data dir — do this **after** writing config files, not before
- Do **not** use the `:U` volume flag in quadlet templates — it overrides the manual chown at container start
- `host.containers.internal` (from `postgres_host_access_name`) is the hostname containers use to reach the host
- Networking uses `pasta` (not `--network=host` or uidmap)

### YAML libraries

- `pyyaml` (`import yaml`) is for all read-only YAML parsing throughout the codebase
- `ruamel.yaml` is restricted to `models/ansible/access.py` only — for round-trip writes to inventory files that preserve formatting
- This split is intentional and enforced by the `python-ruamel-yaml-only-in-ansible-access` Semgrep rule. Do not add `from ruamel.yaml import` elsewhere.

### Semgrep boundaries (treat violations as architecture failures)

- Python must not call `ansible-playbook` directly
- `ansible-vault` CLI is only called from `linux_hi/vault/service.py`
- Writes to `host_vars/` and `group_vars/` are only allowed in `models/ansible/access.py`, `linux_hi/vault/service.py`, and `linux_hi/cli/generate_apps.py`
- `ruamel.yaml` imports are only allowed in `models/ansible/access.py`

---

## Common Pitfalls

**Generated files not present after fresh clone** — run `make generate-apps` first. App `make` targets now auto-detect and run this if files are missing, but tests and direct Ansible invocations will not.

**Policy check failures in tests** — `make test` includes `TestRepoPolicy`, which runs the full structural policy check against the actual project. If it fails, the failure message is specific. Common causes: new app not in registry, preflight var default conflicts between registry and role defaults.

**Vault decrypt error** — the vault password file must exist at `ansible/.vault-password`. Run `make bootstrap` on first setup.

**`become_passwords` not set** — the `setup.yml` pre_tasks assert will fail. Add the host's become password to the vault via `make config-vault-add NAME=become_passwords` or `make bootstrap`.

---

## Adding a New App

See [ADDING_AN_APP.md](ADDING_AN_APP.md) for the full guide. The checklist:

1. Add entry to `ansible/registry.yml` (service_type, image, port, runtime_uid/gid if needed, preflight_vars, vault_secrets)
2. Create `ansible/apps/<app>/` with tasks, defaults, templates, handlers
3. Write `ansible/apps/<app>/playbook.yml` (see existing apps for the pattern)
4. `make generate-apps` — regenerates `group_vars/all/vars.yml`
5. Update `tests/test_ansible_apps.py` expected app lists
6. `make test` — all tests must pass including `TestRepoPolicy`

**Note:** `ADDING_AN_APP.md` uses `service_name_var` in its example — that field was replaced by `service_name` (the value directly). Use `service_name: myapp` in the registry.

---

## Testing

```bash
make test                        # full suite: unit + lint + policy (fast, no infra)
make test-e2e HOST=debian        # live host tests (requires reachable host)
poetry run pytest tests/test_ansible_apps.py -v   # just the registry contract tests
poetry run pytest tests/test_lint.py::TestRepoPolicy -v  # just the policy check
```

Tests are in two tiers: fast local tests in `tests/` and live host tests in `tests/e2e/` (excluded from `make test` by default). The `tests/support/` directory contains fakes and builders — prefer these over mocking when testing interactive flows.
