SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
MAKEFLAGS += --warn-undefined-variables

POETRY := poetry run
PY_DIRS := linux_hi/ tests/

ANSIBLE_DIR := ansible
COVERAGE_FLOOR ?= 55
APPS := $(shell $(POETRY) python -c "from linux_hi.models import ANSIBLE_DATA; print(' '.join(ANSIBLE_DATA.containerized_apps()))")

# Default host alias — prefer first SSH-capable inventory host.
# Override per-run: HOST=myserver make site
HOST ?= $(shell $(POETRY) python -c "from linux_hi.models import ANSIBLE_DATA; hs=ANSIBLE_DATA.inventory_hosts(); print(next((h for h in hs if str(ANSIBLE_DATA.read_host_vars_raw(h).get('ansible_connection','')).lower()!='local' and str(ANSIBLE_DATA.read_host_vars_raw(h).get('ansible_host', h)) not in ('localhost','127.0.0.1','::1')), hs[0] if hs else ''))")

# Optional operator inputs used by config and maintenance targets.
NAME ?=
ADDRESS ?=
ADDR ?=
SECRET ?=
KEY ?=
PORT ?=
APP ?=
SVC ?=
TAGS ?=

# Single inventory call — emits "host user port key" on one line so Make can
# split it into four variables with $(word N,...).
# We only read hosts.yml + host_vars/, not group_vars or vault.
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
VAULT_PASS := $(CURDIR)/ansible/.vault-password
INV := ansible/inventory/hosts.yml
_ANSIBLE_FLAGS := ansible-playbook -i $(INV) --vault-password-file $(VAULT_PASS) --limit $(HOST) $(if $(TAGS),--tags $(TAGS),)
SETUP_PLAY := $(_ANSIBLE_FLAGS) ansible/playbooks/setup.yml

_APP_PREFLIGHTS := $(addprefix _,$(addsuffix _preflight,$(APPS)))

.PHONY: add-hostkey baikal bootstrap caddy check doctor generate-apps help lint logs mount ping
.PHONY: format rclone ruff ruff-fix ruff-format setup ssh status
.PHONY: test test-e2e vault-edit
.PHONY: config-rclone config-rclone-edit config-hosts config-hosts-add config-hosts-remove config-hosts-list config-hosts-edit
.PHONY: config-vault config-vault-add config-vault-remove config-vault-list config-vault-edit
.PHONY: lint-ansible lint-ansible-coverage lint-ansible-roles-coverage lint-check lint-checkmake lint-coverage lint-cpd lint-format lint-lizard lint-repo-policy
.PHONY: lint-semgrep lint-ty lint-vulture
.PHONY: _ci _generate_check _inv_check _vault_check $(APPS)

