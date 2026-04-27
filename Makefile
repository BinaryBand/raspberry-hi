SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
MAKEFLAGS += --warn-undefined-variables

POETRY := poetry run
PY_DIRS := linux_hi/ models/ tests/

ANSIBLE_DIR := ansible
ROLES := service_adapter rclone
APPS := $(shell $(POETRY) python -c "from models import ANSIBLE_DATA; print(' '.join(ANSIBLE_DATA.all_apps()))")
RESTORE_APPS := $(shell $(POETRY) python -c "from models import ANSIBLE_DATA; print(' '.join(ANSIBLE_DATA.restore_apps()))")
CLEANUP_APPS := $(shell $(POETRY) python -c "from models import ANSIBLE_DATA; print(' '.join(ANSIBLE_DATA.cleanup_apps()))")

# Default host alias — set to the first host in ansible/inventory/hosts.yml.
# Override per-run: HOST=myserver make site
HOST ?= rpi

# Single inventory call — emits "host user port key" on one line so Make can
# split it into four variables with $(word N,...).  No ANSIBLE_CONFIG needed:
# we only read hosts.yml + host_vars/, not group_vars or vault.
# python3 returns '' on any error rather than crashing Make evaluation.
# Spaces are not valid in IPs, usernames, ports, or key paths, so word-split is safe.
_INV := $(shell ansible-inventory -i $(ANSIBLE_DIR)/inventory/hosts.yml --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); \
	print(d.get('ansible_host',''), d.get('ansible_user',''), d.get('ansible_port', 22), d.get('ansible_ssh_private_key_file',''))" \
	2>/dev/null)
REMOTE_HOST := $(word 1,$(_INV))
REMOTE_USER := $(word 2,$(_INV))
REMOTE_PORT := $(or $(word 3,$(_INV)),22)
REMOTE_KEY := $(word 4,$(_INV))

# Shared Ansible flags — avoids repeating paths across targets.
ANSIBLE_CFG := $(CURDIR)/ansible/ansible.cfg
VAULT_PASS := $(CURDIR)/ansible/.vault-password
INV := ansible/inventory/hosts.yml
_ANSIBLE_FLAGS := ANSIBLE_CONFIG=$(ANSIBLE_CFG) ansible-playbook -i $(INV) --vault-password-file $(VAULT_PASS) --limit $(HOST)
SETUP_PLAY := $(_ANSIBLE_FLAGS) ansible/setup.yml

_APP_PREFLIGHTS := $(addprefix _,$(addsuffix _preflight,$(APPS)))

.PHONY: add-hostkey ansible-lint backup backup-check baikal bootstrap check checkmake cleanup cpd repo-policy
.PHONY: format format-check generate-apps help lint logs mount ping ty rclone restore restore-check ruff
.PHONY: ruff-check ruff-fix ruff-format ruff-help semgrep setup ssh status test test-e2e vault-edit vulture
.PHONY: hosts-add hosts-list hosts-remove
.PHONY: _backup_preflight _ci _cleanup_preflight _inv_check _restore_preflight _vault_check $(APPS)

