"""Recon script: discover whether German healthcare directories expose JSON APIs.

Launches a headless Chromium via Playwright, visits each candidate directory,
enumerates the search forms / inline scripts / iframes, attempts to submit a
search, and records every XHR/fetch call the page makes (URL, method, headers,
request body, response status, content-type, first 5 KB of response body).

Output is written to ``recon/<site>.json`` and a ``recon/summary.md`` overview.

Usage:

    poetry run playwright install chromium
    poetry run python scripts/recon_sources.py

Override the target list via ``--only ptk,psych_info`` or add a custom site via
``--extra name=https://example.com/search``.

No authentication, no CAPTCHA bypass — if a site blocks the request, the
script reports the failure and moves on.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sys
from typing import Any

try:
    from playwright.async_api import (
        Page,
        Request,
        Response,
        async_playwright,
    )
except ImportError:  # pragma: no cover - handled at runtime
    print(
        "playwright is not installed. Run:\n"
        "    poetry add --group dev playwright\n"
        "    poetry run playwright install chromium",
        file=sys.stderr,
    )
    raise SystemExit(1) from None


OUT_DIR = Path("recon")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 "
    "therapist-finder-recon/0.1 (+https://github.com/anneoneone/therapist-finder)"
)


@dataclass
class NetworkCall:
    """A single HTTP request captured by Playwright."""

    url: str
    method: str
    resource_type: str
    request_headers: dict[str, str]
    post_data: str | None
    status: int | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: str | None = None
    content_type: str | None = None


DISCOVER_JS = """() => {
    const forms = Array.from(document.forms).map(f => ({
        action: f.action,
        method: f.method,
        id: f.id,
        name: f.name,
        inputs: Array.from(f.elements).map(i => ({
            tag: i.tagName,
            name: i.name,
            id: i.id,
            type: i.type,
            placeholder: i.placeholder,
            required: i.required
        }))
    }));
    const scripts = Array.from(document.querySelectorAll('script')).map(s => ({
        src: s.src || null,
        type: s.type || null,
        inlineLength: s.src ? 0 : (s.textContent || '').length,
        preview: s.src ? null : (s.textContent || '').slice(0, 200)
    }));
    const iframes = Array.from(document.querySelectorAll('iframe')).map(i => ({
        src: i.src, id: i.id, name: i.name
    }));
    const appRoot =
        document.querySelector('#app, #root, [data-v-app]')?.outerHTML?.slice(0, 500) || null;
    const globals = Object.keys(window).filter(
        k => k.startsWith('__') && typeof window[k] === 'object'
    );
    return { title: document.title, forms, scripts, iframes, appRoot, globals };
}"""


SEARCH_TERM = "Berlin"


async def submit_generic(page: Page) -> None:
    """Best-effort search submission: fill first text-like input, press Enter."""
    selectors = [
        "input[type='search']",
        "input[name*='ort' i]",
        "input[placeholder*='Ort' i]",
        "input[placeholder*='PLZ' i]",
        "input[name*='plz' i]",
        "input[type='text']",
    ]
    for selector in selectors:
        try:
            el = await page.query_selector(selector)
            if el is None:
                continue
            await el.fill(SEARCH_TERM, timeout=3000)
            await page.keyboard.press("Enter")
            return
        except Exception:
            continue
    # As a last resort, try submitting the first form
    try:
        await page.evaluate("document.forms[0] && document.forms[0].submit()")
    except Exception:
        pass


@dataclass
class Target:
    """A recon target site."""

    name: str
    url: str


DEFAULT_TARGETS = [
    # Verified real URLs. Note: psychotherapeutenkammer-berlin.de delegates
    # its search to psych-info.de, and aekb.de + kvberlin.de overlap 116117,
    # so psych_info and therapie_de are the main targets worth probing for
    # JSON APIs.
    Target(
        "psych_info",
        "https://psych-info.de/",
    ),
    Target(
        "therapie_de",
        "https://www.therapie.de/psychotherapie/-ort-/berlin/",
    ),
    Target(
        "ptk_berlin",
        "https://www.psychotherapeutenkammer-berlin.de/psychotherapeutinnensuche",
    ),
    Target(
        "aekb",
        "https://www.aekb.de/patient-innen/suche-nach-aerztinnen",
    ),
]


async def record_target(target: Target) -> dict[str, Any]:
    """Open the target URL, attempt a search, and capture network traffic."""
    calls: list[NetworkCall] = []
    by_id: dict[str, NetworkCall] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT, locale="de-DE")
        page = await context.new_page()

        def on_request(req: Request) -> None:
            nc = NetworkCall(
                url=req.url,
                method=req.method,
                resource_type=req.resource_type,
                request_headers=dict(req.headers),
                post_data=req.post_data,
            )
            by_id[f"{req.method} {req.url}"] = nc
            calls.append(nc)

        async def capture_response(resp: Response) -> None:
            nc = by_id.get(f"{resp.request.method} {resp.url}")
            if nc is None:
                return
            nc.status = resp.status
            nc.response_headers = dict(resp.headers)
            nc.content_type = resp.headers.get("content-type", "")
            try:
                body = await resp.text()
                nc.response_body = body[:5000]
            except Exception:
                nc.response_body = None

        def on_response(resp: Response) -> None:
            asyncio.create_task(capture_response(resp))

        page.on("request", on_request)
        page.on("response", on_response)

        page_error: str | None = None
        discovery: dict[str, Any] = {}
        try:
            await page.goto(target.url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            discovery = await page.evaluate(DISCOVER_JS)
            await submit_generic(page)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)
        except Exception as e:
            page_error = str(e)

        html_snapshot = ""
        try:
            html_snapshot = await page.content()
        except Exception:
            pass

        await browser.close()

    xhr_calls = [
        c for c in calls if c.resource_type in ("xhr", "fetch") or _looks_like_api(c.url)
    ]

    return {
        "target": asdict(target),
        "error": page_error,
        "discovery": discovery,
        "xhr_call_count": len(xhr_calls),
        "total_call_count": len(calls),
        "xhr_calls": [asdict(c) for c in xhr_calls],
        "all_calls": [
            {
                "url": c.url,
                "method": c.method,
                "resource_type": c.resource_type,
                "status": c.status,
                "content_type": c.content_type,
            }
            for c in calls
        ],
        "html_snapshot": html_snapshot[:20000],
    }


def _looks_like_api(url: str) -> bool:
    markers = ("/api/", "/rest/", "/ajax/", ".json", "/search?", "graphql")
    return any(m in url.lower() for m in markers)


def _write_report(name: str, report: dict[str, Any]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{name}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _render_summary(reports: dict[str, dict[str, Any]]) -> str:
    lines = ["# Recon summary\n"]
    for name, report in reports.items():
        target = report["target"]
        lines.append(f"## {name} — `{target['url']}`\n")
        if report["error"]:
            lines.append(f"- ❌ error: `{report['error']}`\n")
            continue
        disc = report.get("discovery") or {}
        lines.append(f"- page title: {disc.get('title')!r}")
        lines.append(f"- forms: {len(disc.get('forms', []))}")
        lines.append(f"- iframes: {len(disc.get('iframes', []))}")
        if disc.get("iframes"):
            for i in disc["iframes"]:
                lines.append(f"  - iframe → {i.get('src')}")
        lines.append(
            f"- XHR/fetch/API-looking calls: {report['xhr_call_count']} "
            f"of {report['total_call_count']} total"
        )
        for call in report["xhr_calls"][:20]:
            ct = call.get("content_type") or ""
            status = call.get("status")
            lines.append(
                f"  - `{call['method']} {call['url']}` → {status} {ct}"
            )
        lines.append("")
    return "\n".join(lines)


async def main_async(targets: list[Target]) -> None:
    """Run recon across all targets and write the reports."""
    reports: dict[str, dict[str, Any]] = {}
    for t in targets:
        print(f"→ {t.name}: {t.url}", file=sys.stderr)
        try:
            report = await record_target(t)
        except Exception as e:
            print(f"  ✗ recording failed: {e}", file=sys.stderr)
            report = {"target": asdict(t), "error": str(e)}
        reports[t.name] = report
        _write_report(t.name, report)
        count = report.get("xhr_call_count", 0)
        print(f"  ✓ {count} XHR/API-ish calls → recon/{t.name}.json", file=sys.stderr)

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "summary.md").write_text(
        _render_summary(reports), encoding="utf-8"
    )
    print("\nsee recon/summary.md for an overview.", file=sys.stderr)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """CLI args for picking which targets to run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        default="",
        help="comma-separated target names to run (default: all)",
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="additional target as name=URL (repeatable)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    args = parse_args(argv or sys.argv[1:])
    targets = list(DEFAULT_TARGETS)
    if args.only:
        wanted = {w.strip() for w in args.only.split(",") if w.strip()}
        targets = [t for t in targets if t.name in wanted]
    for extra in args.extra:
        name, _, url = extra.partition("=")
        if name and url:
            targets.append(Target(name=name.strip(), url=url.strip()))
    if not targets:
        print("no targets selected", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(main_async(targets))


if __name__ == "__main__":
    main()
