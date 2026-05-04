# Adding a new app

This checklist shows the minimal steps to add a new app to the repository.

1. Add an entry under `ansible/registry.yml` with:
   - `service_type`, `service_name`, `image`, `port` (if containerized)
   - `preflight_vars` for any required filesystem paths (type: `path`)
   - `vault_secrets` for credentials

2. Add app role under `ansible/apps/<app>/` with:
   - `defaults/main.yml` for defaults
   - `tasks/main.yml` implementing: ensure directories, templates, pull image, prepare service_adapter, write_container/use service_adapter
   - `templates/` and `files/` as needed

3. Ensure rootless Podman safety:
   - Do NOT use the `:U` volume flag. Instead, ensure files are created with correct ownership and run a `podman unshare chown -R` step when necessary.

4. Add tests:
   - Add unit tests in `tests/apps/` covering role defaults and registry integration.

5. Update docs:
   - Add any architecture notes to `docs/ARCHITECTURE.md` and reference docs/ADDING_AN_APP.md where helpful.

6. Run checks:
   - `poetry run semgrep scan --config rules/ --error`
   - `poetry run pytest tests/unit -q`

Follow repository conventions (see `docs/ARCHITECTURE.md`) for naming, ports, and shared vars.
