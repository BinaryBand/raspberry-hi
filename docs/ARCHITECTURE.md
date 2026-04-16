# Architecture: Python-as-Toolbox for Ansible

## Goal

Invert the current driver relationship. Today Python scripts are the primary entry points — they call Ansible as a subprocess. The target shape makes Ansible the single driver; Python lives in `ansible/library/` as custom modules that Ansible calls when it needs interactive TUI logic.

This also fixes the immediate `sudo: a password is required` failures on both `rpi` and `debian` by storing per-host become passwords in the vault.

---

## Phase 1 — Fix become passwords

Both hosts need their sudo passwords in the vault so Ansible can become root
without prompting on the command line.

### `models/services/vault.py`

Add two optional fields:

```python
rpi_become_password: Optional[str] = None
debian_become_password: Optional[str] = None
```

### `scripts/bootstrap.py` — `SECRETS` list

Add after the existing minio entries:

```python
{"key": "rpi_become_password",    "label": "rpi sudo password",    "hidden": True},
{"key": "debian_become_password", "label": "Debian sudo password", "hidden": True},
```

### `ansible/inventory/host_vars/rpi.yml`

```yaml
ansible_become_password: "{{ rpi_become_password }}"
```

### `ansible/inventory/host_vars/debian.yml`

```yaml
ansible_become_password: "{{ debian_become_password }}"
```

Run `make bootstrap` after — it prompts only for the two new missing secrets.

---

## Phase 2 — Python-as-toolbox architecture

### Key decision: keep `scripts/utils/` in place

`scripts/utils/storage_utils.py` and `storage_flows.py` stay where they are. The Makefile already exports `PYTHONPATH=$(CURDIR):$(CURDIR)/scripts`, and modules running via `delegate_to: localhost` inherit the calling process environment. No `ansible/module_utils/` directory, no shims, no test import changes needed.

### New files

```text
ansible/
  library/
    pick_device.py        ← NEW: replaces scripts/pick_storage.py
    minio_preflight.py    ← NEW: replaces scripts/setup_minio_storage.py
```

Ansible auto-discovers `library/` adjacent to the playbook. Add
`library = ./library` to `ansible/ansible.cfg` to make it explicit.

---

### `ansible/library/pick_device.py`

Custom Ansible module. Called with `delegate_to: localhost` so `questionary`
runs on the control node. Accepts SSH connection params as module arguments
(passed from hostvars by the playbook), opens its own Fabric connection to
run `lsblk`, presents the TUI, and returns `{device, label}`.

```
argument_spec:
  host:       str, required
  user:       str, required
  key:        str, no_log (path to SSH private key)
  port:       int, default 22
  label_hint: str, optional

returns: {device: "/dev/sda1", label: "minio_data", changed: false}
```

Imports `flow_mount_new_device` from `utils.storage_flows` — same function
that `pick_storage.py` used, no logic duplication.

---

### `ansible/library/minio_preflight.py`

Custom Ansible module. Called from the minio role with `delegate_to: localhost`
when `minio_require_external_mount` is true.

```
argument_spec:
  host:              str, required
  user:              str, required
  key:               str, no_log
  port:              int, default 22
  current_data_path: str, required  (value of minio_data_path)
  host_vars_file:    str, required  (absolute path to write updated path back)

returns: {data_path: "/mnt/minio/data", changed: bool}
```

Logic:

1. SSH in, call `get_real_mounts()` + `mount_covering()` to check if
   `current_data_path` is already on an external mount → if yes, return
   `{changed: false}` immediately (idempotent).
2. If not on external mount and no external mounts exist → `fail_json` with
   "run `make mount` first".
3. Otherwise: `questionary.select` from available external mounts, then
   `questionary.text` for subdirectory.
4. Write the new path back to `host_vars_file` (passed by Ansible as
   `{{ inventory_dir }}/host_vars/{{ inventory_hostname }}.yml`).
5. Return `{changed: true, data_path: new_path}`.

Inlines its own `update_host_vars()` (10 lines of YAML read/write) — no
shared utility needed.

---

### `ansible/mount_storage.yml` — updated

Add a conditional pre-task using `pick_device`. The `device` and `label`
extra vars still work for scripted/non-interactive use; the module only
fires when they are absent.

