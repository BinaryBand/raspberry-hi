from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import subprocess

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

DOCUMENTATION = r"""
lookup: bitwarden
short_description: Fetch a secret from the Bitwarden personal vault
description:
  - Calls the bw CLI to retrieve a login item by name from the personal vault.
  - Reads the active session token from ansible/.bw-session or the BW_SESSION env var.
options:
  _terms:
    description: Name of the Bitwarden item to look up.
    required: true
  field:
    description: Field to return — 'password' (default) or 'username'.
    default: password
  fail_if_missing:
    description: Raise an error if the item is not found.
    default: true
"""


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        if not terms:
            raise AnsibleError("bitwarden lookup requires an item name")

        name = terms[0]
        field = kwargs.get("field", "password")
        fail_if_missing = kwargs.get("fail_if_missing", True)

        session = self._get_session(variables)

        try:
            result = subprocess.run(
                ["bw", "get", "item", name],
                capture_output=True,
                text=True,
                env={**os.environ, "BW_SESSION": session},
            )
        except FileNotFoundError:
            raise AnsibleError(
                "bw CLI not found. Install with: brew install bitwarden-cli"
            )

        if result.returncode != 0:
            if fail_if_missing:
                raise AnsibleError(
                    "bw get item '{}' failed: {}".format(name, result.stderr.strip())
                )
            return []

        try:
            item = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AnsibleError("bitwarden: failed to parse bw output: {}".format(exc))

        value = self._extract_field(item, field)

        if value is None:
            if fail_if_missing:
                raise AnsibleError(
                    "bitwarden: field '{}' not found in item '{}'".format(field, name)
                )
            return []

        return [value]

    def _get_session(self, variables):
        session = os.environ.get("BW_SESSION", "")
        if session:
            return session

        playbook_dir = (variables or {}).get("playbook_dir", os.getcwd())
        session_file = os.path.join(playbook_dir, ".bw-session")

        if os.path.isfile(session_file):
            with open(session_file) as fh:
                session = fh.read().strip()

        if not session:
            raise AnsibleError(
                "No active Bitwarden session. Run 'make bw-login' first."
            )

        return session

    def _extract_field(self, item, field):
        login = item.get("login") or {}
        if field == "password":
            return login.get("password")
        if field == "username":
            return login.get("username")
        for custom in item.get("fields") or []:
            if custom.get("name") == field:
                return custom.get("value")
        return None
