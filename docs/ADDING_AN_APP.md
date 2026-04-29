# Adding a New App

This guide walks through every step needed to add a new application to the repo from scratch — registry entry, Ansible role, and tests.

The worked example is a hypothetical `jellyfin` app: a containerized media server with no dependencies.

---

## Overview

Adding an app touches four things:

1. **`ansible/registry.yml`** — the single declaration that drives preflight, `make` targets, and policy checks.
2. **`ansible/apps/<app>/`** — the Ansible role (tasks, defaults, templates, etc.) and `playbook.yml`.
3. **`make generate-apps`** — regenerates `ansible/group_vars/all/vars.yml` from the registry.
4. **`tests/test_ansible_apps.py`** — update the expected app list and add any contract assertions.

---

## Step 1 — Declare the app in `ansible/registry.yml`

Every registered field drives real behaviour:

```yaml
apps:
  jellyfin:
    service_type: containerized
    service_name: jellyfin
    image: docker.io/jellyfin/jellyfin:10.10.7
    port: 8096
    dependencies: []                # list app names here if ordering is required
    preflight_vars:
      jellyfin_data_path:
        hint: directory for Jellyfin library and config data
        default: /home/linux-hi/jellyfin
    vault_secrets:
      - key: jellyfin_api_key
        label: Jellyfin API key
        hidden: true
```

### Field reference

| Field | Type | Effect |
| --- | --- | --- |
| `service_type` | `containerized` | Required; all apps are containerized. |
| `service_name` | string | The systemd service and container name (e.g. `jellyfin`). |
| `image` | string | The fully-qualified container image with a pinned tag. `:latest` is rejected by Semgrep. |
| `port` | int | Primary published port. Emitted into `group_vars/all/vars.yml`. |
| `dependencies` | list | Apps that must be preflighted and provisioned before this one. |
| `preflight_vars` | map | Variables written to `host_vars/<host>.yml` before provisioning. Null defaults (`~`) trigger a prompt; non-null defaults are offered as suggestions. Use `type: rclone_remote` to get an interactive remote selector. |
| `vault_secrets` | list | Secrets written to the vault before provisioning. `hidden: true` uses password-style input. `generate: true` auto-generates a random hex value when left blank. |

**App with a dependency** (e.g. Baikal depending on PostgreSQL):

```yaml
dependencies:
  - postgres
```

Preflight will recurse into `postgres` first. The playbook must open with `import_playbook: ../postgres/playbook.yml` so Ansible converges PostgreSQL before Baikal.

---

## Step 2 — Create the Ansible role

```text
ansible/apps/jellyfin/
  playbook.yml               # play entry point (write by hand — see pattern below)
  defaults/main.yml          # role defaults; null out required vars here
  tasks/main.yml             # provisioning tasks
  handlers/main.yml          # optional: restart handler
  templates/                 # optional: .env.j2, config templates, etc.
```

### `playbook.yml`

Write this by hand following the pattern used by every existing app:

```yaml
---
- name: Provision jellyfin
  hosts: devices
  gather_facts: true

  pre_tasks:
    - name: Load common pre-tasks
      ansible.builtin.import_tasks: ../../tasks/pre_tasks.yml

  roles:
    - role: jellyfin
```

If the app has dependencies, open with the appropriate `import_playbook` line (see `ansible/apps/baikal/playbook.yml` for the pattern).

### `defaults/main.yml`

Null out any variable that the operator must supply (preflight will prompt for it). Do not put `service_name`, `image`, or `port` here — those come from the registry via `group_vars/all/vars.yml`.

```yaml
---
jellyfin_data_path: ~          # required; set via make jellyfin
```

### `tasks/main.yml`

Follow the four-step pattern used by existing apps:

```yaml
# 0. Guard: fail fast if required variables are not set.
- name: Assert jellyfin_data_path is set
  ansible.builtin.assert:
    that: jellyfin_data_path is not none
    fail_msg: >-
      jellyfin_data_path is not set for '{{ inventory_hostname }}'.
      Add it to ansible/inventory/host_vars/{{ inventory_hostname }}.yml.

# 1. Directories.
- name: Ensure Jellyfin data directory exists
  ansible.builtin.file:
    path: "{{ jellyfin_data_path }}"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: "0750"
  become: true

# 2. Deploy container unit via shared service_adapter template.
- name: Prepare service adapter paths for Jellyfin
  ansible.builtin.include_role:
    name: service_adapter
    tasks_from: prepare
  vars:
    service_adapter_name: "{{ jellyfin_service_name }}"
    service_adapter_user: "{{ ansible_user }}"
    service_adapter_run_script: "{{ app_user_home }}/bin/run-jellyfin.sh"

- name: Install Jellyfin Podman quadlet
  ansible.builtin.include_role:
    name: service_adapter
    tasks_from: write_container
  vars:
    container_description: "Jellyfin Media Server"
    container_image: "{{ jellyfin_image }}"
    container_name: "{{ jellyfin_service_name }}"
    container_ports:
      - "{{ jellyfin_port }}:8096"
    container_volumes:
      - "{{ jellyfin_data_path }}:/config"

# 3. Wire up service management.
- name: Register Jellyfin with service_adapter
  ansible.builtin.import_role:
    name: service_adapter
  vars:
    service_adapter_name: "{{ jellyfin_service_name }}"
    service_adapter_user: "{{ ansible_user }}"
    service_adapter_run_script: "{{ app_user_home }}/bin/run-jellyfin.sh"
```

---

## Step 3 — Regenerate `group_vars/all/vars.yml`

```bash
make generate-apps
```

This reads `registry.yml` and emits `service_name`, `image`, `port`, `runtime_uid/gid`, and `shared_vars` for every app into `ansible/group_vars/all/vars.yml`. Commit nothing from this step — `vars.yml` is gitignored.

---

## Step 4 — Update `tests/test_ansible_apps.py`

Two things need updating:

**1. Expected app list** — add `jellyfin` in registry order:

```python
def test_registry_has_expected_keys() -> None:
    assert ANSIBLE_DATA.all_apps() == ["minio", "postgres", "baikal", "jellyfin"]
```

**2. Add any app-specific contract assertions** (optional but encouraged):

```python
def test_jellyfin_entry_data() -> None:
    entry = ANSIBLE_DATA.get_app_entry("jellyfin")
    assert entry.service_type == "containerized"
    assert entry.dependencies == []
```

Run `make test` to verify everything passes before provisioning.

---

## Step 5 — Provision

On a fresh host, run `make setup` first to install base dependencies (podman, rclone, auto-updates):

```bash
make setup HOST=rpi
```

Then provision the app:

```bash
make jellyfin HOST=rpi
```

The preflight step will prompt for any missing `host_vars` and vault secrets before handing off to Ansible. For subsequent re-provisions (e.g. to update the image tag), the same command is idempotent.

---

## Checklist

- [ ] Entry added to `ansible/registry.yml` (service_name, image, port, runtime_uid/gid, preflight_vars, vault_secrets)
- [ ] `ansible/apps/<app>/playbook.yml` — written by hand following existing app pattern
- [ ] `ansible/apps/<app>/defaults/main.yml` — null out required vars only (no service_name/image/port — those come from registry)
- [ ] `ansible/apps/<app>/tasks/main.yml` — assert → dirs → prepare + write_container → service_adapter
- [ ] `make generate-apps` run to update `group_vars/all/vars.yml`
- [ ] `tests/test_ansible_apps.py` updated and `make test` passes
- [ ] `make lint-repo-policy` passes
