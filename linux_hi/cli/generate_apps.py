"""Generate per-app Ansible playbooks from ansible/registry.yml."""

from __future__ import annotations

import sys

from models import ANSIBLE_DATA

_BECOME_ASSERT = """\
  pre_tasks:
    - name: Verify become password is configured for this host
      ansible.builtin.assert:
        that: (become_passwords | default({})).get(inventory_hostname, '') | length > 0
        fail_msg: >-
          become password not set for '{{ inventory_hostname }}'.
          Run 'make bootstrap' to add it.
      tags: [always]
"""


def _render_playbook(app: str, dependencies: list[str]) -> str:
    parts: list[str] = ["---"]
    for dep in dependencies:
        parts.append(f"- name: Import {dep} playbook")
        parts.append(f"  import_playbook: ../{dep}/playbook.yml")
        parts.append("")
    parts.append(f"- name: Provision {app}")
    parts.append("  hosts: devices")
    parts.append("  gather_facts: true")
    parts.append("")
    parts.append(_BECOME_ASSERT)
    parts.append("  roles:")
    parts.append(f"    - role: {app}")
    parts.append("")
    return "\n".join(parts)


def main() -> None:
    registry = ANSIBLE_DATA.load_app_registry()
    apps_dir = ANSIBLE_DATA.ansible_dir / "apps"
    generated: list[str] = []

    for app, entry in registry.items():
        playbook_path = apps_dir / app / "playbook.yml"
        if not playbook_path.parent.is_dir():
            sys.exit(f"  [FAIL]  No app directory for '{app}': {playbook_path.parent}")
        content = _render_playbook(app, entry.dependencies)
        playbook_path.write_text(content, encoding="utf-8")
        generated.append(app)

    print(f"  [OK  ]  Generated playbooks for: {', '.join(generated)}")


if __name__ == "__main__":
    main()
