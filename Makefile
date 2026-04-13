ANSIBLE_DIR := ansible

# Default Pi host alias (matches ansible/inventory/hosts.ini).
# Override for a specific Pi: HOST=rpi2 make site
HOST ?= rpi

# Single inventory call — splits host/user/key into three Make variables.
# No ANSIBLE_CONFIG: we only need inventory vars (hosts.ini + host_vars/), not group_vars or vault.
# python3 returns '' on empty/failed output rather than crashing.
# Values must not contain spaces (safe for IPs, usernames, and file paths).
_INV    := $(shell ansible-inventory -i $(ANSIBLE_DIR)/inventory/hosts.ini --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); \
	  print(d.get('ansible_host',''), d.get('ansible_user',''), d.get('ansible_ssh_private_key_file',''))" \
	2>/dev/null)
PI_HOST := $(word 1,$(_INV))
PI_USER := $(word 2,$(_INV))
PI_KEY  := $(word 3,$(_INV))

.PHONY: help check ping bootstrap site mount vault-edit ssh add-hostkey


help:
	@echo "Usage: make [HOST=<alias>] <target>"
	@echo ""
	@echo "  bootstrap     First-time setup: vault password + encrypt credentials"
	@echo "  check         Validate prerequisites (vault file, Pi reachability)"
	@echo "  site          Provision the Pi (runs all roles)"
	@echo "  site-local    Provision against localhost (dev/testing)"
	@echo "  mount         Interactive: pick and mount external storage"
	@echo "  vault-edit    Edit encrypted secrets in \$$EDITOR"
	@echo "  ssh           Open a shell on the Pi"
	@echo "  ping          Test Ansible connectivity"
	@echo "  add-hostkey   Trust the Pi's SSH host key (run before first site)"
	@echo ""
	@echo "  HOST defaults to 'rpi'; override with: HOST=rpi2 make site"

check:
	poetry run python ./scripts/check.py

ping:
	ansible raspberry_pi -m ping -i ansible/inventory/hosts.ini

add-hostkey:
	ssh-keyscan -H $(PI_HOST) >> ~/.ssh/known_hosts

ssh:
	ssh -i $(PI_KEY) $(PI_USER)@$(PI_HOST) -p 22

vault-edit:
	EDITOR="$${EDITOR:-nano}" ANSIBLE_CONFIG=ansible/ansible.cfg ansible-vault edit ansible/group_vars/all/vault.yml --vault-password-file $(CURDIR)/ansible/.vault-password

bootstrap:
	poetry run python ./scripts/bootstrap.py

mount:
	poetry run python ./scripts/pick_storage.py

site:
	ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/site.yml -i ansible/inventory/hosts.ini --vault-password-file $(CURDIR)/ansible/.vault-password

site-local:
	ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/site.yml -i ansible/inventory/hosts-local.ini --vault-password-file $(CURDIR)/ansible/.vault-password

%:
	@:
