# linux-hi

Ansible + Python tools for provisioning any Linux system over SSH.

Architecture intent lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Enforceable repository architecture rules live in [rules/](rules/).

## Requirements

- Python 3.12+
- Poetry (`pipx install poetry`)
- Node.js 18+ / npx (for `make cpd` — ships with Node.js)
- SSH key already on the target host

All other dependencies — Ansible, Fabric, Pydantic, etc. — are managed by Poetry:

```bash
poetry install
```

## Project Root

All commands below should be run from the project root (`./`).

## First-time setup

### 1. Configure your host

Add your host to `ansible/inventory/hosts.yml`:

```yaml
all:
  children:
    devices:
      hosts:
        rpi:
```

Then create `ansible/inventory/host_vars/rpi.yml` with its connection details:

```yaml
# ansible_host accepts a hostname, an mDNS name (host.local), or a raw IP (192.168.0.x).
# mDNS survives DHCP address changes without editing this file.
ansible_host: rpi.local
ansible_user: user
ansible_port: 22
ansible_ssh_private_key_file: config/.your-key
ansible_become_password: "{{ (become_passwords | default({})).get(inventory_hostname, '') }}"

# Paths on the host where app data is stored (used by minio/postgres roles).
minio_data_path: /mnt/external/minio
postgres_data_path: /mnt/external/postgres
```

### 2. Set up secrets

Secrets (MinIO credentials) are stored in an Ansible Vault encrypted file that travels with the repo. Run the interactive bootstrap script to set everything up:

```bash
make bootstrap
```

This will prompt you for a vault password (saved locally, never committed) and your MinIO credentials plus any missing per-host sudo passwords, then write the encrypted vault file.

To update secrets later: `make vault-edit`

### 3. Validate prerequisites

```bash
make check
```

Verifies that the vault password file exists and the target host is reachable.

### 4. Provision

```bash
make site
```

Installs and configures everything on the host. Subsequent runs need no extra steps — the vault password file handles decryption automatically.

If you want to prepare external storage on the host, run `make mount`. That command is a standalone Python/Fabric script — it reads connection details from the Ansible inventory and the vault, then interactively picks and mounts a device over SSH. MinIO only requires a persistent `minio_data_path`; it does not require external media.

---

## Commands

### Development

| Command | What it does |
| --- | --- |
| `make lint` | Run the full static quality gate: Ruff, format check, ty, Semgrep, cpd, and ansible-lint |
| `make ruff` | Run Ruff lint checks over `linux_hi/`, `models/`, and `tests/` |
| `make format-check` | Run Ruff formatting checks over `linux_hi/`, `models/`, and `tests/` |
| `make ty` | Run ty type checks over the repository |
| `make semgrep` | Run Semgrep audits for current architectural/process constraints |
| `make cpd` | Fail on any copy-paste duplication (jscpd, threshold 0%) |
| `make checkmake` | Lint Makefile style and quality with mbake |
| `make ansible-lint` | Run ansible-lint over `ansible/` using `.ansible-lint.yml` |
| `make test` | Run unit and stub tests (no infrastructure needed) |
| `make test-e2e` | Run live host tests (requires a reachable host) |

### Provisioning

| Command | What it does |
| --- | --- |
| `make check` | Validate all prerequisites before provisioning |
| `make ping` | Check host is reachable |
| `make bootstrap` | First-time setup: create vault password and encrypt secrets |
| `make vault-edit` | Edit existing encrypted secrets |
| `make site` | Full provision: base → Podman → storage |
| `make minio` | Provision MinIO (purely declarative — reads credentials from vault, data path from `host_vars`) |
| `make postgres` | Provision PostgreSQL for Baikal (reads credentials from vault and data path from `host_vars`) |
| `make baikal` | Provision Baikal (runs PostgreSQL preflight first because Baikal depends on it) |
| `make mount` | Interactively mount external storage |

### Operations

| Command | What it does |
| --- | --- |
| `make status` | Show MinIO service status on the host |
| `make logs` | Tail the last 50 lines of MinIO logs from the host |
| `make ssh` | Open a shell on the host |

### Tags — run a subset of roles

```bash
cd ansible && ansible-playbook site.yml --tags minio
cd ansible && ansible-playbook site.yml --tags "podman,storage"
```

### Multiple hosts

Add each host to `ansible/inventory/hosts.yml` and create a matching `host_vars/` file:

```yaml
# hosts.yml
all:
  children:
    devices:
      hosts:
        rpi:
        rpi2:
```

```yaml
# host_vars/rpi2.yml
ansible_host: rpi2.local
ansible_user: user
ansible_port: 22
ansible_ssh_private_key_file: config/.your-key
```

Then target a specific host with `HOST`:

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

The `.PHONY` line tells Make these are commands, not filenames — without it, Make would skip the target if a file with that name happened to exist.

---

## Ad-hoc Ansible

Playbooks live in `ansible/`. If running Ansible commands directly, first `cd ansible` so `ansible.cfg` is picked up:

```bash
cd ansible
ansible-playbook site.yml
ansible [device] -m ping
```
