---
id: example-security-model
title: Security Model
summary: Authentication model, authorization rules, sensitive data inventory, external
  exposure surface, and agent-specific security rules. Read before modifying any auth,
  data access, or input handling code.
---

# Security Model

## Authentication

_How is identity established? What mechanism (session tokens, JWTs, API keys, none for local tools)?_

> Example: This is a local CLI tool. There is no authentication — the operating system user is implicitly trusted. If multi-user access is added in the future, see ADR-XXX.

## Authorization

_Who can do what? Are there roles? What is the access control model?_

> Example: Single-user tool. All operations are permitted to the local user. No role separation.

| Role / Actor | Permitted operations | Denied operations |
|-------------|---------------------|------------------|
| _e.g. Authenticated user_ | _Description_ | _Description_ |
| _e.g. Unauthenticated_ | _e.g. None_ | _Everything_ |

## Sensitive Data Inventory

_What data in this system is sensitive? Where is it stored? Who has access?_

| Data | Classification | Where stored | Access |
|------|---------------|-------------|--------|
| _e.g. User email_ | _PII_ | _Database, logs_ | _Local user only_ |
| _e.g. API keys_ | _Credential_ | _Environment variable, never disk_ | _Process only_ |
| _e.g. Task content_ | _User data_ | _Local database_ | _Local user only_ |

## External Exposure Surface

_What does this system expose externally? What ports, endpoints, or interfaces are accessible from outside the process?_

> Example: No external exposure. Local CLI only. No listening ports, no HTTP server, no daemon.

## Agent-Specific Rules

_Rules that AI agents working on this codebase must follow. These prevent common security mistakes._

- **Never log credentials.** Environment variables containing keys or tokens must never appear in log output or error messages.
- **Never hardcode secrets.** All credentials go in environment variables. See `constraints/` for the variable names.
- **Validate all external input at the boundary.** User input, file content read from disk, and API responses must be validated before use.
- **{Project-specific rule}:** _Description._

## Known Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| _e.g. SQL injection_ | _Parameterised queries everywhere. No string concatenation in queries._ |
| _e.g. Path traversal_ | _File paths from user input are resolved and validated before use._ |
| _e.g. Dependency vulnerabilities_ | _`uv audit` run in CI on every PR._ |
