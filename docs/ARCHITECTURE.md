# Architecture: Declarative Ansible + Standalone Python Scripts

## Goal

Keep Ansible and Python cleanly separated with no overlap:

- **Ansible** is the single provisioning driver. It is purely declarative — it reads
  state from `host_vars/` and the vault, and converges the Pi toward that state. It
  never calls Python scripts, and Python scripts never call Ansible.
- **Python scripts** handle interactive, one-shot operations (vault bootstrap, storage
  mounting) that are unsuitable for a declarative model. They connect directly to the
  Pi via Fabric and read connection details from the Ansible inventory/vault — they
  do not invoke Ansible at all.

---

## Secrets — Ansible vault

Secrets live in `ansible/group_vars/all/vault.yml`, encrypted with Ansible Vault.

The vault model (`models/services/vault.py`) holds:

- Static app credentials (`minio_root_user`, `minio_root_password`)
- A `become_passwords` dict keyed by inventory hostname:

  ```yaml
  become_passwords:
    rpi: "..."
    rpi2: "..."
  ```

Each `host_vars/<hostname>.yml` references the dict dynamically:

```yaml
ansible_become_password: "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"
```

Adding a new host only requires a new entry in `become_passwords` — no model changes,
no new vault keys, no template changes.

`ansible/site.yml` has an `always`-tagged pre-task that asserts the current host has
an entry in `become_passwords`, so provisioning fails fast with a clear message rather
than a cryptic template error.

---

## Python entry points

### `scripts/bootstrap.py`

First-time setup. Reads `hosts.ini` directly with `configparser` (no Ansible required),
prompts for app credentials and per-host sudo passwords, and writes the encrypted vault
file. Also handles migration of any legacy per-host vault keys (`rpi_become_password`,
etc.) into the `become_passwords` dict.

### `scripts/check.py`

Pre-flight validation. Verifies the vault password file exists, decrypts the vault,
checks all required secrets and `become_passwords` entries are populated, and pings
the Pi. Supports `--vault-only` mode (skips Python/Ansible/Node/ping checks) for use
as a fast Makefile prerequisite.

### `scripts/mount.py`

Interactive storage mounting. Reads connection details from `inventory_host_vars()`,
reads the become password from the vault, opens a Fabric connection, and presents a
TUI to pick and mount a block device. Writes an `fstab` entry for persistence.
No Ansible involvement — a pure Python/Fabric/SSH operation.

---

## Makefile integration

The `_vault_check` target runs `check.py --vault-only` and is a prerequisite for all
provisioning and mount targets:

```makefile
site minio baikal mount: _vault_check
```

This ensures secrets are present before Ansible or Fabric tries to use them, producing
a helpful error message at the Make level rather than deep inside a playbook or script.

---

## Resulting shape

```text
ansible/
  apps/            ← declarative roles (minio, baikal, …)
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

Ansible is the provisioning driver. Python is the interactive toolbox. Neither calls
the other.