help:
	@echo "Usage: make [HOST=<alias>] <target>"
	@echo ""
	@echo "  bootstrap     First-time setup: vault password + encrypt credentials"
	@echo "  check         Validate prerequisites (vault file, Pi reachability)"
	@echo "  doctor        Environment health check (binaries, hosts, SSH keys)"
	@echo "  lint               Run the full static quality gate"
	@echo "  lint-check         Ruff lint checks"
	@echo "  lint-format        Ruff format check"
	@echo "  lint-ty            ty type checks"
	@echo "  lint-semgrep       Semgrep architectural and process audits"
	@echo "  lint-cpd           Copy-paste duplication check (jscpd, threshold 0%)"
	@echo "  lint-coverage       Coverage floor check (config/lint.toml)"
	@echo "  lint-vulture       Unused Python code check"
	@echo "  lint-lizard        Cyclomatic complexity and function length check"
	@echo "  lint-checkmake     Makefile style check (mbake)"
	@echo "  lint-repo-policy   Repository structural and architecture policy checks"
	@echo "  lint-ansible       ansible-lint over ansible/"
	@echo "  lint-ansible-coverage  Ansible app test coverage floor check (config/lint.toml)"
	@echo "  lint-ansible-roles-coverage  Setup-role test coverage floor check (config/lint.toml)"
	@echo "  ruff               Alias for lint-check"
	@echo "  ruff-fix           Auto-fix Ruff lint violations"
	@echo "  ruff-format        Reformat Python files with Ruff"
	@echo "  test          Run unit + stub tests (no infra needed)"
	@echo "  test-e2e      Run live host tests (requires host reachable; HOST defaults to first SSH-capable inventory alias)"
	@echo "  setup         Provision base dependencies on a host (HOST defaults to first SSH-capable inventory alias)"
	@echo "  caddy         Provision Caddy reverse proxy (native system service)"
	@echo "  generate-apps Regenerate ansible/group_vars/all/vars.yml from ansible/registry.yml"
	@echo "  <app>         Provision a named app — runs preflight automatically"
	@echo "                Apps: $(APPS)"
	@echo "  mount         Interactive: pick and mount external storage"
	@echo "  rclone        Configure project rclone remotes and vault the config"
	@echo "  config-rclone Open interactive rclone config editor for ansible/config/rclone.conf"
	@echo "  config-rclone-edit Open ansible/config/rclone.conf in nano"
	@echo "  config-hosts  Hosts config entrypoint (defaults to list)"
	@echo "  config-hosts-add Add a host (supports NAME ADDRESS/ADDR SECRET/KEY SSH_USER PORT)"
	@echo "  config-hosts-remove Remove a host (supports NAME)"
	@echo "  config-hosts-list List configured hosts"
	@echo "  config-hosts-edit Open ansible/inventory/hosts.yml in nano"
	@echo "  config-vault  Vault config entrypoint (defaults to list)"
	@echo "  config-vault-add Add/update a vault key (supports NAME)"
	@echo "  config-vault-remove Remove a vault key (supports NAME)"
	@echo "  config-vault-list List vault keys"
	@echo "  config-vault-edit Open vault editor in nano (ansible-vault edit)"
	@echo "  vault-edit    Edit encrypted secrets in \$$EDITOR"
	@echo "  ssh           Open a shell on the host"
	@echo "  ping          Test Ansible connectivity"
	@echo "  add-hostkey   Trust the host's SSH host key (run before first site)"
	@echo ""
	@echo "  status        Show service status on the host (SVC=<service>)"
	@echo "  logs          Tail service logs from the host (SVC=<service>)"
	@echo ""
	@echo "  HOST defaults to first SSH-capable inventory alias; override with: HOST=myserver make site"
	@echo "  TAGS filters Ansible tasks by tag; e.g. TAGS=auto-updates make setup"

check:
	$(POETRY) python -m linux_hi.cli.check

doctor:
	$(POETRY) python -m linux_hi.cli.check --doctor

lint: lint-check lint-format lint-ty lint-semgrep lint-cpd lint-vulture lint-lizard lint-ansible lint-ansible-coverage lint-ansible-roles-coverage lint-checkmake lint-repo-policy

# Ruff targets: check / format / fix
lint-check:
	$(POETRY) ruff check $(PY_DIRS)

ruff: lint-check

ruff-format:
	$(POETRY) ruff format $(PY_DIRS)

ruff-fix:
	$(POETRY) ruff check --fix $(PY_DIRS)

lint-format:
	$(POETRY) ruff format --check $(PY_DIRS)

format: ruff-format

_ci:
	$(POETRY) ruff check $(PY_DIRS)
	$(POETRY) ty check
	$(POETRY) semgrep scan --config rules/ --error
	$(POETRY) mbake format --check Makefile
	$(POETRY) pytest -q tests/ --ignore=tests/unit/test_lint.py --cov=linux_hi --cov-report=term --cov-fail-under=$(COVERAGE_FLOOR)

lint-ty:
	$(POETRY) ty check

lint-semgrep:
	$(POETRY) semgrep scan --config rules/ --error

lint-cpd:
	npx jscpd --config config/jscpd.json .

lint-vulture:
	$(POETRY) python -m linux_hi.cli.linters.vulture

lint-coverage:
	$(POETRY) python -m linux_hi.cli.linters.coverage

lint-lizard:
	$(POETRY) python -m linux_hi.cli.linters.lizard

lint-ansible:
	$(POETRY) ansible-lint ansible

lint-ansible-coverage:
	$(POETRY) python -m linux_hi.cli.linters.ansible_coverage

lint-ansible-roles-coverage:
	$(POETRY) python -m linux_hi.cli.linters.ansible_roles_coverage

