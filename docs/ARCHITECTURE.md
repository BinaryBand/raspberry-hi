# Architecture: Declarative Ansible + Standalone Python

## Constitutional Rule

This repository separates declared state from operational tooling.

- **Ansible** is the sole provisioning driver.
- **Python** handles interactive, one-shot, and pre-flight operations.
- **Ansible-owned state stays authoritative.** Python may read or update it through
  narrow seams, but it must not become a second source of truth.
- **The boundary is intentional.** Ansible does not call Python to decide state, and
  Python does not orchestrate playbook execution.

---

## Secret Policy

Durable secrets live in [ansible/group_vars/all/vault.yml](ansible/group_vars/all/vault.yml).

The vault model in [models/services/vault.py](models/services/vault.py) holds:

- Static app credentials such as `minio_root_user` and `minio_root_password`
- A `become_passwords` mapping keyed by inventory hostname:

  ```yaml
  become_passwords:
    rpi: "..."
    rpi2: "..."
  ```

Each host inventory file references that mapping dynamically:

```yaml
ansible_become_password: "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
```

This keeps sudo credentials centralized and out of `host_vars`.

[ansible/site.yml](ansible/site.yml) includes an always-on assertion that the current
host has a `become_passwords` entry, so provisioning fails early with a clear error.

---

## Python Entry Point Policy

### [scripts/bootstrap.py](scripts/bootstrap.py)

This script owns first-time vault setup. It may read [ansible/inventory/hosts.ini](ansible/inventory/hosts.ini),
prompt for credentials, and write the encrypted vault.

### [scripts/check.py](scripts/check.py)

This script owns pre-flight validation. It may verify local prerequisites, decrypt the
vault, assert required secret completeness, and perform a minimal reachability check.

### [scripts/mount.py](scripts/mount.py)

This script owns interactive storage mounting. It may read inventory and vault data,
open a Fabric session, and make direct remote changes.

---

## Makefile Policy

The Makefile is the operator-facing entry point. The `_vault_check` target runs
[scripts/check.py](scripts/check.py) in `--vault-only` mode before provisioning or mount
targets:

```makefile
site minio baikal mount: _vault_check
```

Missing prerequisites should be rejected at the edge of the workflow.

---

## App Dependency Policy

Application roles may depend on other app roles when the dependent service is part of
the same declared stack.

- **Dependencies must be explicit** in role metadata.
- **The dependency remains declarative.** Ansible resolves ordering through metadata
  and playbook tags.
- **Operator entry points should still exist.** A dependency may still have its own
  `make` target.

The current example is Baikal depending on PostgreSQL:

- [ansible/apps/baikal/meta/main.yml](ansible/apps/baikal/meta/main.yml) declares the
  dependency on the `postgres` app role.
- [ansible/site.yml](ansible/site.yml) tags both roles so `make postgres` works as an
  explicit operator action and `make baikal` still includes the database path.

This pattern is for repo-owned services, not hidden external prerequisites.

---

## Storage Policy

Application data paths must be explicitly declared, but the storage medium is an
operator choice.

- **Persistence is required.**
- **The medium is an operator choice.**
- **Mount workflows are optional helpers.**

The governing rule is that Ansible owns the declared path, not the storage medium.

---

## Repository Shape

```text
ansible/
  apps/            ← declarative roles (minio, postgres, baikal, …)
  roles/           ← declarative roles (storage, podman, auto-updates, …)
  inventory/
    hosts.ini
    host_vars/     ← per-host connection details + become_password reference
  group_vars/all/
    vault.yml      ← encrypted secrets (become_passwords dict + app creds)
  site.yml         ← single entry point with always-on vault assert

scripts/
  bootstrap.py     ← vault setup (pre-Ansible, no Ansible subprocess)
  check.py         ← pre-flight checks including vault completeness
  mount.py         ← interactive storage mount via Fabric
  utils/
    ansible_utils.py   ← inventory parsing helpers (no playbook invocation)
    storage_utils.py   ← SSH helpers: lsblk, mount detection
    storage_flows.py   ← TUI flows for device selection

models/
  services/vault.py    ← Pydantic model for vault secrets
  ansible/hostvars.py  ← Pydantic model for host_vars
  system/              ← BlockDevice, MountInfo data models
```

Ansible declares and converges durable state. Python assists through narrow seams.
App-to-app dependencies may exist when they stay explicit and repo-owned.
