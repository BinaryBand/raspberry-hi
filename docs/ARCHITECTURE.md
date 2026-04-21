# Architecture: Declarative Ansible + Standalone Python

## Authority

This repository has two architecture authorities with different jobs.

- [.semgrep.yml](../.semgrep.yml) is the enforceable authority. It defines the repository rules that must hold mechanically.
- This document is the explanatory authority. It explains why the rules exist, how the seams are intended to work, and which patterns are architectural rather than incidental.

When the two disagree, treat [.semgrep.yml](../.semgrep.yml) as the source of truth for what contributors may or may not do, then fix this document to match.

---

## Constitutional Rule

This repository separates declared state from operational tooling.

- Ansible is the sole provisioning driver.
- Python handles interactive, one-shot, and pre-flight operations.
- Ansible-owned state stays authoritative. Python may read or update it through narrow seams, but it must not become a second source of truth.
- The boundary is intentional. Ansible does not call Python to decide state, and Python does not orchestrate playbook execution.

This rule is enforced in Semgrep by forbidding Python-side playbook orchestration, raw `ansible-vault` access outside the vault helper, and direct inventory/vault writes outside their dedicated seams.

---

## Domain Vocabulary

| Term | Meaning |
| --- | --- |
| `HOST` | Inventory alias for the target host. All operator-facing make targets accept `HOST=<alias>`. |
| `host_vars` | Per-host YAML files in `ansible/inventory/host_vars/` containing connection and host-specific declared settings. |
| `vault` | The encrypted durable secret store at `ansible/group_vars/all/vault.yml`. |
| `app_user_home` | Home directory for `ansible_user` on the target host. App roles use it for config, scripts, and quadlet paths. |
| `service_adapter_backend` | Init-system adapter selected for app lifecycle management. Supported values are `systemd`, `cron`, and `manual`. |
| `quadlet` | A systemd `.container` unit file used by rootless Podman services. |
| `preflight` | Python-side prompting and persistence of any missing host vars or vault secrets required before a role can converge. |

---

## Secret Policy

Durable secrets live in `ansible/group_vars/all/vault.yml`.

The vault model in `models/services/vault.py` holds:

- Static app credentials such as `minio_root_user` and `minio_root_password`
- A `become_passwords` mapping keyed by inventory hostname

Each host inventory file references that mapping dynamically:

```yaml
ansible_become_password: "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
```

This keeps sudo credentials centralized and out of `host_vars`.

`ansible/site.yml` includes an always-on assertion that the current host has a `become_passwords` entry, so provisioning fails early with a clear error.

Semgrep enforces the secret boundary by rejecting secret-like keys in `host_vars`, rejecting plaintext secrets in non-vault `group_vars`, and requiring the shared `ansible_become_password` vault lookup template.

---

## Python Structure

Top-level files in `scripts/` are entry points. Importable support code lives below them.

Canonical importable CLI modules live in `linux_hi/cli/`. The matching files in `scripts/` are compatibility wrappers only.

### Entry points

- `scripts/bootstrap.py`: first-time vault setup and missing secret collection
- `scripts/check.py`: prerequisite checks and minimal reachability validation
- `scripts/preflight.py`: registry-driven prompting for missing host vars and vault secrets
- `scripts/mount.py`: interactive storage mounting via Fabric
- `scripts/rclone.py`: capture local rclone config into the vault

Top-level scripts are entry points only. Shared logic belongs in importable packages, with `scripts/` kept as a thin compatibility layer.

### Package naming policy

Generic package names are transitional, not preferred.

- Prefer responsibility names such as `orchestration`, `adapters`, `ansible`, `storage`, `vault`, and `process`.
- Do not introduce new generic buckets such as `internal` or `utils` when a responsibility name would describe the module's job more clearly.
- Existing `scripts/internal/` and `scripts/utils/` packages are compatibility names. When packaging work next moves files across boundaries, rename those packages toward responsibility-oriented names instead of expanding the generic buckets.

### Internal orchestration

`scripts/internal/` contains orchestration objects that compose smaller ports or helpers without becoming standalone CLI entry points.

- `mount_orchestrator.py` composes an `InfoPort` with a `Prompter`
- `rclone_controller.py` composes vault I/O with overwrite confirmation

This layer exists to keep interactive control flow testable without mixing it into terminal-facing scripts.

### Utilities

`scripts/utils/` contains narrow seams around process execution, inventory access, vault access, storage discovery, YAML I/O, and other reusable helpers.

Important boundaries:

- `exec_utils.py` is the subprocess seam.
- `vault_service.py` is the `ansible-vault` seam.
- `models/ansible/access.py` exposed as `ANSIBLE_DATA` is the canonical registry and inventory store seam.
- `inventory_service.py` is a thin host-discovery wrapper over that store boundary.
- `ansible_utils.py` is a compatibility facade for non-store operational helpers only.
- `ansible_connection.py` is the Fabric connection seam.
- `yaml_utils.py` and `models/` type YAML and inventory boundaries.

Semgrep enforces these boundaries directly.

---

## Python Entry Point Policy

### `scripts/bootstrap.py`

Compatibility wrapper for `linux_hi.cli.bootstrap`. The package entrypoint owns first-time vault setup, may read `ansible/inventory/hosts.ini`, prompt for credentials, and write the encrypted vault.

### `scripts/check.py`

Compatibility wrapper for `linux_hi.cli.check`. The package entrypoint owns prerequisite validation, may verify local prerequisites, decrypt the vault, assert required secret completeness, and perform a minimal reachability check.

### `scripts/preflight.py`

Compatibility wrapper for `linux_hi.cli.preflight`. The package entrypoint owns registry-driven prompting before provisioning. App metadata is loaded from `ansible/registry.yml`, role-required vars are inferred from `defaults/main.yml`, and any missing values are written through the dedicated inventory and vault helpers.

### `scripts/mount.py`

Compatibility wrapper for `linux_hi.cli.mount`. The package entrypoint owns interactive storage mounting. It may read inventory and vault data, open a Fabric session, and make direct remote changes.

### `scripts/rclone.py`

Compatibility wrapper for `linux_hi.cli.rclone`. The package entrypoint owns rclone vault setup. It reads `~/.config/rclone/rclone.conf` locally and saves the config blob into the vault so the `rclone` Ansible role can deploy it to hosts. No SSH or Fabric session is opened.

---

## Makefile Policy

The Makefile is the operator-facing entry point.

- Provisioning commands flow through `make`, not through Python wrappers around `ansible-playbook`.
- `_vault_check` runs `python -m linux_hi.cli.check --vault-only` before workflows that require decrypted secrets.
- `HOST=<alias>` is the standard multi-host selector for both provisioning and operational commands.

Missing prerequisites should be rejected at the edge of the workflow.

---

## App and Dependency Policy

App metadata is centralized in `ansible/registry.yml`.

Each app entry declares:

- service type
- lifecycle participation such as backup, restore, and cleanup
- preflight host vars
- required vault secrets
- explicit repo-owned dependencies

The current example is Baikal depending on PostgreSQL.

That dependency is declared in the registry for tooling and documentation, but provisioning order is enforced in `ansible/site.yml` through tag composition, not through `meta/main.yml` role dependencies:

- `postgres` is tagged with both `postgres` and `baikal`
- `baikal` is tagged with `baikal`
- `make baikal` therefore runs PostgreSQL first without relying on role metadata dependencies

`meta/main.yml` dependencies must stay empty for these roles. Non-empty role dependencies cause duplicate execution under tag-based runs and are forbidden by Semgrep.

This pattern is for repo-owned service relationships, not hidden external prerequisites.

---

## Service Adapter Policy

App roles are decoupled from init-system specifics through `ansible/roles/service_adapter/`.

Supported backends are defined in `ansible/roles/service_adapter/defaults/main.yml`:

- `systemd`
- `cron`
- `manual`

The backend is auto-detected from `ansible_facts['service_mgr']` by default, but host-specific overrides may set one of those literal values in `host_vars`.

Backend responsibilities:

- `systemd`: quadlets, linger, and `systemctl --user`
- `cron`: deploy a run script and schedule it with `@reboot`
- `manual`: deploy the run script only and leave init-system wiring to the operator

For OpenRC or runit targets, use `manual` and wire the generated run script into the local init system manually.

---

## Storage Policy

Application data paths must be explicitly declared, but the storage medium is an operator choice.

- Persistence is required.
- The medium is an operator choice.
- Mount workflows are optional helpers.

The governing rule is that Ansible owns the declared path, not the storage medium. MinIO and PostgreSQL require durable paths, not specifically external media.

---

## Testing Model

Tests are split into two tiers.

### Tier 1: unit and stub tests

`tests/` contains fast tests that run locally without infrastructure.

This tier covers:

- model validation
- storage discovery and policy logic
- inventory and ansible utility helpers
- script control-flow and orchestration objects
- registry-backed app contracts

SSH-dependent logic uses `tests/support/FakeConnection` and canned payloads from `tests/support/data.py`.

### Tier 2: end-to-end tests

`tests/e2e/` contains live host tests marked `@pytest.mark.e2e`.

- `make test` excludes them
- `make test-e2e` runs them against a reachable host
- `HOST=<alias>` selects the live target

### Static architecture checks

The repository treats Semgrep, ansible-lint, Ruff, Pyright, Vulture, and duplication checks as part of the maintainability model, not just style tooling.

---

## Repository Shape

```text
ansible/
  apps/            declarative app roles (minio, postgres, baikal, restic)
  roles/           shared declarative roles (podman, rclone, service_adapter, auto-updates)
  inventory/
    hosts.ini
    host_vars/     per-host connection details and host-specific declared settings
  group_vars/all/
    vars.yml       shared non-secret variables
    vault.yml      encrypted durable secrets
  registry.yml     app metadata consumed by Python tooling and tests
  site.yml         single provisioning entry point

scripts/
  bootstrap.py     compatibility wrapper for package bootstrap CLI
  check.py         compatibility wrapper for package check CLI
  preflight.py     compatibility wrapper for package preflight CLI
  mount.py         compatibility wrapper for package mount CLI
  rclone.py        compatibility wrapper for package rclone CLI
  internal/        orchestration layer for interactive workflows
  utils/           helper seams around subprocesses, vault, inventory, storage, and YAML

linux_hi/
  cli/             canonical importable CLI modules

models/
  ansible/         typed access to registry and host_vars data
  services/        vault secrets model
  system/          block-device and mount models

tests/
  support/         non-pytest fakes, builders, and canned data
  e2e/             live host checks
  test_*.py        fast local contract, unit, and stub tests
```

---

## Working Rules

- Use `ansible_facts['key']` bracket notation instead of top-level injected fact variables.
- Use Pydantic models at data boundaries rather than untyped dict plumbing.
- Keep top-level scripts thin and move reusable logic downward.
- Keep durable state changes behind the dedicated inventory and vault helpers.
- Treat Semgrep failures as architecture failures, not stylistic warnings.

Ansible declares and converges durable state. Python assists through narrow seams. Semgrep keeps the boundary from drifting.
