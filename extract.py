#!/usr/bin/env python3
"""
Read a contract and fill in the fact sheet that generate.py renders.

    python3 extract.py contract.pdf --slug ab12cd34      # read it
    python3 extract.py contract.pdf --dry-run            # show the prompt
    python3 extract.py contracts/msa-0418.json --check   # validate a sheet

This is the only part of the pipeline that interprets anything. generate.py
is deterministic - it lays out whatever the fact sheet says and can invent
nothing. Keeping the two apart is the point: the probabilistic step produces
one short, readable JSON file that a lawyer checks in two minutes, before a
single page is published. You review the fact sheet, not the output.

No model is bundled. Point it at whichever endpoint your organisation has
already approved - the same configuration decision as the Ask FactorAI panel
on the page. Nothing here calls a vendor you have not chosen:

    set SARA_PROVIDER=anthropic          (or openai)
    set SARA_MODEL=<model name>
    set SARA_KEY=<your key>
    set SARA_URL=<optional, for a private or proxied endpoint>

Scanned PDFs will not work. This reads the text layer; it does no OCR.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).parent

# ==========================================================================
# The fact sheet
# ==========================================================================
# This is the contract between the two halves of the pipeline. generate.py
# reads exactly these keys and nothing else, so the model's whole job is to
# fill this in. Changing the shape here means changing generate.py too.

SCHEMA = {
    "slug": "short opaque id for the URL, lowercase letters and digits",
    "type": "the kind of agreement, e.g. Master Services Agreement",
    "title": "the title as it appears on the document",
    "ref": "the contract reference or number",
    "executed": "YYYY-MM-DD",
    "term_start": "YYYY-MM-DD",
    "term_end": "YYYY-MM-DD",
    "status": "In force | Expired | Terminated",
    "parties": [{"name": "legal name", "role": "customer | supplier"}],
    "brief": "a spoken script, 250-400 words, read aloud to someone driving. "
             "Plain sentences, no bullet points, no clause numbers, no symbols. "
             "Write figures as words a reader would say.",
    "headline": [{"q": "the question a non-lawyer would ask",
                  "a": "the answer, with <b>...</b> around the figures that matter",
                  "ref": "cl. 1.1, sch. 2"}],
    "dates": [{"date": "YYYY-MM-DD", "what": "what happens",
               "note": "why it matters, or who must act", "ref": "cl. 1.1"}],
    "qa": [{"q": "question", "a": "answer with <b>...</b> on key figures",
            "side": "customer | supplier | both", "ref": "cl. 1.1"}],
    "escalate": {"to": "email address", "team": "whose inbox this is"},
}

PROMPT = """You are preparing a plain-language fact sheet about a contract, \
for the people who have to live with it: the procurement manager, the site \
lead, the account owner. They are not lawyers and will never read the \
agreement itself.

Read the contract below and return ONE JSON object matching the schema. \
Return only the JSON - no commentary, no code fences.

RULES, in order of importance.

1. Every statement must be traceable to the text. If the contract does not \
say it, do not write it. Where you are unsure, leave the field out rather \
than guessing - a missing answer is recoverable, a confident wrong one is not.

2. Cite the clause for every answer, in the "ref" field, using the \
document's own numbering ("cl. 14.2", "sch. 2"). Several refs are fine.

3. Answer the question that was asked, not the one the clause answers. \
"Can we get out of it?" is answered by "Not before 30 June 2028", then the \
detail - not by a summary of the termination clause.

4. Lead with what is true for the reader rather than what is in the \
contract's order. State the bad news plainly: a notice period they will \
miss, a cap that excludes the thing they care about, an auto-renewal, a \
remedy that is the only remedy, a term that binds them for two more years.

5. Wrap the figures that matter in <b>...</b> - amounts, notice periods, \
caps, percentages, dates. No other HTML.

6. "headline" holds exactly five questions, in this order: how do we get \
out, what does it cost, what must we do and by when, what happens if they \
fail, who can change it. Reword each to suit this contract.

7. "qa" holds fifteen to twenty-five further questions, the ones that \
actually get asked: assignment, subcontracting, data ownership and \
location, audit, insurance, price increases, exclusivity, what survives, \
governing law, dispute forum. Tag each with the side it concerns.

8. "dates" holds every date a reader could act on or miss - notice \
deadlines, renewal dates, certificates due, review dates. Include dates \
that have already passed; being told something is overdue is the single \
most useful thing this page does.

9. "brief" is spoken aloud, and the listener reached it by scanning the \
contract, so they already know which document they are holding. Do not \
open by introducing it. Open with what they must do and when, starting \
with anything already overdue. Then what it costs and what binds them, \
then the traps. Name the agreement and its governing law in one closing \
line, as context rather than preamble. No numbering, no clause references, \
no symbols: "one crore twenty four lakh rupees", not "Rs 1,24,00,000". \
Aim for 230 to 280 words. A listener gives you fifteen seconds to be \
useful, and the start date is not useful.

