"""Expose the deployed FinAgent analysis client as a Codex MCP tool."""

import json
import os
import pathlib
import subprocess
import sys

from fastmcp import FastMCP


mcp = FastMCP("finagent")
CLIENT = pathlib.Path(__file__).with_name("finagent_client.py")
PASSWORD_FILE = pathlib.Path("/run/admin_password")


@mcp.tool
def analyze_stock(stock_code: str, force_refresh: bool = False) -> dict:
    """Analyze one A-share, Hong Kong, or US stock with FinAgent and DeepSeek.

    The result is an AI-generated report. Verify market data and news sources before
    treating any trading suggestion as current. Use force_refresh to bypass today's
    cached analysis; it may incur another model API charge.
    """
    if not stock_code or len(stock_code) > 32 or not stock_code.isascii():
        raise ValueError("stock_code must be a nonempty ASCII stock symbol")
    command = [
        sys.executable,
        str(CLIENT),
        stock_code,
        "--password-file",
        str(PASSWORD_FILE),
    ]
    if force_refresh:
        command.append("--force-refresh")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", timeout=950, env=env
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-600:] or "FinAgent analysis failed")
    return json.loads(result.stdout)


if __name__ == "__main__":
    mcp.run(transport="stdio")
