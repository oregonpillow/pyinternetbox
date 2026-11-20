"""The MCP server (`ibox mcp`) and its metrics collector (`ibox mcp-exporter`).

The server needs the optional `mcp` dependency: pip install "pyinternetbox[mcp]". The collector and the metrics sender
don't, so nothing here imports it: import internetbox_client.mcp_server.server for the server.
"""
