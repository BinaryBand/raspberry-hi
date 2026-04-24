"""Entrypoint: generate per-app Ansible playbooks from ansible/registry.yml."""

from linux_hi.cli.generate_apps import main

if __name__ == "__main__":
    main()
