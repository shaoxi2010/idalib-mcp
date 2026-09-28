# idalib MCP Headless

Fresh headless MCP supervisor for IDA Pro 9.x through `idalib`.

This project keeps the IDA-facing tool surface compatible with `mrexodia/ida-pro-mcp` by using that package at runtime, then adds a thin supervisor layer for:

- multiple independent worker processes, one per open database/debug session;
- command-line IDA installation selection with `--ida-home`;
- a simple browser UI for listing and closing instances;
- MCP management tools such as `idalib_open`, `idalib_list`, and `idalib_close`.

## Install

Use a project virtual environment with a Python supported by IDA/idapro and the upstream MCP package.

```powershell
cd D:\Projects\idalib-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

After the project is published, installation can use the GitHub archive directly:

```powershell
pip install https://github.com/shaoxi2010/idalib-mcp/archive/refs/heads/master.zip
```

If the `idapro` Python package is not already available, install it from your IDA installation:

```powershell
pip install D:\tools\IDA_PRO_9.1\idalib\python
```

`--ida-home` configures idalib for the worker process without rewriting your normal `%APPDATA%\Hex-Rays\IDA Pro\ida-config.json`.

## Run with uvx

No local checkout is needed. `uvx` builds this package straight from GitHub and launches the headless server, always tracking the latest `master`:

```bash
uvx git+https://github.com/shaoxi2010/idalib-mcp.git --ida-home /path/to/IDA_PRO_9.1
```

Or name the executable explicitly:

```bash
uvx --from git+https://github.com/shaoxi2010/idalib-mcp.git idalib-mcp-headless --ida-home /path/to/IDA_PRO_9.1
```

`uv` caches the repository and the built wheel, so a warm launch only pays a small round trip to check for new commits (~2s measured).

For MCP clients that spawn a stdio server themselves, use the same command in the client config and raise the per-server timeout, for example (Cline, `cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "idalib-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/shaoxi2010/idalib-mcp.git",
        "idalib-mcp-headless", "--stdio", "--ida-home", "/opt/ida-pro-9.3"
      ],
      "timeout": 600
    }
  }
}
```

Notes:

- Always pass `--ida-home`. Without it the worker trusts the global `~/.idapro/ida-config.json`; an empty or stale `ida-install-dir` there makes every worker fail. Verify the file contains `{"Paths": {"ida-install-dir": "/path/to/IDA"}}`.
- IDA auto-analysis can easily run past 60s, so keep `"timeout"` generous (600s is a sane default).
- `--ida-home` isolates the worker's `HOME` into a temp config root; the worker copies your `idapro.hexlic` license and `ida.reg` into it, so licensing keeps working.
- Troubleshooting slow starts: the first launch after a push re-downloads and rebuilds, and a flaky GitHub link can stretch that badly (minutes). If a start ever trips the client timeout, just retry once; if it keeps happening, pin a commit for stability (`--from "git+https://github.com/shaoxi2010/idalib-mcp.git@<commit>"`, serve everything from uv's cache, bump the commit when you update) or switch to `uv tool install git+https://github.com/shaoxi2010/idalib-mcp.git` and run `uv tool upgrade idalib-mcp-headless` to pick up updates.

Note: `uvx` builds in a fresh isolated environment every time, so the `ida-pro-mcp` dependency is pinned to a known-compatible upstream commit in `pyproject.toml`. Do not point it back at the rolling `main` archive: upstream 2.x removed the supervisor API (`IdalibSupervisor.__init__(isolated_contexts=...)`, `STDIO_DEFAULT_CONTEXT_ID`, ...) that this project extends, which fails at startup with `TypeError: ... unexpected keyword argument 'isolated_contexts'`.

## MCP Client Setup

Print generic MCP client snippets:

```powershell
idalib-mcp-headless --config --ida-home D:\tools\IDA_PRO_9.1
```

List supported client targets:

```powershell
idalib-mcp-headless --list-clients
```

Install project-level MCP config for a supported client:

```powershell
idalib-mcp-headless --install cursor --scope project --ida-home D:\tools\IDA_PRO_9.1
```

Install a stdio config that lets the MCP client launch the headless server itself:

```powershell
idalib-mcp-headless --install claude --transport stdio --scope global --ida-home D:\tools\IDA_PRO_9.1
```

In stdio mode the MCP protocol still uses stdin/stdout, and the instance manager is started as a local HTTP sidecar. The server writes the web UI URL to stderr, for example:

```text
Instance UI: http://127.0.0.1:8745/instances
```

If the configured port is already in use, stdio mode retries with an ephemeral port and prints the actual URL.

Install an HTTP config when you run the server separately:

```powershell
idalib-mcp-headless --install vscode --transport streamable-http --scope project --host 127.0.0.1 --port 8745
```

Remove config entries with `--uninstall`, for example:

```powershell
idalib-mcp-headless --uninstall cursor --scope project
```

This project is headless, so the installer only updates MCP client configuration. There is no IDA GUI plugin to install.

## Run

```powershell
idalib-mcp-headless --ida-home D:\tools\IDA_PRO_9.1 --host 127.0.0.1 --port 8745 --max-workers 4
```

Open the instance manager at:

```text
http://127.0.0.1:8745/instances
```

Connect MCP clients to:

```text
http://127.0.0.1:8745/mcp
```

Debugger tools are inherited from the upstream package and are hidden behind the `dbg` extension. Start the server with `--unsafe`, then connect to:

```text
http://127.0.0.1:8745/mcp?ext=dbg
```

Each `idalib_open` call creates or reuses a distinct worker process. Normal upstream tools receive an optional `database` argument at the supervisor layer so calls can target a specific session by session id, filename, or path.

## Useful Commands

Open a database through MCP:

```json
{"name":"idalib_open","arguments":{"input_path":"C:\\path\\to\\sample.exe","session_id":"sample-a"}}
```

List instances through MCP:

```json
{"name":"idalib_list","arguments":{}}
```

Close an instance through MCP:

```json
{"name":"idalib_close","arguments":{"session_id":"sample-a"}}
```

The browser UI uses the same supervisor session table and calls the close operation server-side.
When closing an instance from the browser UI, choose whether to save the IDB before the worker is stopped.

## Validation

Run the dependency-free local checks:

```powershell
python -m unittest discover -s tests -p "test*.py"
python -m py_compile src\idalib_mcp\config.py src\idalib_mcp\installer.py src\idalib_mcp\worker.py src\idalib_mcp\server.py
```

For an end-to-end IDA smoke test, install the dependencies in a virtual environment and start the server with the `--ida-home` path shown above.
