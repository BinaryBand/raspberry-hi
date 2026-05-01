# Project Specs

<!-- 
TODO: Formalize these points:

	- Ansible is the main, stand-alone project. It's strictly declarative. Python exists soley to modify the declaration files.
	- Lean app agnostic for testing.
	- Define terraform logic and states.
	- Reference enforcers for every statement in the doc.
-->

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
  adapters/              # I/O ports (connection types, prompters, info port)
  cli/                   # Operator-facing entry points
  models/
    ansible/             # Typed access boundaries (registry, host_vars, connection, role_vars)
    inventory/           # Inventory-backed model types (vault secrets schema)
    system/              # System info shapes (blockdevice, mount)
  policy/                # Structural repo checks (run via TestRepoPolicy)
  services/              # Business logic (vault, preflight, mount orchestration)
  storage/               # Storage domain (device discovery, display, rclone)
  utils/                 # Generic helpers (subprocess execution)

tests/
  apps/                  # App-specific contract tests
  e2e/                   # Requires live host
  support/               # Shared test infrastructure (fakes, fixtures, data)
  unit/                  # Fast unit + lint tests
```

## Pre-Provisioning Logic

When a user requests an app (`make <app>`), the Python layer guarantees all dependencies, host variables, and secrets are satisfied before Ansible is invoked.

```mermaid
graph
  subgraph Deps [Dependency Recursion]
    NextDep[Next dependency]
    Recurse([Recursive: Resolve dependencies])
  end

  subgraph Vars [Host Vars]
    NextVar[Next host var]
    PromptVar([Prompt operator])
    VarProvided{Provided?}
    VarError([Error: Missing host var])
  end

  subgraph Vault [Vault Secrets]
    NextSecret[Next vault secret]
    PromptSecret([Prompt operator])
    SecretProvided{Provided?}
    CanGenerate{generate=True?}
    AutoGen[Auto-generate]
    VaultError([Error: Missing Secret])
  end

  %% Phase 1: Dependency Recursion
  Start([Start: Pre-flight]) --> NextDep
  NextDep -- While --> Recurse
  Recurse --> NextDep

  %% Phase 2: Host Vars
  Deps -- Break --> NextVar
  NextVar -- While --> PromptVar
  PromptVar --> VarProvided
  VarProvided -- Yes --> NextVar
  VarProvided -- No --> VarError

  %% Phase 3: Vault Secrets
  Vars -- Break --> NextSecret
  NextSecret -- While --> PromptSecret
  PromptSecret --> SecretProvided
  SecretProvided -- Yes --> NextSecret
  SecretProvided -- No --> CanGenerate
  CanGenerate -- No --> VaultError
  CanGenerate -- Yes --> AutoGen
  AutoGen --> NextSecret

  Vault -- Break --> Ready([Status: Ready])
```

## Input Var Types

### Prompt Types

Each var spec declares a prompt type that determines how the operator is asked for a value:

| Type | Behavior |
| :--- | :--- |
| `text` | Free-text input, value shown as typed |
| `password` | Masked input, value hidden from terminal |
| `path` | Path input with home/env expansion and normalized output |
| `rclone_remote` | Selection from configured remotes stored in vault; prompts for host then path |

### Value Formats

All input types are strings, separated only by format. They need to be in order to 'fit' our file-declarative model.

```mermaid
erDiagram
    RCLONE {
      string host "r/^(?<host>):(?<path>)$/"
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

### Prompt Flow

- **`rclone_remote`** → Select configured remote → Prompt for path → stored as `<host>:<path>`
- **`path`** → Path prompt → `~`/env expansion + normalization → stored as string path
- **`text` / `password`** → Single prompt → stored as plain string

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
| `make lint-repo-policy` | `poetry run python -m linux_hi.cli.repo_policy_check` | `-` |
| `make lint-semgrep` | `poetry run semgrep scan --config rules/ --error` | `<root>/rules/**/*.yml` |
| `make lint-lizard` | `poetry run python -m linux_hi.cli.lizard` | `<root>/config/lint.toml` |
| `make lint-vulture` | `poetry run python -m linux_hi.cli.vulture` | `<root>/config/lint.toml` |

### SSH

| **Command** | Command |
| --- | --- |
| `make ssh` | `poetry run python -m linux_hi.cli.rclone` |

### Debug

| **Command** | Command |
| --- | --- |
| `make test` | `poetry run pytest tests/ -v` |
| `make test-e2e` | `HOST=$(HOST) poetry run pytest tests/e2e/ -v -m e2e -s` |
| `make check` | `poetry run python -m linux_hi.cli.check` |
| `make ping` | \`ansible devices -m ping -i \$(INV) |