```yaml
- name: Pick device to mount
  pick_device:
    host: "{{ ansible_host }}"
    user: "{{ ansible_user }}"
    key:  "{{ ansible_ssh_private_key_file | default(omit) }}"
    port: "{{ ansible_port | default(22) }}"
  delegate_to: localhost
  register: _picked
  when: device is not defined

- name: Set device and label from selection
  ansible.builtin.set_fact:
    device: "{{ _picked.device }}"
    label:  "{{ _picked.label }}"
  when: device is not defined
```

Remove the comment at the top about passing `-e device=... label=...` —
that usage becomes optional rather than required.

---

### `ansible/apps/minio/tasks/main.yml` — updated

Add as the first task block (before config dirs):

```yaml
- name: Ensure MinIO data path is on external storage
  minio_preflight:
    host:              "{{ ansible_host }}"
    user:              "{{ ansible_user }}"
    key:               "{{ ansible_ssh_private_key_file | default(omit) }}"
    port:              "{{ ansible_port | default(22) }}"
    current_data_path: "{{ minio_data_path }}"
    host_vars_file:    "{{ inventory_dir }}/host_vars/{{ inventory_hostname }}.yml"
  delegate_to: localhost
  register: _preflight
  when: minio_require_external_mount | bool

- name: Apply preflight data path
  ansible.builtin.set_fact:
    minio_data_path: "{{ _preflight.data_path }}"
  when:
    - minio_require_external_mount | bool
    - _preflight is not skipped
```

---

### Makefile — simplified

```makefile
mount:
    ANSIBLE_CONFIG=$(ANSIBLE_CFG) ansible-playbook ansible/mount_storage.yml \
      -i $(INV) --vault-password-file $(VAULT_PASS) --limit $(HOST)

minio:
    $(ANSIBLE_PLAY) --tags minio
```

`make mount` no longer shells into Python first. `make minio` is a single
Ansible call — the preflight runs inline as a task.

---

### `ansible/ansible.cfg` — add library path

```ini
library = ./library
```

---

## Phase 3 — Cleanup

### Files to delete

| File | Reason |
| ------ | -------- |
| `scripts/pick_storage.py` | Replaced by `ansible/library/pick_device.py` |
| `scripts/setup_minio_storage.py` | Replaced by `ansible/library/minio_preflight.py` |
| `models/services/minio.py` | Only used by `setup_minio_storage.py` |
| `tests/test_ansible_utils.py` | Tests functions that are deleted |

### `scripts/utils/ansible_utils.py` — stripped

Remove: `run_playbook`, `read_role_defaults`, `read_host_vars`,
`write_host_vars`, `update_host_vars`.

Keep: `ROOT`, `ANSIBLE_DIR`, `inventory_host_vars`, `make_connection`.
(`inventory_host_vars` and `make_connection` are still used by
`tests/e2e/conftest.py`.)

### `models/__init__.py` — remove MinioConfig

```python
from .ansible.hostvars import HostVars
from .services.vault import VaultSecrets
from .system.blockdevice import BlockDevice
from .system.mount import MountInfo

__all__ = ["BlockDevice", "HostVars", "MountInfo", "VaultSecrets"]
```

### `tests/test_models.py` — remove MinioConfig test class

---

## Resulting shape

```
ansible/
  library/
    pick_device.py        ← Python, called by Ansible
    minio_preflight.py    ← Python, called by Ansible
  apps/ roles/ ...        ← unchanged

scripts/
  bootstrap.py            ← kept (vault bootstrap is pre-Ansible)
  check.py                ← kept (validates Ansible can run)
  utils/
    ansible_utils.py      ← stripped (ROOT, ANSIBLE_DIR, inventory helpers)
    exec_utils.py         ← unchanged
    storage_utils.py      ← unchanged, imported by library modules
    storage_flows.py      ← unchanged, imported by library modules

models/
  services/vault.py       ← kept + expanded
  ansible/hostvars.py     ← kept (used by e2e tests)
  system/                 ← unchanged
  # services/minio.py     ← deleted
```

Ansible is now the single entry point. Python provides focused toolbox
modules — interactive device selection and storage preflight — that Ansible
calls as tasks, with no Python-calls-Ansible inversion.
