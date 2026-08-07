# Job Intelligence Agent - MCP Server

Wraps `agent/` for any MCP client (Claude Desktop, MCP Inspector, Cowork).
Pure glue - no reimplementation of pipeline logic.

## SDK note

Installed `mcp` package is 2.0.0, which renamed `FastMCP` to `MCPServer` and
moved it from `mcp.server.fastmcp` to `mcp.server.mcpserver`. Most
tutorials/docs (including cached skill references) still show the old path -
it does not exist in this version and importing it fails outright.
`server.py` uses the correct `from mcp.server.mcpserver import MCPServer`.

Also note: `@server.tool()` does not take a `read_only_hint` kwarg directly -
verified by inspecting the real signature before writing this (it only
accepts `annotations: ToolAnnotations | None`). Use
`annotations=ToolAnnotations(read_only_hint=True)` instead.

## Tools

- `job_intel_search_and_brief` - full pipeline (Search/Extract/Match/Brief-writer). Costs Anthropic + Apify usage.
- `job_intel_search_postings` - raw LinkedIn search only, no LLM calls.
- `job_intel_get_profile` - read-only passthrough of the loaded profile.

Verified locally (2026-08-06): server registers all 3 tools with correct
`read_only_hint` annotations, and `job_intel_get_profile` was called through
the actual MCP `call_tool` dispatch path (not just the raw Python function)
and returned the real profile correctly.

## Claude Desktop config

**Important, learned the hard way on the Ops Intel Agent's MCP server and
confirmed to apply here too:** Claude Desktop does NOT honor a `cwd` key in
the server config. Use `PYTHONPATH` in `env` instead, pointing at this
repo's root, or `python -m mcp_server.server` will fail with
`ModuleNotFoundError: No module named 'mcp_server'`.

```json
{
  "mcpServers": {
    "job-intelligence-agent": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "C:\\Users\\dream\\Job-Agent",
        "ANTHROPIC_API_KEY": "<same key as .env>",
        "APIFY_TOKEN": "<same token as .env>",
        "APIFY_ACTOR_ID": "curious_coder/linkedin-jobs-scraper",
        "PROFILE_PATH": "C:\\Users\\dream\\Job-Agent\\agent\\profile\\profile.json"
      }
    }
  }
}
```

Not yet installed into Claude Desktop or tested via MCP Inspector - that's
the remaining verification step, same as the Ops Intel Agent's MCP server
went through before being marked fully done.
