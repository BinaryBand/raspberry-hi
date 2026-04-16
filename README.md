# raspberry-hi

Ansible + Python tools for managing a Raspberry Pi.

## Requirements

- Python 3.12+ (`pyenv install 3.12` or your distro's package manager)
- Poetry (`pipx install poetry`)
- Node.js 18+ / npx (for `make cpd` — ships with Node.js)
- SSH key already on the Pi

All other dependencies — Ansible, Fabric, Pydantic, etc. — are managed by Poetry:

```bash
poetry install
```

## Project Root

All commands below should be run from the project root (`./`).

## First-time setup

### 1. Configure your Pi

Add your Pi to `ansible/inventory/hosts.ini`:

```ini
[devices]
rpi
```

Then create `ansible/inventory/host_vars/rpi.yml` with its connection details:

```yaml
# Use an mDNS name (rpi.local) or a raw IP (192.168.0.x).
# mDNS survives DHCP changes without editing this file.
ansible_host: rpi.local
ansible_user: youruser
ansible_port: 22
ansible_ssh_private_key_file: config/.your-key
```

### 2. Set up secrets

Secrets (MinIO credentials) are stored in an Ansible Vault encrypted file that travels
with the repo. Run the interactive bootstrap script to set everything up:

```bash
make bootstrap
```

This will prompt you for a vault password (saved locally, never committed) and your
MinIO credentials plus any missing per-host sudo passwords, then write the
encrypted vault file.

To update secrets later: `make vault-edit`

### 3. Validate prerequisites

```bash
make check
```

Verifies that the vault password file exists and the Pi is reachable.

### 4. Provision

```bash
make site
```

Installs and configures everything on the Pi. Subsequent runs need no extra steps —
the vault password file handles decryption automatically.

**MinIO external storage:** `make minio` checks whether `minio_data_path` is on an
external mount before provisioning the MinIO role. If not, it prompts you to pick an
existing external mount and a subdirectory for the data path.

If no external mount exists yet, run `make mount` first. That command now launches the
Ansible playbook directly and uses a custom `pick_device` module on the control node to
drive the interactive selection.

You can also run `make mount` at any time to (re-)mount external storage independently.

---

## Commands

### Development

| Command | What it does |
| --- | --- |
| `make lint` | Run ruff over `ansible/library`, `scripts/`, `models/`, and `tests/` |
| `make cpd` | Check for copy-paste duplication (jscpd, threshold 3%) |
| `make test` | Run unit and stub tests (no infrastructure needed) |
| `make test-roles` | Run Ansible role tests in Docker (requires Docker) |
| `make test-e2e` | Run live Pi tests (requires a reachable Pi) |

### Provisioning

| Command | What it does |
| --- | --- |
| `make check` | Validate all prerequisites before provisioning |
| `make ping` | Check Pi is reachable |
| `make bootstrap` | First-time setup: create vault password and encrypt secrets |
| `make vault-edit` | Edit existing encrypted secrets |
| `make site` | Full provision: base → Podman → storage |
| `make minio` | Validate MinIO storage placement, update `host_vars` if needed, then provision MinIO |
| `make mount` | Interactively mount external storage |

### Operations

| Command | What it does |
| --- | --- |
| `make status` | Show MinIO service status on the Pi |
| `make logs` | Tail the last 50 lines of MinIO logs from the Pi |
| `make ssh` | Open a shell on the Pi |

### Tags — run a subset of roles

```bash
cd ansible && ansible-playbook site.yml --tags minio
cd ansible && ansible-playbook site.yml --tags "podman,storage"
```

### Multiple Pis

Add each host to `ansible/inventory/hosts.ini` and create a matching `host_vars/` file:

```ini
# hosts.ini
[devices]
rpi
rpi2
```

```yaml
# host_vars/rpi2.yml
ansible_host: rpi2.local
ansible_user: youruser
ansible_port: 22
ansible_ssh_private_key_file: config/.your-key
```

Then target a specific Pi with `HOST`:

```bash
HOST=rpi2 make site
HOST=rpi2 make status
```

---

## Makefile primer

A Makefile defines named shortcuts (`targets`) you run with `make <target>` from the project root.

```makefile
target:          # name of the command
  shell command  # must be indented with a TAB (not spaces)
  shell command  # multiple lines run in sequence
```

The `.PHONY` line tells Make these are commands, not filenames — without it, Make would skip
the target if a file with that name happened to exist.

---

## Ad-hoc Ansible

Playbooks live in `ansible/`. If running Ansible commands directly, first `cd ansible` so `ansible.cfg` is picked up:

```bash
cd ansible
ansible-playbook site.yml
ansible [device] -m ping
```
