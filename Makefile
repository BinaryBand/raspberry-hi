ANSIBLE_DIR := ansible

# Default Pi host alias (matches ansible/inventory/hosts.ini).
# Override for a specific Pi: HOST=rpi2 make rclone config
HOST ?= rpi

# Derive SSH connection details from inventory — edit hosts.ini, not here.
PI_HOST := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_host',''))" 2>/dev/null)
PI_USER := $(shell cd $(ANSIBLE_DIR) && ansible-inventory --host $(HOST) 2>/dev/null \
	| python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ansible_user',''))" 2>/dev/null)

.PHONY: check ping bw-login bootstrap site mount rclone

check:
	poetry run python scripts/check.py

ping:
	cd $(ANSIBLE_DIR) && ansible raspberry_pi -m ping

bw-login:
	poetry run python scripts/bw-session-refresh.py

bootstrap:
	cd $(ANSIBLE_DIR) && ansible-playbook bootstrap.yml

site: bootstrap
	cd $(ANSIBLE_DIR) && ansible-playbook site.yml

mount:
	poetry run python scripts/pick_storage.py

rclone:
	ssh -t $(PI_USER)@$(PI_HOST) rclone $(filter-out rclone,$(MAKECMDGOALS))

%:
	@:
