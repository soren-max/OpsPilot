# Deployment Knowledge as Configuration

**Question:** Why model legacy deployment knowledge as strict configuration?

**Answer:** Existing runbooks contain valuable but dangerous details: host mappings, service-manager
choices, script identifiers, health criteria and privilege needs. Versioned, reviewed schemas turn
that knowledge into bounded inputs. Unknown fields, unsafe paths, duplicate targets and operations
outside the allowlist fail before execution, while application code remains environment-neutral.