lint-checkmake:
	$(POETRY) mbake format --check Makefile

lint-repo-policy:
	$(POETRY) python -m linux_hi.cli.linters.repo_policy_check

test:
	$(POETRY) pytest tests/ -v --cov=linux_hi --cov-report=term --cov-fail-under=$(COVERAGE_FLOOR)

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

config-rclone:
	rclone config --config ansible/config/rclone.conf

config-rclone-edit:
	nano ansible/config/rclone.conf

config-hosts:
	$(POETRY) python -m linux_hi.cli.hosts

config-hosts-list:
	$(POETRY) python -m linux_hi.cli.hosts list

config-hosts-edit:
	nano ansible/inventory/hosts.yml

config-hosts-add:
	@args=""; \
	if [ -n "$(NAME)" ]; then args="$$args --name $(NAME)"; fi; \
		if [ -n "$(ADDRESS)" ]; then args="$$args --address $(ADDRESS)"; elif [ -n "$(ADDR)" ]; then args="$$args --address $(ADDR)"; fi; \
			if [ -n "$(SECRET)" ]; then args="$$args --secret $(SECRET)"; elif [ -n "$(KEY)" ]; then args="$$args --secret $(KEY)"; fi; \
				if [ -n "$(SSH_USER)" ]; then args="$$args --user $(SSH_USER)"; fi; \
					if [ -n "$(PORT)" ]; then args="$$args --port $(PORT)"; fi; \
						$(POETRY) python -m linux_hi.cli.hosts add $$args

config-hosts-remove:
	@args=""; \
	if [ -n "$(NAME)" ]; then args="$$args --name $(NAME)"; fi; \
		$(POETRY) python -m linux_hi.cli.hosts remove $$args

config-vault:
	$(POETRY) python -m linux_hi.cli.vault

config-vault-list:
	$(POETRY) python -m linux_hi.cli.vault list

config-vault-edit:
	EDITOR=nano ansible-vault edit ansible/group_vars/all/vault.yml --vault-password-file $(VAULT_PASS)

config-vault-add:
	@args=""; \
	if [ -n "$(NAME)" ]; then args="$$args --name $(NAME)"; fi; \
		$(POETRY) python -m linux_hi.cli.vault add $$args

config-vault-remove:
	@args=""; \
	if [ -n "$(NAME)" ]; then args="$$args --name $(NAME)"; fi; \
		$(POETRY) python -m linux_hi.cli.vault remove $$args

vault-edit:
	EDITOR="$${EDITOR:-nano}" ansible-vault edit ansible/group_vars/all/vault.yml --vault-password-file $(VAULT_PASS)

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

# Generic preflight — works for any app registered in APPS.
_%_preflight: _vault_check
	HOST=$(HOST) $(POETRY) python -m linux_hi.cli.preflight $*

_generate_check:
	@if [ ! -f ansible/group_vars/all/vars.yml ]; then \
		echo "  [INFO]  ansible/group_vars/all/vars.yml missing — running 'make generate-apps'..."; \
		$(MAKE) generate-apps; \
	fi

# Generic app provisioning — each app in APPS gets: make <app> → preflight → per-app playbook.
# Dependency preflight chaining is handled by linux_hi.cli.preflight via registry.yml.
$(APPS): %: _generate_check _%_preflight
	$(_ANSIBLE_FLAGS) ansible/apps/$@/playbook.yml

status: _inv_check
	@test -n "$(SVC)" || { echo "Error: SVC is required — e.g. make status SVC=minio"; exit 1; }
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) -p $(REMOTE_PORT) "systemctl --user status $(SVC) --no-pager"

logs: _inv_check
	@test -n "$(SVC)" || { echo "Error: SVC is required — e.g. make logs SVC=minio"; exit 1; }
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) -p $(REMOTE_PORT) "journalctl --user -u $(SVC) -n 50 --no-pager"

setup: _vault_check
	HOST=$(HOST) $(POETRY) python -m linux_hi.cli.preflight setup
	$(SETUP_PLAY)

caddy: _vault_check
	$(_ANSIBLE_FLAGS) ansible/playbooks/site.yml --tags caddy

%:
	@echo "Unknown target '$@'. Run 'make help' for available targets." && exit 1