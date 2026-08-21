# Agent Infrastructure Observability

MCP SDK 2.0 propagates OpenTelemetry context through request metadata. OpsPilot spans connect MCP
calls to capability work. Attributes are bounded: capability/tool names and correlation IDs are
safe; tokens, prompts, raw logs, and evidence bodies are prohibited.
