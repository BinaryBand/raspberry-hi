# Adding a New App

This guide walks through every step needed to add a new application to the repo from scratch — registry entry, Ansible role, and tests.

The worked example is a hypothetical `jellyfin` app: a containerized media server with no dependencies.

---

## Overview

Adding an app touches five things:

1. **`ansible/registry.yml`** — the single declaration that drives preflight, `make` targets, backup/restore eligibility, and policy checks.
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
    backup: true                    # include in restic backup playbook
    restore: true                   # include in restic restore playbook
    cleanup: true                   # expose via make cleanup APP=jellyfin
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
| `service_type` | `containerized` \| `tool` | `containerized` apps are required to have `backup/` and `restore/` subdirs (enforced by repo-policy). |
| `backup` / `restore` / `cleanup` | bool | Gates inclusion in `make backup`, `make restore`, and `make cleanup`. Also drives repo-policy dir checks. |
| `dependencies` | list | Apps that must be preflighted and provisioned before this one. Preflight chaining and `import_playbook` ordering are both derived from this list. |
| `preflight_vars` | map | Variables written to `host_vars/<host>.yml` before provisioning. Null defaults (`~`) trigger a prompt; non-null defaults are offered as suggestions. Use `type: rclone_remote` to get an interactive remote selector. |
| `vault_secrets` | list | Secrets written to the vault before provisioning. `hidden: true` uses password-style input. |

**Persistent apps** (containerized, backup, or restore) must declare at least one `*_data_path` preflight var. Repo-policy enforces this.

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
  meta/main.yml              # always empty dependencies: []
  tasks/main.yml             # provisioning tasks
  tasks/cleanup.yml          # teardown tasks (required if cleanup: true)
  backup/main.yml            # restic snapshot tasks (required if backup: true)
  restore/main.yml           # restic restore tasks (required if restore: true)
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

### `meta/main.yml`

Always empty. Non-empty `dependencies:` cause duplicate execution under per-app playbook invocation and are rejected by Semgrep (`ansible-meta-no-non-empty-dependencies`). Cross-app ordering belongs in `registry.yml`.

```yaml
---
dependencies: []
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

### `backup/main.yml` (if `backup: true`)

Validate that the data path exists on the host, then delegate to the restic role:

```yaml
- name: Check Jellyfin backup paths on host
  ansible.builtin.stat:
    path: "{{ item }}"
  loop:
    - "{{ jellyfin_data_path }}"
  register: _jellyfin_backup_paths
  become: true
  become_user: "{{ ansible_user }}"

- name: Fail if Jellyfin backup paths are missing
  ansible.builtin.fail:
    msg: >-
      Jellyfin backup path does not exist: {{ item.item }}.
      Run 'make jellyfin' to provision Jellyfin first.
  when: not item.stat.exists
  loop: "{{ _jellyfin_backup_paths.results }}"

- name: Snapshot Jellyfin data to restic
  ansible.builtin.include_role:
    name: restic
    tasks_from: backup
  vars:
    restic_snapshot_paths:
      - "{{ jellyfin_data_path }}"
    restic_snapshot_tag: jellyfin
```

### `restore/main.yml` (if `restore: true`)

Stop the service, restore the snapshot, restart:

```yaml
---
- name: Stop Jellyfin service
  ansible.builtin.include_role:
    name: service_adapter
    tasks_from: stop
  vars:
    svc_name: "{{ jellyfin_service_name }}"
    svc_user: "{{ ansible_user }}"

- name: Restore Jellyfin data from restic
  ansible.builtin.include_role:
    name: restic
    tasks_from: restore
  vars:
    restic_snapshot_tag: jellyfin
    restic_restore_target: /

- name: Start Jellyfin service
  ansible.builtin.include_role:
    name: service_adapter
    tasks_from: start
  vars:
    svc_name: "{{ jellyfin_service_name }}"
    svc_user: "{{ ansible_user }}"
```

### `tasks/cleanup.yml` (if `cleanup: true`)

Deregister the service, remove the container, remove config and data:

```yaml
---
- name: Deregister Jellyfin service
  ansible.builtin.include_role:
    name: service_adapter
    tasks_from: teardown
  vars:
    svc_name: "{{ jellyfin_service_name }}"
    svc_user: "{{ ansible_user }}"
    svc_run_script: "{{ app_user_home }}/bin/run-jellyfin.sh"

- name: Remove Jellyfin container
  ansible.builtin.command:
    argv: [podman, rm, --force, --ignore, "{{ jellyfin_service_name }}"]
  become: true
  become_user: "{{ ansible_user }}"
  changed_when: false

- name: Remove Jellyfin data directory
  ansible.builtin.file:
    path: "{{ jellyfin_data_path }}"
    state: absent
  become: true
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
    assert ANSIBLE_DATA.all_apps() == ["minio", "postgres", "baikal", "restic", "jellyfin"]
```

**2. Add any app-specific contract assertions** (optional but encouraged):

```python
def test_jellyfin_entry_data() -> None:
    entry = ANSIBLE_DATA.get_app_entry("jellyfin")
    assert entry.service_type == "containerized"
    assert entry.backup is True
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
- [ ] `ansible/apps/<app>/meta/main.yml` — `dependencies: []`
- [ ] `ansible/apps/<app>/tasks/main.yml` — assert → directories → container → service_adapter
- [ ] `ansible/apps/<app>/backup/main.yml` — if `backup: true`
- [ ] `ansible/apps/<app>/restore/main.yml` — if `restore: true`
- [ ] `ansible/apps/<app>/tasks/cleanup.yml` — if `cleanup: true`
- [ ] `make generate-apps` run and `playbook.yml` committed
- [ ] `tests/test_ansible_apps.py` updated and `make test` passes
- [ ] `make lint-repo-policy` passes
