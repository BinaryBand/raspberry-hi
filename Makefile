ANSIBLE_DIR := ansible

# Default Pi host alias (matches ansible/inventory/hosts.ini).
# Override for a specific Pi: HOST=rpi2 make rclone config
HOST ?= rpi

# Derive SSH connection details from inventory — edit hosts.ini, not here.
PI_HOST := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_host',''))" 2>/dev/null)
PI_USER := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_user',''))" 2>/dev/null)

.PHONY: check ping bootstrap site mount vault-edit

check:
	poetry run python scripts/check.py

ping:
	cd $(ANSIBLE_DIR) && ansible raspberry_pi -m ping

bootstrap:
	poetry run python scripts/bootstrap.py


vault-edit:
	cd $(ANSIBLE_DIR) && ansible-vault edit group_vars/all/vault.yml

site:
	cd $(ANSIBLE_DIR) && ansible-playbook site.yml

mount:
	poetry run python scripts/pick_storage.py


%:
	@:
