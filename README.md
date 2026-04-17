# raspberry-hi

Ansible + Python tools for managing a Raspberry Pi.

## Requirements

- Python 3.12+
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
ansible_user: user
ansible_port: 22
ansible_ssh_private_key_file: config/.your-key
```

### 2. Set up secrets

Secrets (MinIO credentials) are stored in an Ansible Vault encrypted file that travels
with the repo. Run the interactive bootstrap script to set everything up:

```bash
make bootstrap
```

This will prompt you for a vault password (saved locally, never committed) and your MinIO credentials plus any missing per-host sudo passwords, then write the
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

To mount external storage on the Pi before provisioning MinIO, run `make mount` first. That command is a standalone Python/Fabric script — it reads connection details from the Ansible inventory and the vault, then interactively picks and mounts a device over SSH.

---

## Commands

### Development

| Command | What it does |
| --- | --- |
| `make lint` | Run ruff over `scripts/`, `models/`, and `tests/` |
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
| `make minio` | Provision MinIO (purely declarative — reads credentials from vault, data path from `host_vars`) |
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
ansible_user: user
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
