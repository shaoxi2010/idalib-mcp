# idalib MCP Headless

一个基于 `idalib` 的全新 IDA Pro 9.x 无头 MCP supervisor。

本项目在运行时复用 `mrexodia/ida-pro-mcp`，从而保持面向 IDA 的工具接口兼容，同时增加一层轻量 supervisor，用于提供：

- 多个独立 worker 进程，每个打开的数据库/调试会话对应一个 worker；
- 通过 `--ida-home` 在命令行指定 IDA 安装目录；
- 用于列出和关闭实例的简单浏览器 UI；
- `idalib_open`、`idalib_list`、`idalib_close` 等 MCP 管理工具。

## 安装

建议使用项目级虚拟环境，并选择 IDA/idapro 与上游 MCP 包支持的 Python 版本。

```powershell
cd D:\Projects\idalib-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

项目发布后，也可以直接通过 GitHub archive 安装：

```powershell
pip install https://github.com/shaoxi2010/idalib-mcp/archive/refs/heads/master.zip
```

如果当前环境还没有 `idapro` Python 包，请从 IDA 安装目录安装：

```powershell
pip install D:\tools\IDA_PRO_9.1\idalib\python
```

`--ida-home` 会为 worker 进程配置 idalib，不会改写你正常使用的 `%APPDATA%\Hex-Rays\IDA Pro\ida-config.json`。

## 使用 uvx 运行

无需本地克隆仓库，`uvx` 会直接从 GitHub 构建本包并启动无头 server：

```bash
uvx git+https://github.com/shaoxi2010/idalib-mcp.git --ida-home /path/to/IDA_PRO_9.1
```

也可以显式指定可执行文件名：

```bash
uvx --from git+https://github.com/shaoxi2010/idalib-mcp.git idalib-mcp-headless --ida-home /path/to/IDA_PRO_9.1
```

对于由 MCP 客户端自行拉起 stdio server 的场景，在客户端配置中使用同样的命令，例如：

```json
{
  "mcpServers": {
    "idalib-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/shaoxi2010/idalib-mcp.git",
        "idalib-mcp-headless", "--stdio", "--ida-home", "/path/to/IDA_PRO_9.1"
      ]
    }
  }
}
```

注意：`uvx` 每次都会在全新的隔离环境中构建，因此 `pyproject.toml` 已将 `ida-pro-mcp` 依赖固定到已知兼容的上游提交。不要改回滚动更新的 `main` archive：上游 2.x 移除了本项目扩展的 supervisor API（`IdalibSupervisor.__init__(isolated_contexts=...)`、`STDIO_DEFAULT_CONTEXT_ID` 等），会导致启动时报 `TypeError: ... unexpected keyword argument 'isolated_contexts'`。

## MCP 客户端配置

打印通用 MCP 客户端配置片段：

```powershell
idalib-mcp-headless --config --ida-home D:\tools\IDA_PRO_9.1
```

列出支持的客户端目标：

```powershell
idalib-mcp-headless --list-clients
```

为支持的客户端安装项目级 MCP 配置：

```powershell
idalib-mcp-headless --install cursor --scope project --ida-home D:\tools\IDA_PRO_9.1
```

安装 stdio 配置，让 MCP 客户端自行启动无头 server：

```powershell
idalib-mcp-headless --install claude --transport stdio --scope global --ida-home D:\tools\IDA_PRO_9.1
```

在 stdio 模式下，MCP 协议仍然使用 stdin/stdout；实例管理器会作为本地 HTTP sidecar 启动。server 会把 Web UI URL 写到 stderr，例如：

```text
Instance UI: http://127.0.0.1:8745/instances
```

如果配置的端口已被占用，stdio 模式会改用临时端口，并打印实际 URL。

如果你单独运行 server，可以安装 HTTP 配置：

```powershell
idalib-mcp-headless --install vscode --transport streamable-http --scope project --host 127.0.0.1 --port 8745
```

可以用 `--uninstall` 删除配置项，例如：

```powershell
idalib-mcp-headless --uninstall cursor --scope project
```

本项目是无头模式，因此安装器只更新 MCP 客户端配置，不会安装 IDA GUI 插件。

## 运行

```powershell
idalib-mcp-headless --ida-home D:\tools\IDA_PRO_9.1 --host 127.0.0.1 --port 8745 --max-workers 4
```

打开实例管理器：

```text
http://127.0.0.1:8745/instances
```

MCP 客户端连接地址：

```text
http://127.0.0.1:8745/mcp
```

调试器工具继承自上游包，并通过 `dbg` 扩展隐藏。启动 server 时加上 `--unsafe`，然后连接到：

```text
http://127.0.0.1:8745/mcp?ext=dbg
```

每次调用 `idalib_open` 都会创建或复用一个独立 worker 进程。普通上游工具在 supervisor 层支持可选的 `database` 参数，因此可以用 session id、文件名或路径指定目标会话。

## 常用命令

通过 MCP 打开数据库：

```json
{"name":"idalib_open","arguments":{"input_path":"C:\\path\\to\\sample.exe","session_id":"sample-a"}}
```

通过 MCP 列出实例：

```json
{"name":"idalib_list","arguments":{}}
```

通过 MCP 关闭实例：

```json
{"name":"idalib_close","arguments":{"session_id":"sample-a"}}
```

浏览器 UI 使用同一份 supervisor session 表，并在 server 端执行关闭操作。
从浏览器 UI 关闭实例时，可以选择是否先保存 IDB，然后再停止 worker。

## 验证

运行不依赖 IDA 的本地检查：

```powershell
python -m unittest discover -s tests -p "test*.py"
python -m py_compile src\idalib_mcp\config.py src\idalib_mcp\installer.py src\idalib_mcp\worker.py src\idalib_mcp\server.py
```

如需端到端 IDA smoke test，请先在虚拟环境中安装依赖，然后使用上文中的 `--ida-home` 路径启动 server。
