# Project Constitution — linux-hi

## Stack

- Language: Python 3.12
- Framework: None (Ansible + Python tools)
- Test runner: Pytest
- Linter: Ruff, Lizard, ansible-lint, semgrep

## Complexity Rules

- Max function length: 25 lines
- Max cyclomatic complexity: 5
- Max nesting depth: 3
- Max parameters per function: 4
- Prefer early returns over nested conditionals

## Naming Conventions

- Functions: verb_noun snake_case
- Booleans: is_/ has_ / can_ prefix
- Constants: UPPER_SNAKE_CASE
- Classes: PascalCase, noun-first

## Data Flow Architecture

- Ansible owns provisioning and convergence; Python handles interactive pre-provisioning only
- No business logic in CLI entrypoints or Ansible playbooks
- Pydantic models at all data boundaries (registry, host_vars, vault)
- Side effects (vault writes, inventory writes) only in their dedicated seams (`linux_hi/vault/`, `models/ansible/access.py`)

## Readability Standard

- Style reference: Google Python Style Guide
- Every public function has a docstring
- No function does more than one thing
- A junior dev should understand any function in 15 seconds

## Repository Principles

- All infrastructure code is reproducible and idempotent
- All configuration is version-controlled
- Security and privacy are prioritized in all automation
- Documentation is required for all new features and changes
- All code and playbooks are reviewed before merging

## Amendment Process

- Changes to this constitution require consensus among core maintainers
- Amendments must be proposed via pull request and discussed openly
- All amendments are documented in this file with rationale and date
