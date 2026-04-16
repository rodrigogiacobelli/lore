---
id: example-integrations
title: Integrations
summary: 'All external systems this project interacts with: purpose, protocol, auth
  method, failure behaviour, and what is off-limits to modify. Agents must read this
  before touching any code that calls an external system.'
---

# Integrations

_One section per external system. External systems include: APIs consumed, services depended on, third-party tools, message queues, external databases, and auth providers._

> If this project has no external integrations, replace this file's content with "This project has no external integrations." Retain the file as a placeholder.

---

## {Integration Name — e.g. SendGrid, Stripe, GitHub API}

**Purpose:** _What does this integration do for the project? One sentence._

**Direction:** _Inbound (they call us) | Outbound (we call them) | Both_

**Protocol:** _e.g. REST/JSON over HTTPS, gRPC, Webhooks, SMTP_

**Authentication:** _e.g. API key in Authorization header, OAuth2 client credentials, HMAC signature on webhook payload_

**Configuration:** _Where are credentials stored? What environment variables? Link to secrets management._

| Variable | Description |
|----------|-------------|
| `{ENV_VAR_1}` | _Description_ |
| `{ENV_VAR_2}` | _Description_ |

**Failure behaviour:** _What happens when this integration is unavailable? Does the feature degrade gracefully or fail hard? What is the retry policy?_

**Off-limits:** _What must agents never do with this integration? e.g. "Never call the production API from tests — use the sandbox.", "Never store raw webhook payloads to disk."_

**Rate limits:** _Any known rate limits that constrain usage patterns._

---

## {Integration Name 2}

_Repeat the structure above for each additional integration._
