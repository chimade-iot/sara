#!/usr/bin/env python3
"""
Render a sample contract as a PDF with the Sara QR code on its front page.

    python3 make_pdf.py                       # every contract with a body file
    python3 make_pdf.py contracts/msa-0418.json

Writes docs/<slug>/contract.pdf - page 1 is the cover carrying the QR, and
the agreement itself follows.

The point of the artefact: the QR is printed on the paper, so anyone holding
the document can reach the summary without being given a link, an account or
an application. The PDF is what you hand to a judge.

PDF rendering goes through whatever Chromium-family browser is already on
the machine (Chrome, Edge or Chromium) in headless mode. That avoids adding
a PDF toolchain as a dependency - every Windows machine already has Edge.
Set the CHROME environment variable to override the search.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).parent
CONTRACTS = ROOT / "contracts"
SITE = ROOT / "docs"

CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/opt/pw-browsers/chromium",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def find_browser() -> str | None:
    for c in CANDIDATES:
        if not c:
            continue
        if Path(c).is_file():
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def paras(text: str) -> str:
    return "".join(f"<p>{esc(p)}</p>" for p in text.split("\n") if p.strip())


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


CSS = """
@page { size: A4; margin: 22mm 20mm 20mm; }
* { box-sizing: border-box; }
body {
  margin: 0; font-family: Georgia, "Times New Roman", serif;
  font-size: 10.5pt; line-height: 1.5; color: #111;
}
/* --- cover ---------------------------------------------------------- */
.cover { height: 253mm; display: flex; flex-direction: column; }
.cover .rule { border-top: 2.5pt solid #111; margin-bottom: 10mm; }
.cover h1 { font-size: 22pt; font-weight: normal; line-height: 1.2; margin: 0 0 3mm; }
.cover .doctype { font-size: 11pt; color: #555; margin: 0 0 16mm; }
.cover dl { font-size: 10.5pt; line-height: 1.8; margin: 0; }
.cover dt { float: left; width: 40mm; clear: left; color: #555; }
.cover dd { margin: 0 0 0 40mm; }
.scan {
  margin-top: auto; display: flex; gap: 8mm; align-items: center;
  border: 0.8pt solid #999; padding: 7mm; background: #fafaf8;
}
.scan img { width: 32mm; height: 32mm; flex: 0 0 auto; }
.scan .t { font-family: Helvetica, Arial, sans-serif; font-size: 9.5pt; line-height: 1.5; }
.scan .t b { display: block; font-size: 11.5pt; margin-bottom: 2mm; }
.scan .t span { color: #444; display: block; }
.scan .t .url {
  font-family: "Courier New", monospace; font-size: 8.5pt;
  color: #666; margin-top: 2.5mm; word-break: break-all;
}
.coverfoot { margin-top: 6mm; font-size: 8pt; color: #888; }
/* --- the agreement --------------------------------------------------- */
.body { break-before: page; }
h2.doc {
  font-size: 13pt; font-weight: normal; text-align: center;
  letter-spacing: .06em; text-transform: uppercase; margin: 0 0 8mm;
}
.between p { margin: 0 0 4mm; }
.between .lead { font-weight: bold; }
.recitals { margin: 0 0 8mm; }
.recitals .h { font-weight: bold; margin: 0 0 2mm; }
.recitals ol { margin: 0; padding-left: 8mm; }
.recitals li { margin-bottom: 2mm; }
.op { font-weight: bold; margin: 0 0 6mm; }
section.cl { break-inside: auto; margin-bottom: 5mm; }
section.cl > h3 {
  font-size: 10.5pt; font-weight: bold; margin: 0 0 2mm;
  break-after: avoid;
}
.sub { display: grid; grid-template-columns: 13mm 1fr; margin-bottom: 1.8mm; }
.sub .n { color: #333; }
.sub .x { text-align: justify; }
.schedules { break-before: page; }
.sch { break-inside: avoid; margin-bottom: 7mm; }
.sch h3 { font-size: 11pt; margin: 0 0 3mm; }
.sch p { margin: 0 0 3mm; text-align: justify; }
.sign { break-inside: avoid; margin-top: 10mm; }
.sign .w { font-weight: bold; margin-bottom: 8mm; }
.sign table { width: 100%; border-collapse: collapse; }
.sign td { width: 50%; vertical-align: top; padding-right: 8mm; }
.sign .line { border-bottom: 0.8pt solid #111; height: 16mm; margin-bottom: 2mm; }
.sign .who { font-size: 9.5pt; color: #444; }
.footnote { margin-top: 10mm; font-size: 8pt; color: #888; text-align: center; }
"""


def build_html(d: dict, b: dict, qr_b64: str, url: str) -> str:
    cl = []
    for c in b["clauses"]:
        subs = "".join(
            f'<div class="sub"><span class="n">{esc(s["n"])}</span>'
            f'<span class="x">{esc(s["text"])}</span></div>'
            for s in c["subs"])
        cl.append(f'<section class="cl"><h3>{esc(c["n"])}. '
                  f'{esc(c["heading"])}</h3>{subs}</section>')

    sch = '<div class="schedules">' + "".join(
        f'<section class="sch"><h3>Schedule {esc(s["n"])} &mdash; '
        f'{esc(s["heading"])}</h3>{paras(s["text"])}</section>'
        for s in b["schedules"]) + "</div>"

    between = "".join(f"<p>{esc(x)}</p>" for x in b["between"])
    recitals = "".join(f"<li>{esc(x)}</li>" for x in b["recitals"])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{esc(d['title'])}</title><style>{CSS}</style></head>
<body>

<div class="cover">
  <div class="rule"></div>
  <h1>{esc(d['title'])}</h1>
  <p class="doctype">{esc(d['type'])} &middot; {esc(d['ref'])}</p>
  <dl>
    <dt>Between</dt><dd>{esc(d['parties'][0]['name'])}
      ({esc(d['parties'][0]['role'])})</dd>
    <dt>and</dt><dd>{esc(d['parties'][1]['name'])}
      ({esc(d['parties'][1]['role'])})</dd>
    <dt>Commencement</dt><dd>{esc(fmt(d['term_start']))}</dd>
    <dt>Expiry</dt><dd>{esc(fmt(d['term_end']))}</dd>
    <dt>Executed</dt><dd>{esc(fmt(d['executed']))}</dd>
  </dl>

  <div class="scan">
    <img src="data:image/png;base64,{qr_b64}" alt="">
    <div class="t">
      <b>Read or listen to the summary</b>
      <span>Scan with any phone camera. Plain-language answers to what this
      agreement actually does, the dates that matter, and a spoken brief.</span>
      <span>No app, no sign-in, nothing to install.</span>
      <span class="url">{esc(url)}</span>
    </div>
  </div>
  <p class="coverfoot">Illustrative document prepared for demonstration.
    The parties, figures and addresses are invented.</p>
</div>

<div class="body">
  <h2 class="doc">{esc(d['type'])}</h2>
  <div class="between">
    <p class="lead">{esc(b['parties_recital'])}</p>
    <p><b>BETWEEN:</b></p>
    {between}
  </div>
  <div class="recitals">
    <p class="h">WHEREAS:</p>
    <ol>{recitals}</ol>
  </div>
  <p class="op">NOW IT IS AGREED as follows:</p>
  {''.join(cl)}
  {sch}
  <div class="sign">
    <p class="w">{esc(b['execution'])}</p>
    <table><tr>
      <td><div class="line"></div>
        <div class="who">For and on behalf of<br>
          {esc(d['parties'][0]['name'])}</div></td>
      <td><div class="line"></div>
        <div class="who">For and on behalf of<br>
          {esc(d['parties'][1]['name'])}</div></td>
    </tr></table>
  </div>
  <p class="footnote">Illustrative document. Not a real agreement.</p>
</div>

</body></html>
"""


def build(src: Path) -> None:
    body_path = src.with_name(src.stem + ".body.json")
    if not body_path.exists():
        print(f"  {src.name}: no {body_path.name} - skipped")
        return

    d = json.loads(src.read_text(encoding="utf-8"))
    b = json.loads(body_path.read_text(encoding="utf-8"))
    out_dir = SITE / d["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)

    qr = out_dir / "qr.png"
    if not qr.exists():
        sys.exit(f"{qr} is missing - run generate.py first, "
                 "so the QR matches the published page")
    qr_b64 = base64.b64encode(qr.read_bytes()).decode("ascii")

    # Take the base URL from generate.py rather than restating it here. The
    # QR on the paper and the page it opens must never drift apart, and the
    # cheapest way to guarantee that is to have one definition of the host.
    from generate import BASE
    url = BASE.rstrip("/") + "/" + d["slug"] + "/"

    htm = build_html(d, b, qr_b64, url)
    tmp = Path(tempfile.mkdtemp(prefix="sara-pdf-")) / "contract.html"
    tmp.write_text(htm, encoding="utf-8")

    browser = find_browser()
    pdf = out_dir / "contract.pdf"
    if not browser:
        fallback = out_dir / "contract.html"
        fallback.write_text(htm, encoding="utf-8")
        print(f"  no Chrome, Edge or Chromium found. Wrote {fallback} "
              "- open it and print to PDF, or set CHROME=<path to the exe>.")
        return

    subprocess.run([browser, "--headless=new", "--disable-gpu",
                    "--no-pdf-header-footer", "--no-sandbox",
                    f"--print-to-pdf={pdf}", tmp.as_uri()],
                   capture_output=True, text=True, timeout=120)
    if not pdf.exists():
        sys.exit(f"{Path(browser).name} did not produce {pdf}")
    print(f"  {src.name}  ->  docs/{d['slug']}/contract.pdf "
          f"({pdf.stat().st_size / 1024:.0f} KB)")
    print(f"    {len(b['clauses'])} clauses, {len(b['schedules'])} schedules")
    print(f"    QR points at {url}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("sources", nargs="*", type=Path)
    a = ap.parse_args()
    srcs = a.sources or [p for p in sorted(CONTRACTS.glob("*.json"))
                         if not p.name.endswith(".body.json")]
    if not srcs:
        sys.exit("no contract records found in contracts/")
    b = find_browser()
    print(f"Rendering with: {b or 'nothing found - will write HTML instead'}")
    for s in srcs:
        build(s)


if __name__ == "__main__":
    main()
