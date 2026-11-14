#!/usr/bin/env python3
"""
Render onepager.md as a single-page A4 PDF, with a QR code per contract.

    python3 make_onepager.py

Writes onepager.pdf beside the markdown. Edit onepager.md and run it again;
the markdown stays the single source of the words, and the QR band is built
from the contract records so a slug can never drift between the entry
document and the live pages.

The QR codes are the point. A judge reading this scans from the screen and
performs the gesture the product is about, rather than clicking a link and
leaving the document. One code per contract, because that is how it works
on paper: the code belongs to the agreement, not to the product.
"""

from __future__ import annotations

import base64
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from make_pdf import find_browser          # noqa: E402  same browser search
from generate import BASE                  # noqa: E402  one definition of the host


def md(text: str) -> str:
    """Just enough markdown: headings, bold, italic, paragraphs."""
    out = []
    for block in [b.strip() for b in text.split("\n\n") if b.strip()]:
        esc = html.escape(block, quote=False)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"(?<!\*)\*([^*\s][^*]*?)\*(?!\*)", r"<em>\1</em>", esc)
        if esc.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif esc.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        else:
            out.append("<p>" + esc.replace("\n", "<br>") + "</p>")
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 14mm 15mm 12mm; }
* { box-sizing: border-box; }
body { margin:0; font-family: Georgia,"Times New Roman",serif;
       font-size: 9.1pt; line-height: 1.42; color:#202e4c; }
h1 { font-size: 19pt; font-weight: normal; margin: 0 0 1mm; letter-spacing:-.2pt; }
h1 + p { font-size: 8.6pt; color:#4a5878; margin: 0 0 3mm;
         padding-bottom: 2.5mm; border-bottom: 2pt solid #202e4c; }
h2 { font-family: "Helvetica Neue",Helvetica,Arial,sans-serif;
     font-size: 7.6pt; font-weight: 700; letter-spacing: .13em;
     text-transform: uppercase; color:#4a5878;
     margin: 3.4mm 0 1.4mm; break-after: avoid; }
p { margin: 0 0 1.9mm; text-align: justify; }
strong { font-weight: bold; }
em { font-style: italic; }
.scan { margin-top: 3mm; display: flex; gap: 6mm; }
.card { flex: 1 1 0; border: 0.8pt solid #aed6e8; background:#f1f9fd;
        border-radius: 2mm; padding: 3.5mm 4mm; display:flex; gap:4mm;
        align-items:center; }
.card img { width: 21mm; height: 21mm; flex: 0 0 auto; }
.card .t { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;
           font-size: 7.6pt; line-height: 1.4; }
.card .t b { display:block; font-size: 8.4pt; margin-bottom: 1mm;
             font-family: Georgia, serif; }
.card .t span { display:block; color:#4a5878; }
.card .t .u { font-family:"Courier New",monospace; font-size: 6.2pt;
              color:#7d89a3; margin-top: 1.2mm;
              white-space: nowrap; text-decoration: none; display:block; }
.foot { margin-top: 3mm; padding-top: 2mm; border-top: 0.8pt solid #cbe6f1;
        font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;
        font-size: 7.4pt; color:#4a5878; line-height:1.5; }
.foot b { color:#202e4c; }
"""


def main() -> None:
    src = ROOT / "onepager.md"
    if not src.exists():
        sys.exit("onepager.md is missing")

    cards = []
    for rec in sorted((ROOT / "contracts").glob("*.json")):
        if rec.name.endswith(".body.json"):
            continue
        d = json.loads(rec.read_text(encoding="utf-8"))
        qr = ROOT / "docs" / d["slug"] / "qr.png"
        if not qr.exists():
            sys.exit(f"{qr} is missing - run generate.py first")
        b64 = base64.b64encode(qr.read_bytes()).decode("ascii")
        url = BASE.rstrip("/") + "/" + d["slug"] + "/"
        cards.append(
            f'<div class="card"><img src="data:image/png;base64,{b64}" alt="">'
            f'<div class="t"><b>{html.escape(d["title"])}</b>'
            f'<span>{html.escape(d["type"])}</span>'
            f'<a class="u" href="{html.escape(url, quote=True)}">'
            f'{html.escape(url.replace("https://", ""))}</a>'
            "</div></div>")

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Sara - one page</title><style>{CSS}</style></head><body>
{md(src.read_text(encoding="utf-8"))}
<div class="scan">{''.join(cards)}</div>
<p class="foot"><b>Everything above is live.</b> Each page carries the
summary, the spoken brief and the source agreement as a PDF, and page 1 of
that PDF carries the same QR code you just scanned. Code and contract
records: <b>github.com/chimade-iot/sara</b>. Built with Claude. The
extraction step is model-agnostic, so it runs on whichever assistant an
organisation has already approved. Every contract here is invented. No
client data appears anywhere in this entry.</p>
</body></html>"""

    tmp = Path(tempfile.mkdtemp(prefix="sara-1p-")) / "onepager.html"
    tmp.write_text(page, encoding="utf-8")

    browser = find_browser()
    out = ROOT / "onepager.pdf"
    if not browser:
        (ROOT / "onepager.html").write_text(page, encoding="utf-8")
        print("No Chrome, Edge or Chromium found. Wrote onepager.html "
              "- open it and print to PDF.")
        return
    subprocess.run([browser, "--headless=new", "--disable-gpu",
                    "--no-pdf-header-footer", "--no-sandbox",
                    f"--print-to-pdf={out}", tmp.as_uri()],
                   capture_output=True, text=True, timeout=120)
    if not out.exists():
        sys.exit("the browser produced no PDF")

    pages = "?"
    try:
        from pypdf import PdfReader
        pages = len(PdfReader(str(out)).pages)
    except Exception:
        pass
    print(f"onepager.pdf  ({out.stat().st_size / 1024:.0f} KB, {pages} page)")
    print(f"  {len(cards)} QR code(s) embedded")
    if pages != 1:
        print(f"  WARNING: {pages} pages. Trim onepager.md - the brief asks "
              "for one page.")


if __name__ == "__main__":
    main()
