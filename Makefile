ANSIBLE_DIR := ansible

# Default Pi host alias (matches ansible/inventory/hosts.ini).
# Override for a specific Pi: HOST=rpi2 make site
HOST ?= rpi

# Derive SSH connection details from inventory — edit hosts.ini, not here.
PI_HOST := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_host',''))" 2>/dev/null)
PI_USER := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_user',''))" 2>/dev/null)
PI_KEY  := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_ssh_private_key_file',''))" 2>/dev/null)

.PHONY: check ping bootstrap site mount vault-edit


check:
	poetry run python ./scripts/check.py


ping:
	ansible raspberry_pi -m ping -i ansible/inventory/hosts.ini



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
