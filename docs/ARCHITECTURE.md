# Architecture: Declarative Ansible + Standalone Python

## Authority

This repository has two architecture authorities with different jobs.

- [.semgrep.yml](../.semgrep.yml) is the enforceable authority. It defines the repository rules that must hold mechanically. (Enforcement: [docs/POLICY_CONTRACT.yml](docs/POLICY_CONTRACT.yml#L5-L11); Semgrep rules: [.semgrep.yml](.semgrep.yml))
- This document is the explanatory authority. It explains why the rules exist, how the seams are intended to work, and which patterns are architectural rather than incidental.

When the two disagree, treat [.semgrep.yml](../.semgrep.yml) as the source of truth for what contributors may or may not do, then fix this document to match.

---

## Constitutional Rule

This repository separates declared state from operational tooling.

- Ansible is the sole provisioning driver.
- Python handles interactive, one-shot, and pre-flight operations.
- Ansible-owned state stays authoritative. Python may read or update it through narrow seams, but it must not become a second source of truth. (Enforcement: [docs/POLICY_CONTRACT.yml](docs/POLICY_CONTRACT.yml#L13-L20))
- The boundary is intentional. Ansible does not call Python to decide state, and Python does not orchestrate playbook execution.

This rule is enforced in Semgrep by forbidding Python-side playbook orchestration, raw `ansible-vault` access outside the vault helper, and direct inventory/vault writes outside their dedicated seams. (Semgrep rules: [.semgrep.yml](.semgrep.yml) — see `python-must-not-run-ansible-playbook`, `python-ansible-vault-only-in-vault-service`, `python-ruamel-yaml-only-in-ansible-access`, `python-no-ansible-inventory-cli`.) Repo-level checks also validate playbook-level variables via [linux_hi/policy_utils.py](linux_hi/policy_utils.py#L120-L132).

---

## Domain Vocabulary

| Term | Meaning |
| --- | --- |
| `HOST` | Inventory alias for the target host. All operator-facing make targets accept `HOST=<alias>`. |
| `host_vars` | Per-host YAML files in `ansible/inventory/host_vars/` containing connection and host-specific declared settings. |
| `vault` | The encrypted durable secret store at `ansible/group_vars/all/vault.yml`. |
| `app_user_home` | Home directory for `ansible_user` on the target host. App roles use it for config and quadlet paths. |
| `service_adapter_backend` | Init-system adapter selected for app lifecycle management. Supported values are `systemd`, `cron`, and `manual`. |
| `quadlet` | A systemd `.container` unit file used by rootless Podman services. |
| `preflight` | Python-side prompting and persistence of any missing host vars or vault secrets required before a role can converge. |

---

## Secret Policy

Durable secrets live in `ansible/group_vars/all/vault.yml`.

The vault model in `models/services/vault.py` uses a typed core plus allowed extras:

- Explicit typed fields include shared operational secrets such as `become_passwords`, `rclone_config`, and `restic_password`
- App-specific credentials (for example `minio_root_user` and `minio_root_password`) are accepted as additional keys and remain valid durable vault state

Each host inventory file references that mapping dynamically:

```yaml
ansible_become_password: "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
```

This keeps sudo credentials centralized and out of `host_vars`.

`ansible/playbooks/setup.yml` includes an always-on assertion that the current host has a `become_passwords` entry, so provisioning fails early with a clear error. Each per-app playbook (`ansible/apps/<app>/playbook.yml`) carries the same assertion.

Semgrep enforces the secret boundary by rejecting secret-like keys in `host_vars`, rejecting plaintext secrets in non-vault `group_vars`, and requiring the shared `ansible_become_password` vault lookup template.

---

## Python Structure

Canonical importable CLI modules live in `linux_hi/cli/`.

### Package naming policy

Generic package names are transitional, not preferred.

- Prefer responsibility names such as `orchestration`, `adapters`, `ansible`, `storage`, `vault`, and `process`.
- Do not introduce new generic buckets such as `internal` or `utils` when a responsibility name would describe the module's job more clearly.
(Enforcement: Semgrep: [.semgrep.yml](.semgrep.yml) — `python-no-compatibility-namespace-imports`; Repo check: [linux_hi/policy_utils.py](linux_hi/policy_utils.py#L135-L144).)

### Orchestration

`linux_hi/orchestration/` is the canonical orchestration layer. It composes ports and helpers without becoming standalone CLI entry points.

- `mount_orchestrator.py` composes an `InfoPort` with a `Prompter`
- `rclone_controller.py` composes vault I/O with overwrite confirmation

This layer exists to keep interactive control flow testable without mixing it into terminal-facing scripts.

### Responsibility Packages

The canonical import surface is organized by responsibility:

Important boundaries:

- `linux_hi/process/` is the subprocess seam.
- `linux_hi/vault/` is the `ansible-vault` seam.
- `models/ansible/access.py` exposed as `ANSIBLE_DATA` is the canonical registry and inventory store seam.
- `linux_hi/ansible/` contains inventory discovery, role-var introspection, connection setup, and YAML boundary helpers.
- `linux_hi/adapters/` contains protocols and adapter implementations for interactive workflows.
- `linux_hi/storage/` contains storage discovery, classification, display, and rclone parsing helpers.

Semgrep enforces these boundaries directly (see [.semgrep.yml](.semgrep.yml) for rules such as `python-no-direct-subprocess-import`, `python-no-direct-subprocess-call`, and `python-ruamel-yaml-only-in-ansible-access`).

---

## Makefile Policy

The Makefile is the operator-facing entry point.

- Provisioning commands flow through `make`, not through Python wrappers around `ansible-playbook`.
- `_vault_check` runs `python -m linux_hi.cli.check --vault-only` before workflows that require decrypted secrets.
- `HOST=<alias>` is the standard multi-host selector for both provisioning and operational commands.

Missing prerequisites should be rejected at the edge of the workflow.

### Make Style Contract

All Makefile changes must satisfy this contract: (Enforcement: [docs/POLICY_CONTRACT.yml](docs/POLICY_CONTRACT.yml#L22-L29); Semgrep: [.semgrep.yml](.semgrep.yml) — `make-no-direct-poetry-run`, `make-no-hardcoded-py-dirs`; Repo check: [linux_hi/policy_utils.py](linux_hi/policy_utils.py#L214-L226))

- Public operator targets are `.PHONY` and appear in `make help` with a one-line description.
- Public target names use lowercase kebab style (`format-check`, `backup-check`) and read as verbs or verb-noun actions.
- Internal workflow targets are prefixed with `_` and are not listed as operator-facing commands.
- Shared command fragments and reusable values live in variables to avoid repeating long command lines.
- Targets that require runtime inputs fail fast with explicit guard checks and actionable error messages.
- Operator-facing workflows must keep `HOST=<alias>` support and default to the repo standard host selector. (Enforcement: [docs/POLICY_CONTRACT.yml](docs/POLICY_CONTRACT.yml#L31-L37))
- Makefile style is machine-checked with `mbake` (`make checkmake`) and included in CI quality gates.

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

That dependency is declared in the registry and enforced at two levels:

- `linux_hi.cli.preflight` walks `registry.yml` dependencies depth-first, so `make baikal` automatically prompts for any missing PostgreSQL vars before Baikal's own preflight runs.
- `ansible/apps/baikal/playbook.yml` opens with `import_playbook: ../postgres/playbook.yml`, so Ansible converges PostgreSQL before Baikal during provisioning.

Both files are generated from `registry.yml` and must not be edited by hand. Run `make generate-apps` to regenerate after registry changes.

`meta/main.yml` dependencies must stay empty for these roles. (Enforcement: [docs/POLICY_CONTRACT.yml](docs/POLICY_CONTRACT.yml); Semgrep: [.semgrep.yml](.semgrep.yml) — `ansible-meta-no-non-empty-dependencies`.) Non-empty role dependencies cause duplicate execution under per-app playbook invocation and are forbidden by Semgrep.

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

(Enforcement: Semgrep: [.semgrep.yml](.semgrep.yml) — `host-vars-service-adapter-backend-literal`.)

---

## Storage Policy

Application data paths must be explicitly declared (Enforcement: [docs/POLICY_CONTRACT.yml](docs/POLICY_CONTRACT.yml#L46-L51)), but the storage medium is an operator choice.

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

See Semgrep rules in [.semgrep.yml](.semgrep.yml) and repo-level policy validations in [linux_hi/policy_utils.py](linux_hi/policy_utils.py#L177-L212).

---

## Repository Shape

```text
ansible/
  apps/            declarative app roles (minio, postgres, baikal, restic)
  roles/           shared declarative roles (podman, rclone, service_adapter, auto-updates)
  inventory/
    hosts.yml
    host_vars/     per-host connection details and host-specific declared settings
  group_vars/all/
    vars.yml       shared non-secret variables
    vault.yml      encrypted durable secrets
  registry.yml     app metadata consumed by Python tooling and tests
  setup.yml        base provisioning playbook (auto-updates, podman, rclone)

linux_hi/
  cli/             canonical importable CLI modules
  orchestration/   orchestration flows composed from adapters and stores
  adapters/        protocols and adapter implementations
  ansible/         ansible-facing helpers and typed YAML boundaries
  storage/         storage and rclone helpers
  vault/           vault access helpers
  process/         process execution helpers

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
- Keep durable state changes behind the dedicated inventory and vault helpers.
- Treat Semgrep failures as architecture failures, not stylistic warnings.

(Enforcement examples: Semgrep rule `ansible-facts-top-level-injection` in [.semgrep.yml](.semgrep.yml).)

Ansible declares and converges durable state. Python assists through narrow seams. Semgrep keeps the boundary from drifting.
