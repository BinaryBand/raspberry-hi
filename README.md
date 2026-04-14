# raspberry-hi

Ansible + Python tools for managing a Raspberry Pi.

## Requirements

- Ansible (`brew install ansible`)
- Poetry (`pipx install poetry`)
- SSH key already on the Pi

## Project Root

All commands below should be run from the project root (`./`).

## First-time setup

### 1. Configure your Pi

Edit `ansible/inventory/hosts.ini` and set your Pi's IP and username:

```ini
[raspberry_pi]
rpi ansible_host=192.168.0.33

[raspberry_pi:vars]
ansible_user=youruser
```

To manage multiple Pis, add more lines under `[raspberry_pi]`.

### 2. Set up secrets

Secrets (MinIO credentials) are stored in an Ansible Vault encrypted file that travels
with the repo. Run the interactive bootstrap script to set everything up:

```bash
make bootstrap
```

This will prompt you for a vault password (saved locally, never committed) and your
MinIO credentials, then write the encrypted vault file.

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

**MinIO external storage:** `make site` checks whether `minio_data_path` is on an
external mount before provisioning. If not, it walks you through your options:

- **Mount a new drive** — lists external block devices on the Pi, mounts the one you
  pick, and writes the path to `host_vars` automatically.
- **Use an already-mounted drive** — lists current non-root mounts and lets you pick one.
- **Use the root filesystem** — sets `minio_require_external_mount: false` in `host_vars`
  and continues. Not recommended; risks wearing the SD card.

You can also run `make mount` at any time to (re-)mount external storage independently.

---

## Commands

| Command | What it does |
| --- | --- |
| `make check` | Validate all prerequisites before provisioning |
| `make ping` | Check Pi is reachable |
| `make bootstrap` | First-time setup: create vault password and encrypt secrets |
| `make vault-edit` | Edit existing encrypted secrets |
| `make site` | Full provision: base → Homebrew → Podman → storage → MinIO |
| `make mount` | Interactively mount external storage |
| `make backup` | Backup Raspberry Pi Imager customizations |
| `make backup-dryrun` | Preview what would be backed up |
| `make reset` | Reset to Raspberry OS Lite default state |
| `make reset-dryrun` | Preview what would be removed |
| `make restore` | Restore configurations from backup |
| `make restore-dryrun` | Preview what would be restored |

### Tags — run a subset of roles

```bash
cd ansible && ansible-playbook site.yml --tags homebrew
cd ansible && ansible-playbook site.yml --tags minio
cd ansible && ansible-playbook site.yml --tags "podman,storage"
```

### Multiple Pis

Add hosts to `ansible/inventory/hosts.ini`, then target a specific one:

```bash
HOST=rpi2 make site
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
ansible raspberry_pi -m ping
ansible-playbook backup.yml
ansible-playbook reset.yml
ansible-playbook restore.yml
```

## Backup and Reset Operations

### Backup Customizations
Before making major changes, backup your Raspberry Pi's Imager customizations:

```bash
make backup
```

This backs up:
- SSH configurations (server and client)
- User accounts and keys
- Wi-Fi credentials
- Network settings (hostname, hosts file)
- Localization settings (locale, timezone)

### Reset to Factory Defaults
Reset your Raspberry Pi to a clean Raspberry OS Lite state:

```bash
make reset
```

This removes:
- All user-installed packages
- Podman containers and images
- MinIO data and configuration
- Homebrew installation
- Custom systemd services
- User cron jobs
- Custom mount points
- Non-system configuration files

### Restore from Backup
After a reset, restore your customizations:

```bash
make restore
```

This restores the configurations you backed up, getting your Pi back to its customized state.

### Dry Run Mode
Test operations without making changes:

```bash
make backup-dryrun    # See what would be backed up
make reset-dryrun     # See what would be removed
make restore-dryrun   # See what would be restored
```
