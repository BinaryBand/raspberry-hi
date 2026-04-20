# Plan: Preflight Validation for Lifecycle Operations

## Context

`make backup`, `make restore`, and `make cleanup` run lifecycle playbooks that require
restic/rclone vars to be set. Currently the only pre-run validation is `_vault_check`
(confirms vault password file exists and become_passwords are present) plus `APP=` for
restore/cleanup. If a host hasn't had `make restic` run, backup/restore fail mid-playbook
with unhelpful Ansible variable-undefined errors.

## Goal

Run the same interactive preflight that `make <app>` uses before backup/restore. Missing
restic vars get prompted at the Make layer rather than failing silently mid-playbook.

## Design

`scripts/preflight.py restic` already reads `ansible/apps/restic/preflight.yml` and
prompts for any unset vars/secrets. No new files or scripts are needed.

### Makefile changes

Add `_backup_preflight` (reuses existing `_%_preflight` pattern):

```makefile
_backup_preflight: _vault_check
	HOST=$(HOST) poetry run python ./scripts/preflight.py restic
```

Wire into `backup` and `restore`:

```makefile
backup: _backup_preflight
restore: _backup_preflight _restore_preflight
```

`cleanup` has no restic dependency — unchanged.

## Scope

- `backup` and `restore` gain restic preflight validation.
- `cleanup` is unchanged.
- No new scripts or YAML files required.

## Verification

```bash
# With restic vars unset: should prompt interactively instead of failing in Ansible
make backup HOST=rpi
make restore APP=minio HOST=rpi

# With all vars set: should pass through immediately
make backup HOST=rpi

# Cleanup must still work without restic vars
make cleanup APP=minio HOST=rpi

make lint && make test
```