help:
	@echo "Usage: make [HOST=<alias>] <target>"
	@echo ""
	@echo "  bootstrap     First-time setup: vault password + encrypt credentials"
	@echo "  check         Validate prerequisites (vault file, Pi reachability)"
	@echo "  lint          Run the full static quality gate (Ruff, format check, Pyright, Semgrep, cpd, ansible-lint)"
	@echo "  ruff          Run Ruff lint checks over linux_hi/, models/, and tests/"
	@echo "  ruff-check    Run Ruff lint without auto-fix"
	@echo "  ruff-fix      Auto-fix Ruff lint violations"
	@echo "  ruff-format   Reformat Python files with Ruff"
	@echo "  ruff-help     Show Ruff command-line help"
	@echo "  format-check  Run Ruff formatting checks over linux_hi/, models/, and tests/"
	@echo "  ty            Run ty type checks over the repository"
	@echo "  semgrep       Run Semgrep architectural and process audits"
	@echo "  cpd           Fail on any copy-paste duplication (jscpd, threshold 0%)"
	@echo "  vulture       Check for unused Python code (min confidence 80%)"
	@echo "  checkmake     Lint Makefile style and quality with mbake"
	@echo "  repo-policy   Run repository structural and architecture policy checks"
	@echo "  ansible-lint  Run ansible-lint over ansible/"
	@echo "  test          Run unit + stub tests (no infra needed)"
	@echo "  test-e2e      Run live host tests (requires host reachable, HOST=rpi)"
	@echo "  setup         Provision base dependencies on a host (HOST=rpi|rpi2|debian)"
	@echo "  generate-apps Regenerate per-app playbooks from ansible/registry.yml"
	@echo "  <app>         Provision a named app — runs preflight automatically"
	@echo "                Apps: $(APPS)"
	@echo "  rclone        Configure project rclone remotes and vault the config"
	@echo "  backup        Back up all apps to the restic repository"
	@echo "  backup-check  Dry-run backup validation (no snapshots or prune writes)"
	@echo "  restore       Restore a named app from the latest restic snapshot (APP=$(RESTORE_APPS))"
	@echo "  restore-check Dry-run restore validation for one app (APP=$(RESTORE_APPS))"
	@echo "  mount         Interactive: pick and mount external storage"
	@echo "  hosts-add     Add a host to inventory, host_vars, and vault (NAME ADDR USER PORT KEY)"
	@echo "  hosts-remove  Remove a host from inventory, host_vars, and vault (NAME=<alias>)"
	@echo "  hosts-list    List configured inventory hosts and their connection details"
	@echo "  vault-edit    Edit encrypted secrets in \$$EDITOR"
	@echo "  ssh           Open a shell on the host"
	@echo "  ping          Test Ansible connectivity"
	@echo "  add-hostkey   Trust the host's SSH host key (run before first site)"
	@echo ""
	@echo "  cleanup       Purge an app and all its data from the host (APP=$(CLEANUP_APPS))"
	@echo "  status        Show service status on the host (SVC=<service>)"
	@echo "  logs          Tail service logs from the host (SVC=<service>)"
	@echo ""
	@echo "  HOST defaults to 'rpi'; override with: HOST=myserver make site"

check:
	$(POETRY) python -m linux_hi.cli.check

lint: ruff format-check ty semgrep cpd vulture ansible-lint checkmake repo-policy

# Ruff targets: help / check / format / fix
ruff: ruff-check

ruff-help:
	$(POETRY) ruff --help

ruff-check:
	$(POETRY) ruff check $(PY_DIRS)

ruff-format:
	$(POETRY) ruff format $(PY_DIRS)

ruff-fix:
	$(POETRY) ruff check --fix $(PY_DIRS)

format-check:
	$(POETRY) ruff format --check $(PY_DIRS)

format: ruff-format

_ci:
	$(POETRY) ruff check $(PY_DIRS)
	$(POETRY) ty check
	$(POETRY) semgrep scan --config .semgrep.yml --error
	$(POETRY) mbake format --check Makefile
	$(POETRY) python -m linux_hi.cli.repo_policy_check
	$(POETRY) pytest -q tests/ --ignore=tests/test_lint.py

ty:
	$(POETRY) ty check

semgrep:
	$(POETRY) semgrep scan --config .semgrep.yml --error

cpd:
	npx jscpd --format python --min-tokens 50 --threshold 0 --ignore '**/.venv/**,**/typings/**' .

vulture:
	$(POETRY) vulture --min-confidence 80 $(PY_DIRS)

ansible-lint:
	ANSIBLE_CONFIG=$(ANSIBLE_CFG) $(POETRY) ansible-lint ansible

checkmake:
	$(POETRY) mbake format --check Makefile

repo-policy:
	$(POETRY) python -m linux_hi.cli.repo_policy_check

test:
	$(POETRY) pytest tests/ -v

test-e2e:
	HOST=$(HOST) $(POETRY) pytest tests/e2e/ -v -m e2e -s

generate-apps:
	$(POETRY) python -m linux_hi.cli.generate_apps

ping:
	ansible devices -m ping -i $(INV) || true

