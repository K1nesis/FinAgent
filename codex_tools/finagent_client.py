"""Call a tunneled FinAgent API for one stock without exposing credentials in argv."""

import argparse
import http.cookiejar
import json
import pathlib
import sys
import urllib.error
import urllib.request


def request_json(opener, url, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"FinAgent HTTP {error.code}: {body[:500]}") from error


def main():
    parser = argparse.ArgumentParser(description="Analyze one stock with FinAgent")
    parser.add_argument("stock_code", help="A/HK/US stock code, e.g. 600519 or AAPL")
    parser.add_argument("--url", default="http://127.0.0.1:18000")
    parser.add_argument("--password-file", type=pathlib.Path, required=True)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    if not args.url.startswith("http://127.0.0.1:"):
        parser.error("Only a local SSH tunnel URL is supported")

    password = args.password_file.read_text(encoding="utf-8").strip()
    if not password:
        parser.error("Password file is empty")

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    base = args.url.rstrip("/")
    status = request_json(opener, base + "/api/v1/auth/status")
    if not status.get("authEnabled") or not status.get("passwordSet"):
        raise RuntimeError("Set the FinAgent admin password in its web UI first")

    request_json(opener, base + "/api/v1/auth/login", {"password": password})
    result = request_json(
        opener,
        base + "/api/v1/analysis/analyze",
        {
            "stock_code": args.stock_code,
            "report_type": "full",
            "force_refresh": args.force_refresh,
            "async_mode": False,
            "notify": False,
        },
        timeout=900,
    )
    report = result.get("report") if isinstance(result, dict) else None
    if isinstance(report, dict):
        details = report.get("details") or {}
        raw_result = details.get("raw_result") or {}
        summary = report.get("summary") or {}
        if (
            isinstance(raw_result, dict)
            and not any(str(value).strip() for value in raw_result.values())
            and summary.get("analysis_summary") == "待补充"
        ):
            raise RuntimeError(
                "FinAgent returned a placeholder report; check LLM API balance and server logs"
            )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
