# raspberry-hi

Ansible + Python tools for managing a Raspberry Pi.

## Requirements

- Ansible (`brew install ansible`)
- Poetry (`brew install poetry`)
- SSH key already on the Pi

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

---

## Commands

| Command | What it does |
| --- | --- |
| `make check` | Validate all prerequisites before provisioning |
| `make ping` | Check Pi is reachable |
| `make bootstrap` | First-time setup: create vault password and encrypt secrets |
| `make vault-edit` | Edit existing encrypted secrets |
| `make site` | Full provision: base → Homebrew → Podman → Rclone → MinIO |
| `make mount` | Interactively mount external storage |
| `make rclone [args]` | Forward rclone commands to the Pi over SSH |

### Tags — run a subset of roles

```bash
cd ansible && ansible-playbook site.yml --tags homebrew
cd ansible && ansible-playbook site.yml --tags minio
cd ansible && ansible-playbook site.yml --tags "podman,rclone"
```

### Multiple Pis

Add hosts to `ansible/inventory/hosts.ini`, then target a specific one for rclone:

```bash
HOST=rpi2 make rclone config
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

Playbooks live in `ansible/` and must be run from there (so `ansible.cfg` is picked up):

```bash
cd ansible
ansible-playbook site.yml
ansible raspberry_pi -m ping
```
