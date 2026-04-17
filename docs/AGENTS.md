# raspberry-hi — Agent Guide

## Purpose

Provision and manage a Raspberry Pi media server using Ansible and Python. The primary service is MinIO object storage, running in a rootless Podman container backed by an external USB drive. Baikal provides CalDAV/CardDAV for calendar and contact sync.

**Scope:** Infrastructure provisioning, storage configuration, and secret management.
**Out of scope:** Application-level MinIO configuration, rclone restore workflows (see `docs/.notes.md`).

**When responding:** Be concise. Prefer bullet lists over prose. Always reference exact file paths. Use `make <target>` syntax for commands.

---

## Domain vocabulary

| Term | Meaning |
| --- | --- |
| `HOST` | Alias for the target Pi (`rpi` or `rpi2`). Defaults to `rpi`. Pass as `HOST=rpi2 make site`. |
| `minio_data_path` | Filesystem path on the Pi where MinIO stores data. Must be on external storage. |
| `minio_require_external_mount` | Boolean role default. If `true`, `make minio` aborts unless `minio_data_path` is on a non-root mount. |
| `app_user_home` | Home directory for `ansible_user` on the target host. Defined in `group_vars/all/vars.yml`. Used by app roles for config and quadlet paths. |
| `service_adapter_backend` | Init system adapter used by app roles. Auto-detected from `ansible_facts['service_mgr']`; override in `host_vars` (`systemd`, `cron`, `manual`). |
| `mc_install_method` | How mc is installed in the minio app. Set in `mc_adapter/defaults/main.yml` (`binary`, `package`, `skip`). |
| `quadlet` | A systemd `.container` unit file that Podman uses to manage containers as services. |
| `vault` | An Ansible Vault-encrypted YAML file (`ansible/group_vars/all/vault.yml`) storing MinIO credentials. |
| `host_vars` | Per-host YAML files in `ansible/inventory/host_vars/`. Override role defaults for a specific Pi. |

---

## Architecture

```text
ansible/                  Playbooks and roles
  apps/
    minio/                MinIO object storage container (Linux only, tagged minio)
    baikal/               Baikal CalDAV/CardDAV server (Linux only, tagged baikal)
  roles/
    auto-updates/         Unattended security upgrades (apt/dnf/zypper/apk/pacman)
    podman/               Rootless container runtime (apt/dnf)
    storage/              Creates the minio_data_path directory
    service_adapter/      Port: service lifecycle management (systemd/cron/manual)
    mc_adapter/           Port: MinIO client installation (binary/package/skip)
  inventory/
    hosts.ini             Pi host aliases and IP addresses
    host_vars/rpi.yml     Per-host settings (ansible_user, minio_data_path, etc.)
  group_vars/all/
    vault.yml             Encrypted MinIO credentials

models/                   Pydantic models for typed data shared across scripts
  system/
    blockdevice.py        BlockDevice   — lsblk output
    mount.py              MountInfo     — findmnt output
  ansible/
    hostvars.py           HostVars      — ansible-inventory output
  services/
    vault.py              VaultSecrets  — MinIO credentials
  __init__.py             Re-exports all models — import sites use `from models import X`

scripts/
  utils/                  Shared helpers — imported by scripts, never called directly
    exec_utils.py         subprocess.run wrapper (resolves executables via PATH)
    ansible_utils.py      inventory_host_vars, make_connection
    storage_utils.py      get_block_devices, get_external_devices,
                          get_real_mounts, mount_covering, external_mounts
    storage_flows.py      interactive TUI flows for picking/mounting storage
  bootstrap.py            make bootstrap — first-time vault + credential setup
  check.py                make check    — validates prerequisites

ansible/
  library/                Custom Ansible modules, executed via delegate_to: localhost
    pick_device.py        make mount helper — interactive device picker
    minio_preflight.py    make minio helper — ensures minio_data_path is on
                          external storage; updates host_vars when needed

tests/
  test_models.py          Unit tests for Pydantic model validation
  test_storage_utils.py   Unit tests for mount/block device logic
  test_storage_flows.py   Unit tests for pure storage flow functions
  conftest.py             Shared pytest fixtures (findmnt_conn, lsblk_conn)
  support/
    builders.py           Helper constructors for test data (e.g. mnt())
    connections.py        FakeConnection — stubs fabric SSH without a real Pi
    data.py               Canned JSON fixtures (lsblk, findmnt output)
  e2e/
    test_connectivity.py  Live Pi tests (require HOST to be reachable)
    conftest.py           e2e-specific fixtures (live_conn)

typings/fabric/             Type stubs for the fabric SSH library

Makefile                  All user-facing commands — run `make help` for full list
```

---

## Key conventions

### Python imports

The Makefile exports `PYTHONPATH=$(CURDIR):$(CURDIR)/scripts` so local Python
entry points and custom Ansible modules can import project packages directly:

```python
from models import HostVars
from utils.ansible_utils import make_connection
```

