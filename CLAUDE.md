# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make lint              # full quality gate: ruff, format-check, pyright, semgrep, cpd, vulture, ansible-lint
make test              # run all unit + contract tests
poetry run pytest tests/test_ansible_apps.py::TestClass::test_name -v  # single test
make <app>             # preflight + provision a named app (minio, postgres, baikal, restic)
make site              # provision base infrastructure only (no apps)
make backup            # back up all apps via restic
make restore APP=<app> # restore a single app from its latest snapshot
make cleanup APP=<app> # remove app and all data from the host
make rclone            # capture local rclone config into vault
make bootstrap         # first-time vault + credential setup
make check             # validate prerequisites (vault file, host reachability)
```

## Architecture

This repo automates provisioning a Linux server using Python + Ansible.

**Two layers:**

- `scripts/` — interactive Python (prompting, validation, bootstrap); runs on the operator's machine
- `ansible/` — declarative Ansible (idempotent provisioning); runs against the remote host

**Entry point:** `Makefile` orchestrates both layers. Never invoke `ansible-playbook` directly
from Python (Semgrep rule `python-must-not-run-ansible-playbook` enforces this).

**App contract:** Every app under `ansible/apps/<app>/` must declare:

- `tasks/main.yml` — provisioning (must call `include_role name: service_adapter`)
- `tasks/cleanup.yml` — teardown (must call `service_adapter tasks_from: teardown`)
- `backup/main.yml` — backup (must call `include_role name: restic tasks_from: backup`)
- `restore/main.yml` — restore
- `preflight.yml` — YAML spec declaring `var_hints` and `vault_secrets` for operator prompting

`scripts/preflight.py` reads `preflight.yml` and drives the interactive prompting flow.
`_SERVICELESS_APPS` (currently `{"restic"}`) exempts tool apps from containerised-service
contract tests.

**Service adapter:** `ansible/roles/service_adapter` abstracts init-system differences. Apps
call it instead of hardcoding systemd.

**Backup flow:** `make backup` → `ansible/backup.yml` → each app's `backup/main.yml` gathers
data → `include_role name: restic tasks_from: backup` → snapshots to `rclone:<remote>:<path>`
→ single global prune at end.

**Secrets:** Vault at `ansible/group_vars/all/vault.yml` (ansible-vault encrypted). Python model
at `models/services/vault.py` (`VaultSecrets`). `host_vars` must never store secret-like keys
(Semgrep rule `host-vars-no-inline-secret-keys`).

**Tests:** `tests/test_ansible_apps.py` has structural contract tests enforcing the app wiring
contract. `tests/test_lint.py` runs ansible-lint programmatically. Both use `_all_apps()` /
`_containerized_apps()` helpers that glob `ansible/apps/*/tasks/main.yml`.

**Key Semgrep rules (`.semgrep.yml`):**

- Subprocess must go through `scripts/utils/exec_utils.py`
- No `ansible-playbook` invocation from Python
- No inline secrets in `host_vars` or plain `group_vars`
- No `include_vars` in lifecycle playbooks (cleanup/backup/restore)
- No `:latest` image tags
- No top-level Ansible fact injection — use `ansible_facts['key']` bracket notation
