# Private Adapter Boundary

Public OpsPilot provides generic ports, schemas, templates, safe adapters and a synthetic lab.
Environment-specific deployment knowledge belongs in a separate private configuration repository.

```text
Public OpsPilot/                    Private company-opspilot-config/
├── domain                         ├── inventory/
├── application                    ├── target profiles/
├── workflow                       ├── service mappings/
├── capability ports              ├── ticket adapter config/
├── execution ports               └── secret references/
├── generic adapters
└── deployment/{examples,schemas,templates}
```

The private repository may reference internal inventory and APIs, but should still keep credential
values in a secret manager, CI secret or mounted secret file. Public examples must never be edited
to contain real IPs, company domains, usernames, inventory, ticket IDs or service names.

Review private profile changes as code. Schema version, target identity, allowed actions, service
mapping and verification criteria are security-sensitive. Unknown fields and unsafe mappings fail
closed before any connectivity or execution attempt.