Within `scripts/utils/`, use relative imports: `from .exec_utils import run_resolved`.

### ansible-inventory must run from ANSIBLE_DIR

`ansible-inventory` needs `ansible.cfg` in scope, which lives in `ANSIBLE_DIR`.
See `inventory_host_vars()`.

### Use Pydantic models, not dicts

Use models (`MountInfo`, `HostVars`, `BlockDevice`) wherever data has a known shape.
Add new models to `models/` and export from `models/__init__.py`.

### Multi-Pi support

- `rpi`  — 192.168.0.33 (default)
- `rpi2` — 192.168.0.35

All make targets accept `HOST=rpi2 make <target>`. Python scripts read it via `os.environ.get("HOST", "rpi")`.

### Platform constraints

| Constraint | Scope | Behaviour on violation |
| --- | --- | --- |
| Package manager | `auto-updates`, `podman` roles | Assert/skip with message (controlled by `*_fail_on_unsupported`) |
| Service backend | `service_adapter` role | Assert if `service_adapter_backend` not in supported list; auto-detected from facts |
| Linux (`/proc`, `/sys` paths) | `storage` role, storage scripts | Implicit — no guard, will fail at runtime |

**Service backends:** App roles (`minio`, `baikal`) are decoupled from init-system details via `service_adapter`. The backend is auto-detected from `ansible_facts['service_mgr']` but can be overridden in `host_vars`:

- `systemd` (default on Pi OS) — Podman quadlets, `loginctl enable-linger`, `systemctl --user`
- `cron` — deploys a `podman run` script, schedules it via `@reboot` cron; no restart-on-failure
- `manual` — deploys the run script only; operator wires it into their init system

For OpenRC/runit targets: set `service_adapter_backend: manual`, wire the deployed run script into your init system manually. Quadlets and linger are not used in this path.

### Ansible facts

Always use `ansible_facts['key']` instead of top-level `ansible_*` variables.
Example: `ansible_facts['pkg_mgr']`, not `ansible_pkg_mgr`.
The top-level form triggers deprecation warnings in ansible-core ≥ 2.20.

---

## Provisioning pipeline

```text
make site                         # provisions base stack (skips all app roles)
  └─ ansible-playbook site.yml --skip-tags apps
       ├─ role: auto-updates
       ├─ role: podman
       └─ role: storage           # creates minio_data_path directory

make minio                        # configure storage and provision MinIO
  └─ ansible-playbook site.yml --tags minio
    └─ role: minio             # runs minio_preflight, then deploys quadlet and bucket setup

make baikal                       # provision Baikal CalDAV/CardDAV
  └─ ansible-playbook site.yml --tags baikal
       └─ role: baikal            # creates data dirs, deploys quadlet, enables service

make mount                        # mount a drive without provisioning
  └─ ansible-playbook mount_storage.yml
    └─ pick_device             # interactive device picker when device= is omitted
```

App roles (under `ansible/apps/`) are tagged with both `apps` and their own name (e.g. `[apps, minio]`). This means `make site` skips all of them, while individual `make <app>` targets still work. Future apps follow the same pattern.

---

## Secrets

Stored in `ansible/group_vars/all/vault.yml` (Ansible Vault encrypted).
Password lives in `ansible/.vault-password` (gitignored, mode 600).
Edit with `make vault-edit`. Bootstrap with `make bootstrap`.
**Never commit `.vault-password` or unencrypted secrets.**

---

## What to avoid

| Don't | Why |
| --- | --- |
| Run `ansible-playbook` from `ANSIBLE_DIR` | Relative SSH key paths in `host_vars` resolve against CWD — they break from `ansible/` |
| Set `minio_require_external_mount: false` in role defaults | This is a per-host opt-out; it belongs in `host_vars` so it's explicit and auditable |
| Use `ansible_*` top-level facts | Deprecated since ansible-core 2.20; use `ansible_facts['key']` instead |
| Remove `RequiresMountsFor` from the quadlet | Without it, MinIO starts before the external drive is mounted on slow boots |

---

## Success rubric

When asked to evaluate this project, score it 1–5 across the following dimensions and provide a brief justification for each:

| Dimension | What to assess |
| --- | --- |
| **Portability** | Does the project handle multiple OS/architectures cleanly? Are there hard dependencies that limit where it can run? |
| **Simplicity** | Is the project structure flat and navigable? Are responsibilities well-separated? Is complexity justified? |
| **Maintainability** | Is the code modular enough to change one part without breaking others? Are dependencies pinned and upgradeable? Do tests catch regressions meaningfully? |
| **Usability** | Is it easy for a new user to get started? Are commands discoverable? Is error handling helpful? |
| **Best practice** | Are secrets, types, linting, and testing handled correctly? Does it follow conventions for its toolchain? |

Respond with a Markdown table. For each dimension include a score (1–5) and a one-sentence note citing a specific file or pattern as evidence.