add-hostkey: _inv_check
	ssh-keyscan -H $(REMOTE_HOST) >> ~/.ssh/known_hosts

ssh: _inv_check
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) -p $(REMOTE_PORT)

hosts-add:
	NAME=$(NAME) ADDR=$(ADDR) USER=$(USER) PORT=$(PORT) KEY=$(KEY) $(POETRY) python -m linux_hi.cli.hosts add

hosts-remove:
	NAME=$(NAME) $(POETRY) python -m linux_hi.cli.hosts remove

hosts-list:
	$(POETRY) python -m linux_hi.cli.hosts list

vault-edit:
	EDITOR="$${EDITOR:-nano}" ANSIBLE_CONFIG=$(ANSIBLE_CFG) ansible-vault edit ansible/group_vars/all/vault.yml --vault-password-file $(VAULT_PASS)

bootstrap:
	$(POETRY) python -m linux_hi.cli.bootstrap

_vault_check:
	@$(POETRY) python -m linux_hi.cli.check --vault-only

_inv_check:
	@test -n "$(REMOTE_HOST)" || { echo "Error: HOST='$(HOST)' not found in inventory — check ansible/inventory/hosts.yml and host_vars/$(HOST).yml"; exit 1; }

mount: _vault_check
	HOST=$(HOST) $(POETRY) python -m linux_hi.cli.mount

rclone: _vault_check
	$(POETRY) python -m linux_hi.cli.rclone

_backup_preflight: _vault_check
	HOST=$(HOST) $(POETRY) python -m linux_hi.cli.preflight restic

backup: _backup_preflight
	$(_ANSIBLE_FLAGS) ansible/backup.yml

backup-check: _backup_preflight
	$(_ANSIBLE_FLAGS) --check ansible/backup.yml

_restore_preflight: _vault_check
	@test -n "$(APP)" || { echo "Error: APP is required — supported restore apps: $(RESTORE_APPS)"; exit 1; }
	@case " $(RESTORE_APPS) " in *" $(APP) "*) ;; *) echo "Error: APP='$(APP)' is not restorable. Supported restore apps: $(RESTORE_APPS)"; exit 1 ;; esac

restore: _backup_preflight _restore_preflight
	$(_ANSIBLE_FLAGS) ansible/restore.yml -e restore_app=$(APP)

restore-check: _backup_preflight _restore_preflight
	$(_ANSIBLE_FLAGS) --check ansible/restore.yml -e restore_app=$(APP)

# Generic preflight — works for any app registered in APPS.
_%_preflight: _vault_check
	HOST=$(HOST) $(POETRY) python -m linux_hi.cli.preflight $*

# Generic app provisioning — each app in APPS gets: make <app> → preflight → per-app playbook.
# Dependency preflight chaining is handled by linux_hi.cli.preflight via registry.yml.
$(APPS): %: _%_preflight
	$(_ANSIBLE_FLAGS) ansible/apps/$@/playbook.yml

status: _inv_check
	@test -n "$(SVC)" || { echo "Error: SVC is required — e.g. make status SVC=minio"; exit 1; }
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) -p $(REMOTE_PORT) "systemctl --user status $(SVC) --no-pager"

logs: _inv_check
	@test -n "$(SVC)" || { echo "Error: SVC is required — e.g. make logs SVC=minio"; exit 1; }
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) -p $(REMOTE_PORT) "journalctl --user -u $(SVC) -n 50 --no-pager"

_cleanup_preflight: _vault_check
	@test -n "$(APP)" || { echo "Error: APP is required — supported cleanup apps: $(CLEANUP_APPS)"; exit 1; }
	@case " $(CLEANUP_APPS) " in *" $(APP) "*) ;; *) echo "Error: APP='$(APP)' is not cleanable. Supported cleanup apps: $(CLEANUP_APPS)"; exit 1 ;; esac

cleanup: _cleanup_preflight
	$(_ANSIBLE_FLAGS) ansible/cleanup.yml -e cleanup_app=$(APP)

setup: _vault_check
	$(SETUP_PLAY)

%:
	@echo "Unknown target '$@'. Run 'make help' for available targets." && exit 1