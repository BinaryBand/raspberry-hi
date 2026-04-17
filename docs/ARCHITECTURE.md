# Architecture: Declarative Ansible + Standalone Python

## Constitutional Rule

This repository separates durable declared state from interactive operational tooling.

- **Ansible** is the sole provisioning driver. It reads declared state from inventory
  and the vault, and converges the host toward that state.
- **Python** exists to support interactive, one-shot, or pre-flight operations that do
  not fit a declarative playbook model.
- **Ansible-owned state remains authoritative.** Python may read it, validate it, and
  update it through narrow seams, but Python must not become a second persistent source
  of truth.
- **The boundary is intentional.** Ansible does not call Python entry points to decide
  declared state, and Python does not orchestrate playbook execution.

---

## Secret Policy

Durable secrets live in [ansible/group_vars/all/vault.yml](ansible/group_vars/all/vault.yml), encrypted with Ansible Vault.

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

This rule keeps sudo credentials centralized, auditable, and detached from per-host
inventory files. Adding a new host requires a new `become_passwords` entry, not a new
vault schema or a new secret location.

[ansible/site.yml](ansible/site.yml) includes an always-on assertion that the current
host has a `become_passwords` entry. The policy is that provisioning should fail early
with a clear inventory or vault error, not later with a template failure.

---

## Python Entry Point Policy

### [scripts/bootstrap.py](scripts/bootstrap.py)

This script owns first-time vault setup. It may read [ansible/inventory/hosts.ini](ansible/inventory/hosts.ini),
prompt for credentials, and write the encrypted vault. It is the approved seam for
vault creation, vault migration, and durable secret updates.

### [scripts/check.py](scripts/check.py)

This script owns pre-flight validation. It may verify local prerequisites, decrypt the
vault, assert required secret completeness, and perform a minimal reachability check.
Its role is validation, not provisioning.

### [scripts/mount.py](scripts/mount.py)

This script owns interactive storage mounting. It may read inventory and vault data,
open a Fabric session, and make direct remote changes that are operational rather than
declarative. Its role is to perform one-shot storage work without turning Ansible into
an interactive shell.

---

## Makefile Policy

The Makefile remains the operator-facing entry point. The `_vault_check` target runs
[scripts/check.py](scripts/check.py) in `--vault-only` mode before provisioning or mount
targets:

```makefile
site minio baikal mount: _vault_check
```

The policy is that missing prerequisites should be rejected at the edge of the workflow,
before Ansible or Fabric reaches a deeper failure mode.

---

## App Dependency Policy

Application roles may depend on other application roles when the dependent service is
part of the same declared stack and is provisioned by this repository.

- **Dependencies must be explicit.** If one app requires another, that relationship
  belongs in role metadata rather than in operator memory or README-only sequencing.
- **The dependency remains declarative.** The consumer app declares what it needs;
  Ansible resolves ordering through role metadata and playbook tags.
- **Operator entry points should still exist.** A dependency may be provisioned on its
  own with a dedicated `make` target even when another app pulls it in transitively.

The current example is Baikal depending on PostgreSQL:

- [ansible/apps/baikal/meta/main.yml](ansible/apps/baikal/meta/main.yml) declares the
  dependency on the `postgres` app role.
- [ansible/site.yml](ansible/site.yml) tags both roles so `make postgres` works as an
  explicit operator action and `make baikal` still includes the database path.

This pattern is reserved for services that are part of the same repo-owned stack. It
should not be used to hide external infrastructure assumptions.

---

## Storage Policy

Application data paths must be explicitly declared, but the repository does not
mandate a specific storage medium.

- **Persistence is required.** App data should live at a declared path that survives
  container restarts and reprovisioning.
- **The medium is an operator choice.** A path may live on the root filesystem, an
  external drive, or any other storage the operator considers appropriate.
- **Mount workflows are optional helpers.** `make mount` exists to help prepare
  external storage, but app roles must not assume that external media is mandatory.

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

The governing rule is simple: Ansible declares and converges durable state; Python
assists through narrow operational seams. App-to-app dependencies may exist when they
remain explicit and repo-owned, but the system must still have a single declarative
source of truth.
