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
	poetry run python ./scripts/check.py


ping:
	ansible raspberry_pi -m ping -i ansible/inventory/hosts.ini

	poetry run python ./scripts/bootstrap.py


ssh:
	ssh -i config/.ed25519 $$(awk '/^rpi / {for(i=1;i<=NF;i++) if($$i ~ /^ansible_host=/) {split($$i,a,"="); host=a[2]}} /^ansible_user=/ {split($$0,a,"="); user=a[2]} END {print user "@" host}' ansible/inventory/hosts.ini) -p 22


vault-edit:
	ANSIBLE_CONFIG=ansible/ansible.cfg ansible-vault edit ansible/group_vars/all/vault.yml --vault-password-file ansible/.vault-password


	sleep 1
	ansible-playbook ansible/site.yml -i ansible/inventory/hosts.ini --vault-password-file ansible/.vault-password

	poetry run python ./scripts/pick_storage.py


%:
	@:
