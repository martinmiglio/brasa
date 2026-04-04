@AGENTS.md

## Claude-specific

- Use `uv` for all Python operations (never pip/pipx)
- Use `bunx` over `npx` for JS tools
- Do not add Claude/Anthropic as commit authors
- Do not address formatting warnings — handled by pre-commit
- Place all imports at top level
- Keep `__init__.py` files empty unless they need content
