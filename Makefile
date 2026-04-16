ANSIBLE_DIR := ansible

# Default host alias (matches ansible/inventory/hosts.ini).
# Override for a specific host: HOST=rpi2 make site
HOST ?= rpi

# Single inventory call — splits host/user/key into three Make variables.
# No ANSIBLE_CONFIG: we only need inventory vars (hosts.ini + host_vars/), not group_vars or vault.
# python3 returns '' on empty/failed output rather than crashing.
# Values must not contain spaces (safe for IPs, usernames, and file paths).
_INV        := $(shell ansible-inventory -i $(ANSIBLE_DIR)/inventory/hosts.ini --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); \
	  print(d.get('ansible_host',''), d.get('ansible_user',''), d.get('ansible_ssh_private_key_file',''))" \
	2>/dev/null)
REMOTE_HOST := $(word 1,$(_INV))
REMOTE_USER := $(word 2,$(_INV))
REMOTE_KEY  := $(word 3,$(_INV))

# Shared Ansible flags — avoids repeating paths across targets.
ANSIBLE_CFG  := $(CURDIR)/ansible/ansible.cfg
VAULT_PASS   := $(CURDIR)/ansible/.vault-password
INV          := ansible/inventory/hosts.ini
INV_LOCAL    := ansible/inventory/hosts-local.ini
PLAYBOOK     := ansible/site.yml
ANSIBLE_PLAY := ANSIBLE_CONFIG=$(ANSIBLE_CFG) ansible-playbook $(PLAYBOOK) -i $(INV) --vault-password-file $(VAULT_PASS) --limit $(HOST)

# Make project packages importable without sys.path manipulation in scripts.
export PYTHONPATH := $(CURDIR):$(CURDIR)/scripts

.PHONY: help check ping bootstrap site site-local mount vault-edit ssh add-hostkey lint cpd test test-roles test-e2e status logs baikal minio


help:
	@echo "Usage: make [HOST=<alias>] <target>"
	@echo ""
	@echo "  bootstrap     First-time setup: vault password + encrypt credentials"
	@echo "  check         Validate prerequisites (vault file, Pi reachability)"
	@echo "  lint          Run ruff linter over scripts/ and models/"
	@echo "  cpd           Check for copy-paste duplication (jscpd, threshold 3%)"
	@echo "  test          Run unit + stub tests (no infra needed)"
	@echo "  test-roles    Run Ansible role tests in Docker (requires Docker)"
	@echo "  test-e2e      Run live Pi tests (requires Pi up, HOST=rpi)"
	@echo "  site          Provision the Pi (runs all roles)"
	@echo "  site-local    Provision against localhost (dev/testing)"
	@echo "  minio         Setup MinIO storage"
	@echo "  baikal        Provision Baikal CalDAV/CardDAV server"
	@echo "  mount         Interactive: pick and mount external storage"
	@echo "  vault-edit    Edit encrypted secrets in \$$EDITOR"
	@echo "  ssh           Open a shell on the Pi"
	@echo "  ping          Test Ansible connectivity"
	@echo "  add-hostkey   Trust the Pi's SSH host key (run before first site)"
	@echo ""
	@echo "  status        Show MinIO service status on the Pi"
	@echo "  logs          Tail MinIO logs from the Pi"
	@echo ""
	@echo "  HOST defaults to 'rpi'; override with: HOST=rpi2 make site"

check:
	poetry run python ./scripts/check.py

lint:
	poetry run ruff check scripts/ models/ tests/

cpd:
	npx jscpd .

test:
	poetry run pytest tests/ -v

test-roles:
	cd ansible/roles/storage && poetry run molecule test

test-e2e:
	HOST=$(HOST) poetry run pytest tests/e2e/ -v -m e2e

ping:
	ansible devices -m ping -i $(INV) || true

add-hostkey:
	ssh-keyscan -H $(REMOTE_HOST) >> ~/.ssh/known_hosts

ssh:
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) -p 22

vault-edit:
	EDITOR="$${EDITOR:-nano}" ANSIBLE_CONFIG=$(ANSIBLE_CFG) ansible-vault edit ansible/group_vars/all/vault.yml --vault-password-file $(VAULT_PASS)

bootstrap:
	poetry run python ./scripts/bootstrap.py

mount:
	HOST=$(HOST) poetry run python ./scripts/pick_storage.py

minio:
	HOST=$(HOST) poetry run python ./scripts/setup_minio_storage.py
	$(ANSIBLE_PLAY) --tags minio

baikal:
	$(ANSIBLE_PLAY) --tags baikal

status:
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) "systemctl --user status minio --no-pager"

logs:
	ssh -i $(REMOTE_KEY) $(REMOTE_USER)@$(REMOTE_HOST) "journalctl --user -u minio -n 50 --no-pager"

site:
	$(ANSIBLE_PLAY) --skip-tags apps

site-local:
	ANSIBLE_CONFIG=$(ANSIBLE_CFG) ansible-playbook $(PLAYBOOK) -i $(INV_LOCAL) --vault-password-file $(VAULT_PASS) --skip-tags apps

%:
	@echo "Unknown target '$@'. Run 'make help' for available targets." && exit 1
