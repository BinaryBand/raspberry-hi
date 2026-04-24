# IN BRIEF — Architecture (short)

This short, plain-English summary explains the repository's architecture for a junior programmer. It highlights the chief ideas, common workflows, and where to look for more detail.

## Big picture

- The repo separates *declared state* (Ansible) from *tooling and interactive helpers* (Python). Ansible is the single source of truth for provisioning.
- The Makefile is the operator-facing entry point; Python provides thin, testable CLIs (preflight, bootstrap, check, mount, rclone).
- Semgrep and repo checks enforce architecture rules (treat Semgrep failures as real architecture issues).

```mermaid
graph LR
  Operator[Operator (you)] --> Makefile[Makefile (operator entry)]
  Makefile --> Ansible[Ansible (declarative provisioning)]
  Makefile --> Scripts[Python scripts (preflight, check, bootstrap)]
  Scripts --> Vault[Vault (ansible/group_vars/all/vault.yml)]
  Scripts --> Registry[ansible/registry.yml]
  Registry --> Ansible
  Inventory[ansible/inventory/host_vars] --> Ansible
  Ansible --> Hosts[Target Hosts]
```

## Core rules (short)

- Ansible owns declared state. Python may read or update state only through narrow, dedicated seams (inventory and vault helpers).
- Python must not orchestrate Ansible playbooks or become a second source of truth.
- Secrets live in `ansible/group_vars/all/vault.yml`; `host_vars` must not contain durable secrets.

Example (how sudo passwords are looked up from the vault):

```yaml
ansible_become_password: "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
```

## Quick examples — common workflows

- Run the operator-friendly provisioning for an app (Baikal example):

```bash
make baikal HOST=raspi1
```

- Prompt for missing host vars and vault secrets (preflight):

```bash
python -m linux_hi.cli.preflight --host raspi1
# or the thin wrapper
scripts/preflight.py
```

Notes: app dependencies are documented in `ansible/registry.yml`. Provisioning order is enforced via tags in `ansible/site.yml`, not by `meta/main.yml` role dependencies.

```mermaid
graph LR
  registry[ansible/registry.yml] --> make[make baikal]
  make --> site[ansible/site.yml (tags)]
  site --> postgres[postgres role]
  site --> baikal[baikal role]
  postgres --> baikal
```

## Python layout (what to edit)

- `scripts/` — thin compatibility wrappers (entrypoints only).
- `linux_hi/cli/` — real CLI implementations and reusable logic.
- `linux_hi/` packages — split by responsibility: `ansible`, `orchestration`, `adapters`, `storage`, `vault`, `process`.

When you add a new CLI feature, put logic in `linux_hi/cli/` and keep `scripts/` minimal.

## Secrets & vault

- Durable secrets must be in the vault file: `ansible/group_vars/all/vault.yml`.
- Vault models are typed (see `models/services/vault.py`) — add keys there for typed secrets; app-specific keys are allowed as extras.

## Service adapters (how an app runs)

- The repo decouples app roles from init systems via `roles/service_adapter`.
- Supported backends: `systemd`, `cron`, `manual`.

Short summary of each:

- `systemd`: uses quadlets and `systemctl --user` (recommended where supported).
- `cron`: deploys a run script and schedules it with `@reboot`.
- `manual`: deploys run script only; operator wires it into the local init system.

## Storage policy (simple)

- Roles declare the data paths that must be persisted. The operator chooses the medium.
- Ansible owns the declared paths and is responsible for ensuring they exist and are mounted.

## Tests and checks

- Unit/stub tests live under `tests/` and are fast local checks.
- End-to-end tests live under `tests/e2e/` and run with `make test-e2e` against a reachable host.

Common commands:

```bash
make test         # unit + fast checks (excludes e2e)
make test-e2e HOST=raspi1
```

Static checks enforced in CI: Semgrep, ansible-lint, Ruff, Pyright, Vulture, duplication checks.

## Repo shape (at-a-glance)

- `ansible/` — roles, apps, inventory, registry, site.yml
- `scripts/` — thin wrappers for package CLIs
- `linux_hi/` — the package code (cli, adapters, vault, storage, orchestration)
- `models/` — typed models and ansible-access helpers
- `tests/` — unit, support, and e2e tests

## Working rules checklist (keep these in mind)

- Use `ansible_facts['key']` bracket-style access in templates.
- Use Pydantic models at Python/edge boundaries instead of untyped dicts.
- Keep top-level scripts thin and move logic into importable modules.
- Keep durable state changes behind `ansible` inventory/vault helpers.

---

For full detail or to resolve policy questions, see the authoritative text: `docs/ARCHITECTURE.md` and `docs/POLICY_CONTRACT.yml`.

If you'd like, I can run a quick lint or preview the rendered mermaid diagrams locally.
