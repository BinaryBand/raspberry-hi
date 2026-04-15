# CLAUDE.md — raspberry-hi

Ansible + Python tools for provisioning and managing a Raspberry Pi media server.
MinIO object storage is the primary service, backed by an external USB drive.
Data is restored from pCloud via rclone (see `config/.help.md` for restore commands).

---

## Architecture

```text
ansible/                  Playbooks and roles
  roles/
    auto-updates/         Unattended upgrades
    homebrew/             Linuxbrew (used for CLI tools)
    minio/                MinIO container + mc bucket setup
    podman/               Podman (rootless container runtime)
    storage/              Creates minio_data_path directory
  inventory/
    hosts.ini             Pi host aliases
    host_vars/rpi.yml     Per-host overrides (including minio_data_path)
  group_vars/all/
    vault.yml             Encrypted MinIO credentials

models/                   Pydantic models shared across scripts
  blockdevice.py          BlockDevice (lsblk output)
  hostvars.py             HostVars (ansible-inventory output)
  minio.py                MinioConfig (role defaults + host_var overrides)
  mount.py                MountInfo (findmnt output)
  vault.py                VaultSecrets (minio credentials)

scripts/
  utils/                  Shared library — never called directly by make
    exec_utils.py         subprocess.run wrapper (resolves executables)
    ansible_utils.py      inventory_host_vars, make_connection, run_playbook,
                          read/write host_vars, read_role_defaults
    storage_utils.py      get_block_devices, get_external_devices,
                          get_real_mounts, mount_covering, external_mounts
  bootstrap.py            make bootstrap — vault password + credential setup
  check.py                make check — prereq validation
  pick_storage.py         make mount — interactive device picker + mounter
  setup_minio_storage.py  make site pre-flight — ensures minio_data_path is
                          on external storage, guides user if not

stubs/fabric/             Type stubs for the fabric SSH library

Makefile                  All user-facing commands (bootstrap, check, site, mount)
```

---

## Key conventions

### Python imports

All entry-point scripts add both ROOT and SCRIPTS_DIR to `sys.path`:

```python
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))      # for models
sys.path.insert(0, str(SCRIPTS_DIR))  # for utils package
```

Then import as `from utils.ansible_utils import ...` and `from models import ...`.

Within `scripts/utils/`, modules use relative imports: `from .exec_utils import run_resolved`.

### ansible-playbook must run from ROOT

Relative SSH key paths in host_vars (e.g. `config/.ed25519`) resolve against CWD.
Always pass `cwd=str(ROOT)` and `env={**os.environ, "ANSIBLE_CONFIG": str(ANSIBLE_DIR / "ansible.cfg")}` when calling ansible-playbook. See `run_playbook()` in `utils/ansible_utils.py`.

### ansible-inventory must run from ANSIBLE_DIR

Conversely, `ansible-inventory` needs to run from `ANSIBLE_DIR` so it picks up `ansible.cfg` and its relative inventory path. See `inventory_host_vars()`.

### Models over dicts

Use Pydantic models (`MountInfo`, `MinioConfig`, `BlockDevice`, etc.) instead of plain dicts wherever data has a known shape. Add new models to `models/` and export from `models/__init__.py`.

### HOST is hardcoded as "rpi"

`pick_storage.py` and `setup_minio_storage.py` hardcode `HOST = "rpi"`. The Makefile supports `HOST=rpi2 make site` for ansible-playbook but the Python scripts don't yet honour it.

---

## Provisioning pipeline

```
make site
  └─ setup_minio_storage.py     # pre-flight: verify minio_data_path is on external mount
       ├─ if not: guide user →  # pick device → mount → update host_vars/rpi.yml
       └─ exit 0
  └─ ansible-playbook site.yml
       ├─ role: auto-updates
       ├─ role: homebrew
       ├─ role: podman
       ├─ role: storage          # creates minio_data_path directory
       └─ role: minio            # deploys quadlet, enables service, sets up bucket
```

`make mount` (pick_storage.py) can be run independently to mount a drive without provisioning.

---

## MinIO specifics

- Data path: `minio_data_path` in `ansible/inventory/host_vars/rpi.yml`
  (defaults to `/srv/minio/data` in role, expected to be overridden to external mount)
- External mount check: `minio_require_external_mount: true` (role default)
  Override to `false` in host_vars to allow root-filesystem storage
- fstab entry uses `nofail` — Pi boots even if drive is absent
- Quadlet uses `RequiresMountsFor={{ minio_data_path }}` — MinIO won't start until mount is up
- MinIO web console runs on port 9001 (credentials from vault)
- rclone restores from `pcloud:/Backups/Minio/media` — see `config/.help.md`

---

## Secrets

Stored in `ansible/group_vars/all/vault.yml` (ansible-vault encrypted).
Password lives in `ansible/.vault-password` (gitignored, mode 600).
Edit with `make vault-edit`. Bootstrap with `make bootstrap`.
Never commit `.vault-password` or unencrypted vault contents.

---

## What to avoid

- Don't run ansible-playbook from ANSIBLE_DIR — SSH key resolution breaks
- Don't add `minio_require_external_mount: false` to defaults — it belongs in host_vars as an explicit opt-out
- Don't use `ansible_*` prefixed facts in tasks — use `ansible_facts['key']` instead (deprecation warning)
- Don't skip `RequiresMountsFor` in the quadlet — without it MinIO starts before the drive is ready on slow boots
