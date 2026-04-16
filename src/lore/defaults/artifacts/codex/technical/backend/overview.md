---
id: example-tech-backend
title: Backend
summary: Command dispatch lifecycle, domain organisation, error output conventions,
  and exit codes. Start here before adding or modifying any backend code.
---

# Backend

_One paragraph. What kind of backend is this (CLI, HTTP API, worker, etc.)? What framework? What is the entry point?_

## Request / Command Dispatch Lifecycle

_Show the path a request or command takes from entry point to output. Use a code-style diagram._

```
User runs: {example command or request}

  → {entry-point file}       {description}
      → {router/group}       {description}
          → {handler}        {description}
              → validate     {what is validated}
              → {db/service} {what is called}
              → output       {what is returned}
```

_Every command/endpoint should follow this pattern. Describe it once here; refer to it in specific command docs._

## Domain Organisation

_How is the backend code organised? One module per domain? By layer?_

```
{source-dir}/
├── {domain-a}/    {commands or routes in this domain}
└── {domain-b}/    {commands or routes in this domain}
```

_Describe the convention for adding a new domain._

## Error Output Conventions

- **Errors go to {stderr/response body}.** _Convention for surfacing errors._
- **Results go to {stdout/response body}.** _Convention for success output._
- **No tracebacks in production output.** _Catch specific exceptions; let unexpected ones propagate to the top-level handler._

## Exit Codes / Status Codes

| Code | Meaning | When |
|------|---------|------|
| {0 / 200} | Success | _Command completed without error_ |
| {1 / 400} | Not found or invalid input | _Description_ |
| {2 / 409} | Conflict | _Description_ |

_Add rows for all codes your application returns. Remove rows that don't apply._
