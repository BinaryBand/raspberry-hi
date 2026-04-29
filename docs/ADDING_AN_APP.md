# Adding a New App

This guide walks through every step needed to add a new application to the repo from scratch — registry entry, Ansible role, and tests.

The worked example is a hypothetical `jellyfin` app: a containerized media server with no dependencies.

---

## Overview

Adding an app touches five things:

1. **`ansible/registry.yml`** — the single declaration that drives preflight, `make` targets, and policy checks.
2. **`ansible/apps/<app>/`** — the Ansible role (tasks, defaults, templates, etc.).
3. **`make generate-apps`** — regenerates `ansible/apps/<app>/playbook.yml` from the registry.
4. **`tests/test_ansible_apps.py`** — update the expected app list and add any contract assertions.
5. **`make setup`** — run once on a fresh host to provision base dependencies before installing apps.

---

## Step 1 — Declare the app in `ansible/registry.yml`

Every registered field drives real behaviour:

```yaml
apps:
  jellyfin:
    service_type: containerized     # containerized | tool
    # backup, restore, and cleanup fields have been removed
    service_name_var: jellyfin_service_name
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

**Field reference**

| Field | Type | Effect |
|---|---|---|
| `service_type` | `containerized` \| `tool` | `containerized` apps are required to have a playbook and main tasks. |
| `dependencies` | list | Apps that must be preflighted and provisioned before this one. Preflight chaining and `import_playbook` ordering are both derived from this list. |
| `preflight_vars` | map | Variables written to `host_vars/<host>.yml` before provisioning. Null defaults (`~`) trigger a prompt; non-null defaults are offered as suggestions. Use `type: rclone_remote` to get an interactive remote selector. |
| `vault_secrets` | list | Secrets written to the vault before provisioning. `hidden: true` uses password-style input. |

**Persistent apps** (containerized) must declare at least one `*_data_path` preflight var.

**App with a dependency** (e.g. Baikal depending on PostgreSQL):

```yaml
dependencies:
  - postgres
```

Preflight will recurse into `postgres` first. `make generate-apps` will prepend `import_playbook: ../postgres/playbook.yml` to the generated playbook.

---

## Step 2 — Create the Ansible role

```
ansible/apps/jellyfin/
  defaults/main.yml          # role defaults; null out required vars here
  tasks/main.yml             # provisioning tasks
  # backup.yml, restore.yml, and cleanup.yml are no longer required or supported
  handlers/main.yml          # optional: restart handler
  templates/                 # optional: .container.j2, .env.j2, etc.
```

### `defaults/main.yml`

Null out any variable that the operator must supply (preflight will prompt for it). Pin image tags explicitly — `:latest` is rejected by Semgrep.

```yaml
---
jellyfin_image: docker.io/jellyfin/jellyfin:10.10.7
jellyfin_data_path: ~          # required; set via make preflight or make jellyfin
jellyfin_port: 8096
jellyfin_service_name: jellyfin
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

# 2. Deploy container unit.
- name: Install Jellyfin Podman quadlet
  ansible.builtin.template:
    src: jellyfin.container.j2
    dest: "{{ app_user_home }}/.config/containers/systemd/jellyfin.container"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: "0644"
  become: true
  notify: restart jellyfin

# 3. Wire up service management.
- name: Register Jellyfin with service_adapter
  ansible.builtin.import_role:
    name: service_adapter
  vars:
    svc_name: "{{ jellyfin_service_name }}"
    svc_user: "{{ ansible_user }}"
    svc_run_script: "{{ app_user_home }}/bin/run-jellyfin.sh"
```



---

## Step 3 — Regenerate the per-app playbook

```bash
make generate-apps
```

This reads `registry.yml` and writes `ansible/apps/jellyfin/playbook.yml`. Commit the generated file alongside the role. Do not edit the playbook by hand — it will be overwritten on the next `make generate-apps` run.

If the app has dependencies, the generated playbook will open with the appropriate `import_playbook` lines.

---

## Step 4 — Update `tests/test_ansible_apps.py`

Two lines need updating:

**1. Expected app list** — add `jellyfin` in registry order:

```python
def test_registry_has_expected_keys() -> None:
    assert ANSIBLE_DATA.all_apps() == ["minio", "postgres", "baikal","jellyfin"]
```

**2. Add any app-specific contract assertions** (optional but encouraged):

```python
def test_jellyfin_entry_data() -> None:
    entry = ANSIBLE_DATA.get_app_entry("jellyfin")
    assert entry.service_type == "containerized"
    # backup field is no longer present
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

- [ ] Entry added to `ansible/registry.yml`
- [ ] `ansible/apps/<app>/defaults/main.yml` — null out required vars, pin image tag
- [ ] `ansible/apps/<app>/tasks/main.yml` — assert → directories → container → service_adapter
- [ ] `make generate-apps` run and `playbook.yml` committed
- [ ] `tests/test_ansible_apps.py` updated and `make test` passes
- [ ] `make lint-repo-policy` passes