SCHEMA:
{schema}

CONTRACT:
{contract}
"""


# ==========================================================================
# Reading the source document
# ==========================================================================

def read_source(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("Reading a PDF needs pypdf:  pip install pypdf")
        pages = [p.extract_text() or "" for p in PdfReader(str(path)).pages]
        text = "\n\n".join(pages).strip()
        if len(text) < 500:
            sys.exit(
                f"{path.name} yielded only {len(text)} characters of text. "
                "It is probably a scan. This reads the text layer and does "
                "no OCR - run it through an OCR tool first.")
        return text

    if path.suffix.lower() == ".json":
        # A body file: the agreement already structured. Flatten it back to
        # prose so the model sees what a reader would see.
        b = json.loads(path.read_text(encoding="utf-8"))
        if "clauses" not in b:
            return path.read_text(encoding="utf-8")
        out = [b.get("parties_recital", "")]
        out += b.get("between", [])
        out += [f"Recital: {r}" for r in b.get("recitals", [])]
        for c in b["clauses"]:
            out.append(f"\n{c['n']}. {c['heading']}")
            out += [f"{s['n']} {s['text']}" for s in c["subs"]]
        for s in b.get("schedules", []):
            out.append(f"\nSchedule {s['n']} - {s['heading']}\n{s['text']}")
        return "\n".join(out)

    return path.read_text(encoding="utf-8")


# ==========================================================================
# The model call
# ==========================================================================

def call_model(prompt: str) -> str:
    provider = os.environ.get("SARA_PROVIDER", "anthropic").lower()
    key = os.environ.get("SARA_KEY", "")
    model = os.environ.get("SARA_MODEL", "")
    if not key:
        sys.exit("No SARA_KEY set. Use --dry-run to see the prompt without "
                 "calling anything, or set the environment variables listed "
                 "at the top of this file.")
    if not model:
        sys.exit("No SARA_MODEL set - name the model your organisation has "
                 "approved.")
    try:
        import requests
    except ImportError:
        sys.exit("The model call needs requests:  pip install requests")

    if provider == "anthropic":
        url = os.environ.get("SARA_URL", "https://api.anthropic.com/v1/messages")
        r = requests.post(url, timeout=300, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01",
            "content-type": "application/json"},
            json={"model": model, "max_tokens": 16000,
                  "messages": [{"role": "user", "content": prompt}]})
        if r.status_code != 200:
            sys.exit(f"{url} returned {r.status_code}: {r.text[:400]}")
        return "".join(b.get("text", "") for b in r.json().get("content", []))

    url = os.environ.get("SARA_URL",
                         "https://api.openai.com/v1/chat/completions")
    r = requests.post(url, timeout=300, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model,
              "messages": [{"role": "user", "content": prompt}]})
    if r.status_code != 200:
        sys.exit(f"{url} returned {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"]


def parse_json(raw: str) -> dict:
    """Models wrap JSON in prose and fences however firmly you ask them not to."""
    s = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", s, re.S)
    if fence:
        s = fence.group(1).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        sys.exit("The model returned no JSON object:\n" + raw[:600])
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError as e:
        sys.exit(f"The model returned malformed JSON ({e}). First 600 chars:\n"
                 + s[:600])


# ==========================================================================
# The review gate
# ==========================================================================
# A fact sheet that passes these checks is still only machine-checked. The
# point of printing the review sheet is that the next pair of eyes is human.

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate(rec: dict, source: str = "") -> list[str]:
    bad = []
    for k in ("slug", "type", "title", "ref", "term_start", "term_end",
              "status", "parties", "headline", "dates", "qa", "escalate"):
        if not rec.get(k):
            bad.append(f"missing or empty: {k}")

    for k in ("executed", "term_start", "term_end"):
        v = rec.get(k, "")
        if v and not ISO.match(str(v)):
            bad.append(f"{k} is not YYYY-MM-DD: {v!r}")

    if not re.fullmatch(r"[a-z0-9]{6,12}", str(rec.get("slug", ""))):
        bad.append("slug should be 6-12 lowercase letters and digits, and "
                   "unguessable - it is the only thing protecting the page")

    if len(rec.get("parties", [])) != 2:
        bad.append("expected exactly two parties")

    if len(rec.get("headline", [])) != 5:
        bad.append(f"expected 5 headline questions, got "
                   f"{len(rec.get('headline', []))}")

    for i, d in enumerate(rec.get("dates", []), 1):
        if not ISO.match(str(d.get("date", ""))):
            bad.append(f"date {i} is not YYYY-MM-DD: {d.get('date')!r}")

    for i, q in enumerate(rec.get("qa", []), 1):
        if q.get("side") not in ("customer", "supplier", "both"):
            bad.append(f"qa {i} has side {q.get('side')!r}")
        if not q.get("ref"):
            bad.append(f"qa {i} ({q.get('q', '')[:40]}...) cites no clause")

    words = len(str(rec.get("brief", "")).split())
    if words and not 180 <= words <= 500:
        bad.append(f"brief is {words} words; aim for 250-400")
    for ch in ("₹", "#", "*", "`"):
        if ch in str(rec.get("brief", "")):
            bad.append(f"brief contains {ch!r} - it is read aloud, so write "
                       "figures and symbols as words")

    # Every cited clause should exist in the document. This catches the
    # failure that matters most: a confident answer pinned to a clause
    # number the contract does not have.
    if source:
        nums = set(re.findall(r"\b\d+\.\d+\b", source))
        for grp in list(rec.get("headline", [])) + list(rec.get("qa", [])):
            for ref in re.findall(r"\b\d+\.\d+\b", str(grp.get("ref", ""))):
                if ref not in nums:
                    bad.append(f"cites cl. {ref}, which is not in the document "
                               f"({str(grp.get('q', ''))[:40]}...)")
    return bad


def review_sheet(rec: dict) -> None:
    print("\n" + "=" * 68)
    print("REVIEW BEFORE PUBLISHING - check these against the contract")
    print("=" * 68)
    print(f"{rec.get('title', '?')}  [{rec.get('ref', '?')}]")
    print(f"  {rec.get('term_start')} to {rec.get('term_end')}   "
          f"status: {rec.get('status')}")
    for p in rec.get("parties", []):
        print(f"  {p.get('role', '?'):<9} {p.get('name', '?')}")
    print("\nDates the page will count down to:")
    for d in sorted(rec.get("dates", []), key=lambda d: str(d.get("date"))):
        print(f"  {d.get('date')}  {d.get('what', '')}  [{d.get('ref', '')}]")
    print("\nThe five answers:")
    for h in rec.get("headline", []):
        plain = re.sub(r"</?b>", "", str(h.get("a", "")))
        print(f"  Q {h.get('q', '')}")
        print(f"    {plain[:150]}{'...' if len(plain) > 150 else ''}  "
              f"[{h.get('ref', '')}]")
    print(f"\n{len(rec.get('qa', []))} further answers, "
          f"{len(rec.get('dates', []))} dates.")
    print("=" * 68)


# ==========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("source", type=Path,
                    help="the contract (.pdf, .txt) or a fact sheet (.json)")
    ap.add_argument("--slug", help="override the slug the model proposes")
    ap.add_argument("--out", type=Path, help="where to write the fact sheet")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the prompt and exit, calling nothing")
    ap.add_argument("--check", action="store_true",
                    help="validate an existing fact sheet, calling nothing")
    a = ap.parse_args()

    if not a.source.exists():
        sys.exit(f"{a.source} does not exist")

    if a.check:
        rec = json.loads(a.source.read_text(encoding="utf-8"))
        body = a.source.with_name(a.source.stem + ".body.json")
        src = read_source(body) if body.exists() else ""
        problems = validate(rec, src)
        review_sheet(rec)
        for p in problems:
            print(f"  PROBLEM  {p}")
        print("  no problems found" if not problems
              else f"\n{len(problems)} problem(s) to fix before publishing")
        sys.exit(1 if problems else 0)

    text = read_source(a.source)
    prompt = PROMPT.format(schema=json.dumps(SCHEMA, indent=2), contract=text)
    print(f"{a.source.name}: {len(text):,} characters of contract text")

    if a.dry_run:
        print("\n--- prompt that would be sent "
              f"({len(prompt):,} characters) ---\n")
        print(prompt[:4000])
        if len(prompt) > 4000:
            print(f"\n... and {len(prompt) - 4000:,} more characters "
                  "of contract text")
        return

    print(f"asking {os.environ.get('SARA_MODEL')} "
          f"via {os.environ.get('SARA_PROVIDER', 'anthropic')}...")
    rec = parse_json(call_model(prompt))
    if a.slug:
        rec["slug"] = a.slug

    problems = validate(rec, text)
    review_sheet(rec)
    for p in problems:
        print(f"  PROBLEM  {p}")

    out = a.out or (ROOT / "contracts" / (a.source.stem + ".json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nwrote {out}")
    if problems:
        print(f"{len(problems)} problem(s) above. Fix the fact sheet, then "
              "run generate.py.")
    else:
        print("Machine checks passed. Read the review sheet above against "
              "the contract before you publish - that is the gate this "
              "pipeline is built around.")


if __name__ == "__main__":
    main()
