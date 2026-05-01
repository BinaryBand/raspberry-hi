# Project Specs

## System Architecture

```mermaid
flowchart LR
  subgraph STAT [Static Codebase]
      VP[.vault-password]
      R[registry.yml]
      PB[playbooks]
  end

  subgraph VARS [Generated State]
    subgraph INV [Inventory]
      H[hosts.yml]
      HV[host_vars/]
    end
    VAR[vars.yml]
    V[vault.yml]
  end

  R --> PY[Python CLI / Pydantic] --> VAR
  PY <--> INV
  PY <--> V
  STAT --> A[Ansible Engine]
  VARS --> A
```

### Architectural Boundaries

- **Python** handles interactive data gathering and compiles the registry into Ansible variables (`make generate-apps`).
- **Ansible** handles system convergence. Python must never call ansible-playbook.

## Scaffolding

```text
ansible/
  registry.yml           # Single source of truth for all app metadata
  apps/<app>/            # Ansible role per app
    defaults/main.yml    # Hand-authored defaults (nulls for required vars ONLY)
    tasks/main.yml       # Standardized 4-step task pattern
    playbook.yml         # Committed; import_playbook chain + pre_tasks
  roles/                 # Shared roles (service_adapter, rclone, podman)
  group_vars/all/
    vars.yml             # GENERATED/HAND-EDITABLE — shared non-secret vars (names, ports, etc.)
    vault.yml            # GENERATED — Encrypted secrets (ansible-vault)
  inventory/             # GENERATED/HAND-EDITABLE — Managed via `make config-hosts-*`

linux_hi/
  cli/                   # Operator-facing entry points
  policy/                # Structural repo checks (run via TestRepoPolicy)
  models/ansible/        # Typed access boundaries (registry, host_vars)

tests/                   # Fast unit + lint tests; e2e/ requires live host
```

## Pre-Provisioning Logic

When a user requests an app (`make <app>`), the Python layer guarantees all dependencies, host variables, and secrets are satisfied before Ansible is invoked.

```mermaid
graph
  Start([Start: Pre-flight]) --> NextDep[Get next dependency]
  
  %% Phase 1: Dependency Recursion
  NextDep --> Recurse([Recursive Call: Resolve Dependency])
  Recurse --> MoreDeps{More dependencies?}
  MoreDeps -- Yes --> NextDep
  
  %% Phase 2: Parameter Resolution
  MoreDeps -- No --> NextParam[Get next parameter]
  
  NextParam --> Known{Value already available?}
  
  %% Variable Acquisition
  Known -- No --> Request([Request input])
  Request --> Provided{Provided?}
  
  Provided -- No --> HasDefault{Has default fallback?}
  HasDefault -- Yes --> IsSensitive
  
  %% Storage & Security
  Provided -- Yes --> IsSensitive{Is value sensitive?}
  
  IsSensitive -- Yes --> Vault[Store in Vault]
  IsSensitive -- No --> Inventory[Store in Inventory]
  
  %% Parameter Loop-back
  Vault --> MoreParams{More parameters?}
  Inventory --> MoreParams
  Known -- Yes --> MoreParams
  
  MoreParams -- Yes --> NextParam

  HasDefault -- No --> Error([Status: Error])
  MoreParams -- No --> Ready([Status: Ready])
```

## Input Var Types

```mermaid
erDiagram
    RCLONE {
      string host "regex: r/^(?<host>):(?<path>)$/"
      string path "named capture: path"
    }
    PATH {
      string path "regex: r/^(?<path>)$/"
    }
    STRING {
      string value "str"
    }

    RCLONE ||--|| PATH : "is a"
    PATH ||--|| STRING : "is a"

```

## Commands

### Edit Configs

Pattern: config-&lt;target&gt;-&lt;action&gt; \[VARIABLES\]

#### Rclone

| Target | Variables | Command |
| :--- | :---: | ---: |
| `make config-rclone` | `-` | `rclone config --config config/rclone.conf` |

#### Hosts

| Target | Variables | Command |
| :--- | :---: | ---: |
| `make config-hosts-add` | `<name:str> <address:str> <secret:path>` | `poetry run python -m linux_hi.cli.hosts add --name <name> --address <address> --secret <secret>` |
| `make config-hosts-remove` | `<name:str>` | `poetry run python -m linux_hi.cli.hosts remove --name <name>` |
| `make config-hosts-list` | `-` | `poetry run python -m linux_hi.cli.hosts list` |

#### Vault

| Target | Variables | Command |
| :--- | :---: | ---: |
| `make config-vault-add` | `<name:str>` | `poetry run python -m linux_hi.cli.vault add --name <name>` |
| `make config-vault-remove` | `<name:str>` | `poetry run python -m linux_hi.cli.vault remove --name <name>` |
| `make config-vault-list` | `-` | `poetry run python -m linux_hi.cli.vault list` |

### Lint

Run `make lint` to run all of the following:

| **Command** | Command | Config(s) |
| --- | --- | --- |
| `make lint-ansible` | `poetry run ansible-lint ansible` | `<root>/ansible/ansible.cfg` |
| `make lint-check` | `poetry run ruff check` | `<root>/pyproject.toml` |
| `make lint-format` | `poetry run ruff format --check` | `<root>/pyproject.toml` |
| `make lint-ty` | `poetry run ty check` | `<root>/pyproject.toml` |
| `make lint-checkmake` | `poetry run mbake format --check Makefile` | `-` |
| `make lint-cpd` | `npx jscpd --config .jscpd.json .` | `<root>/.jscpd.json` |
| `make lint-repo-policy` | `poetry run python -m linux_hi.cli.linters.repo_policy_check` | `-` |
| `make lint-semgrep` | `poetry run semgrep scan --config rules/ --error` | `<root>/rules/**/*.yml` |
| `make lint-lizard` | `poetry run python -m linux_hi.cli.linters.lizard` | `<root>/config/lint.toml` |
| `make lint-vulture` | `poetry run python -m linux_hi.cli.linters.vulture` | `<root>/config/lint.toml` |

### SSH

| **Command** | Command |
| --- | --- |
| `make ssh` | `ssh -i <key> <user>@<host> -p <port>` |

### Debug

| **Command** | Command |
| --- | --- |
| `make test` | `poetry run pytest tests/ -v` |
| `make test-e2e` | `HOST=$(HOST) poetry run pytest tests/e2e/ -v -m e2e -s` |
| `make check` | `poetry run python -m linux_hi.cli.check` |
| `make ping` | \`ansible devices -m ping -i \$(INV) |
