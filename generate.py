#!/usr/bin/env python3
"""
Build a scan-to-read contract summary from a contract record.

    python3 generate.py                 # every contract in contracts/
    python3 generate.py contracts/x.json
    python3 generate.py --no-audio      # skip the spoken brief

For each contract this writes docs/<slug>/ containing:

    index.html   the summary page - one file, no build step, no framework
    summary.json the same facts as data, for anything else that wants them
    brief.mp3    the spoken brief
    qr.png       a QR code pointing at the page
    cover.html   a mock contract front page carrying that QR, to print

The page is static. Everything that depends on today's date - "in 50 days",
"overdue", the ordering of the diary - is computed in the reader's browser
at load time from the stored ISO dates, so a page generated in March still
reads correctly in November without anyone regenerating anything. The only
reason to regenerate is that the contract itself changed.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:                                  # Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                     # older Python, or a redirected pipe
    pass

ROOT = Path(__file__).parent
CONTRACTS = ROOT / "contracts"
SITE = ROOT / "docs"

# Where the pages will live. The QR encodes BASE + slug, so this has to be
# right before you print anything. Slugs are opaque on purpose: a QR is a
# bearer token, and a guessable URL is a worse one.
BASE = "https://chimade-iot.github.io/sara/"

PRODUCT = "Sāra"                 # overridden by --name
VOICE = "en-IN-PrabhatNeural"     # same family as the bulletin
RATE = "-4%"                      # --rate=-4%, never --rate -4% (argparse)


# ---------------------------------------------------------------- helpers

def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def run(cmd: list[str]) -> None:
    """Run a command and surface its own error text, not just a code."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-6:]
        raise SystemExit(
            f"{cmd[0]} failed ({p.returncode}):\n  " + "\n  ".join(tail))


def say(text: str, out: Path) -> bool:
    """
    Speak the brief.

    This calls the edge_tts library rather than the edge-tts command, and
    the reason is diagnostic. The CLI can exit non-zero having written
    nothing to either stream, which leaves you holding an exit code and no
    explanation. The library raises, so whatever went wrong - no network,
    a rejected voice name, a 403 from the service - arrives with its name
    attached.
    """
    try:
        import asyncio
        import edge_tts
    except ImportError:
        print("    audio skipped: edge-tts is not installed "
              "(pip install edge-tts)")
        return False

    async def speak() -> None:
        c = edge_tts.Communicate(text, VOICE, rate=RATE)
        await c.save(str(out))

    try:
        asyncio.run(speak())
    except Exception as e:                      # noqa: BLE001 - we report it
        out.unlink(missing_ok=True)
        print(f"    audio skipped: {type(e).__name__}: {e}")
        return False

    if not out.exists() or out.stat().st_size < 2048:
        size = out.stat().st_size if out.exists() else 0
        out.unlink(missing_ok=True)
        print(f"    audio skipped: the service returned {size} bytes")
        return False

    print(f"    spoke {len(text)} characters -> {out.name} "
          f"({out.stat().st_size / 1024:.0f} KB)")
    return True


def check_audio() -> int:
    """Say one short line and report precisely what happened."""
    import tempfile
    print(f"voice {VOICE}, rate {RATE}")
    tmp = Path(tempfile.gettempdir()) / "sara-audio-check.mp3"
    ok = say("This is a test of the spoken brief.", tmp)
    if ok:
        print(f"OK - audio works. Wrote {tmp}")
        tmp.unlink(missing_ok=True)
        return 0
    print("\nAudio is not working. Common causes, in order:")
    print("  1. No route to the speech service from this network "
           "(a corporate proxy or VPN will do it) - try a phone hotspot.")
    print("  2. An outdated edge-tts: pip install -U edge-tts")
    print("  3. The voice name is wrong: python generate.py --voices")
    return 1


def list_voices() -> int:
    import asyncio
    import edge_tts
    vs = asyncio.run(edge_tts.list_voices())
    for v in sorted(vs, key=lambda v: v["ShortName"]):
        if v["Locale"].startswith(("en-IN", "en-GB", "en-US")):
            print(f"  {v['ShortName']:<28} {v['Gender']:<7} {v['Locale']}")
    return 0


def qr_png(url: str, out: Path) -> None:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    img = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                        box_size=10, border=2)
    img.add_data(url)
    img.make(fit=True)
    img.make_image(fill_color="black", back_color="white").save(out)


# ---------------------------------------------------------------- the page

STYLE = """
:root{
  --paper:#f4f3ef;--surface:#fff;--surface-2:#f7f6f2;
  --ink:#16181d;--ink-2:#464c57;--ink-3:#7b828e;
  --rule:#e2e0d9;--rule-2:#d2cfc6;
  --accent:#b4651a;--accent-soft:#fdf3e6;
  --good:#2f6b4f;--good-soft:#eaf3ee;
  --warn:#9a3412;--warn-soft:#fdeee7;
  --serif:Georgia,"Iowan Old Style","Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#0f1115;--surface:#161920;--surface-2:#1b1f27;
  --ink:#f1f2f4;--ink-2:#b8bec9;--ink-3:#848c99;
  --rule:#262b34;--rule-2:#333944;
  --accent:#e2922f;--accent-soft:#2a1f12;
  --good:#6cc49a;--good-soft:#13241c;
  --warn:#f0916b;--warn-soft:#2a1811;}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:52rem;margin:0 auto;padding:1.6rem 1rem 4rem}
.eyebrow{font-family:var(--mono);font-size:.688rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink-3)}
h1{font-family:var(--serif);font-weight:400;font-size:clamp(1.5rem,4.5vw,2.1rem);
  line-height:1.15;margin:.35rem 0 .5rem}
h2{font-family:var(--mono);font-size:.75rem;font-weight:500;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink-2);margin:0}
.masthead{border-bottom:2px solid var(--ink);padding-bottom:.9rem;margin-bottom:1.3rem}
.idrow{display:flex;flex-wrap:wrap;gap:.45rem .5rem;align-items:center;margin-top:.5rem}
.chip{font-family:var(--mono);font-size:.688rem;letter-spacing:.06em;padding:.25rem .5rem;
  border:1px solid var(--rule-2);border-radius:3px;color:var(--ink-2);background:var(--surface)}
.chip.live{border-color:var(--good);color:var(--good);background:var(--good-soft)}
.chip.ref{color:var(--ink-3)}
.sidebar-row{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;margin-bottom:1.1rem}
.seg{display:inline-flex;border:1px solid var(--rule-2);border-radius:4px;overflow:hidden;
  background:var(--surface)}
.seg button{font-family:var(--mono);font-size:.72rem;letter-spacing:.07em;
  text-transform:uppercase;padding:.5rem .85rem;border:0;background:none;
  color:var(--ink-3);cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.sidenote{font-size:.813rem;color:var(--ink-3)}
.audio{display:flex;align-items:center;gap:.9rem;background:var(--surface);
  border:1px solid var(--rule);border-radius:4px;padding:.9rem 1rem;margin-bottom:1.5rem}
.playbtn{flex:0 0 auto;width:2.9rem;height:2.9rem;border-radius:50%;background:var(--ink);
  border:0;cursor:pointer;display:grid;place-items:center}
.playbtn svg{width:1.1rem;height:1.1rem;fill:var(--paper)}
.audio .meta{flex:1 1 auto;min-width:0}
.audio .meta b{display:block;font-weight:600;font-size:.938rem}
.audio .meta span{font-size:.813rem;color:var(--ink-3)}
.wave{display:flex;gap:2px;align-items:flex-end;height:1.5rem;flex:0 0 auto}
.wave i{width:3px;background:var(--rule-2);border-radius:1px;display:block}
.wave.on i{background:var(--accent)}
.sechead{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
  border-bottom:1px solid var(--rule);padding-bottom:.45rem;margin:0 0 .9rem}
.qa{display:grid;gap:.6rem;margin-bottom:1.6rem}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:4px;
  padding:.85rem 1rem}
.card .q{font-family:var(--serif);font-size:1.05rem;margin:0 0 .3rem}
.card .a{margin:0;color:var(--ink-2);font-size:.938rem}
.card .a b{color:var(--ink);font-weight:600}
.cite{display:inline-block;margin-top:.5rem;font-family:var(--mono);font-size:.656rem;
  letter-spacing:.05em;color:var(--ink-3);border:1px solid var(--rule-2);
  border-radius:2px;padding:.12rem .4rem}
.dates{display:grid;gap:0;margin-bottom:1.6rem;background:var(--surface);
  border:1px solid var(--rule);border-radius:4px;overflow:hidden}
.date{display:grid;grid-template-columns:6.5rem 1fr auto;gap:.8rem;align-items:center;
  padding:.7rem 1rem;border-top:1px solid var(--rule)}
.date:first-child{border-top:0}
.date .d{font-family:var(--mono);font-size:.75rem;color:var(--ink-2)}
.date .w{font-size:.938rem}
.date .w small{display:block;color:var(--ink-3);font-size:.813rem}
.countdown{font-family:var(--mono);font-size:.688rem;letter-spacing:.05em;
  padding:.2rem .45rem;border-radius:2px;white-space:nowrap}
.countdown.soon{background:var(--warn-soft);color:var(--warn)}
.countdown.past{background:var(--surface-2);color:var(--ink-3);text-decoration:line-through}
.countdown.ok{background:var(--surface-2);color:var(--ink-3)}
.askbox{background:var(--surface);border:1px solid var(--rule);border-radius:4px;
  padding:1rem;margin-bottom:1rem}
#ask{width:100%;font-family:var(--sans);font-size:.938rem;padding:.6rem .75rem;
  border:1px solid var(--rule-2);border-radius:3px;background:var(--surface-2);color:var(--ink)}
#ask:focus{outline:2px solid var(--accent);outline-offset:1px}
.hint{font-size:.813rem;color:var(--ink-3);margin:.55rem 0 0}
.results{margin:.9rem 0 0;display:grid;gap:.5rem}
.res{border-left:2px solid var(--accent);padding:.45rem 0 .45rem .7rem}
.res .rq{font-weight:600;font-size:.938rem;margin:0}
.res .ra{margin:.15rem 0 0;color:var(--ink-2);font-size:.938rem}
.res .ra b{color:var(--ink)}
.res.text{border-left-color:var(--rule-2)}
.escalate{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;background:var(--accent-soft);
  border:1px solid var(--rule-2);border-radius:4px;padding:.9rem 1rem;margin-bottom:.6rem}
.escalate p{margin:0;flex:1 1 16rem;font-size:.875rem;color:var(--ink-2)}
.escalate p b{color:var(--ink)}
.btn{font-family:var(--mono);font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;
  padding:.55rem .85rem;border-radius:3px;cursor:pointer;white-space:nowrap;
  border:1px solid var(--ink);background:var(--ink);color:var(--paper);
  text-decoration:none;display:inline-flex;align-items:center;gap:.4rem}
.optional{display:flex;flex-wrap:wrap;gap:.7rem;align-items:center;border:1px dashed var(--rule-2);
  border-radius:4px;padding:.8rem 1rem;margin-bottom:1.6rem;opacity:.72}
.optional p{margin:0;flex:1 1 16rem;font-size:.84rem;color:var(--ink-3)}
.btn[disabled]{cursor:not-allowed;background:none;color:var(--ink-3);border-color:var(--rule-2)}
footer{border-top:1px solid var(--rule);padding-top:.9rem;font-size:.813rem;color:var(--ink-3)}
footer p{margin:.35rem 0}
footer b{color:var(--ink-2)}
@media (max-width:34rem){
  .date{grid-template-columns:1fr;gap:.2rem}
  .date .countdown{justify-self:start}
}
"""

# The whole of the page's behaviour. Three jobs: work out how far away each
# date is, switch the answers between the two sides, and search. No network
# calls, no dependencies, nothing that needs a server.
SCRIPT = r"""
(function () {
  var D = window.__CONTRACT__;

  // ---- dates -----------------------------------------------------------
  // Compare date-only values, not timestamps. Parsing "2028-12-31" gives
  // midnight UTC; a reader in IST comparing that against a UTC "now" sees
  // the count off by one for most of the Indian day.
  function today() {
    var n = new Date();
    return Date.UTC(n.getFullYear(), n.getMonth(), n.getDate());
  }
  function daysTo(iso) {
    var p = iso.split("-").map(Number);
    return Math.round((Date.UTC(p[0], p[1] - 1, p[2]) - today()) / 86400000);
  }
  function phrase(n) {
    if (n < 0)   return ["past", n === -1 ? "yesterday" : Math.abs(n) + " days ago"];
    if (n === 0) return ["soon", "today"];
    if (n === 1) return ["soon", "tomorrow"];
    if (n <= 90) return ["soon", "in " + n + " days"];
    if (n < 365) return ["ok", "in " + Math.round(n / 30) + " months"];
    var y = n / 365;
    return ["ok", "in " + (y < 1.5 ? "a year" : Math.round(y) + " years")];
  }
  var MONTH = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"];
  function pretty(iso) {
    var p = iso.split("-");
    return Number(p[2]) + " " + MONTH[Number(p[1]) - 1] + " " + p[0];
  }

  var diary = D.dates.slice().sort(function (a, b) {
    return a.date < b.date ? -1 : 1;
  });
  document.getElementById("dates").innerHTML = diary.map(function (d) {
    var s = phrase(daysTo(d.date));
    return '<div class="date"><span class="d">' + pretty(d.date) + "</span>" +
      '<span class="w">' + d.what +
      (d.note ? "<small>" + d.note + "</small>" : "") + "</span>" +
      '<span class="countdown ' + s[0] + '">' + s[1] + "</span></div>";
  }).join("");

  // ---- side ------------------------------------------------------------
  var side = "customer";
  var segs = document.querySelectorAll(".seg button");
  Array.prototype.forEach.call(segs, function (b) {
    b.addEventListener("click", function () {
      side = b.getAttribute("data-side");
      Array.prototype.forEach.call(segs, function (o) {
        o.setAttribute("aria-pressed", String(o === b));
      });
      document.getElementById("sidenote").textContent =
        "Answers below are written for the " + side + " side.";
      render(document.getElementById("ask").value);
    });
  });

  // ---- search ----------------------------------------------------------
  // Plain token AND-matching over the baked-in answers, with a small
  // synonym map so "get out", "exit" and "cancel" all reach termination.
  var SYN = {
    exit:"terminate", cancel:"terminate", quit:"terminate", leave:"terminate",
    end:"terminate", out:"terminate", notice:"terminate",
    cost:"price", pay:"price", fee:"price", charge:"price", money:"price",
    transfer:"assign", novate:"assign", sell:"assign",
    sue:"liability", damages:"liability", claim:"liability", cap:"liability",
    gdpr:"data", privacy:"data", personal:"data",
    renew:"renewal", rollover:"renewal", extend:"renewal"
  };
  function norm(s) {
    return (s || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/).filter(Boolean)
      .map(function (w) { return SYN[w] || w; });
  }
  var STOP = {the:1,a:1,an:1,is:1,are:1,we:1,i:1,can:1,do:1,to:1,of:1,for:1,
              what:1,who:1,how:1,it:1,this:1,that:1,be:1,our:1,us:1,in:1,on:1};

  var bank = D.qa.map(function (r) {
    return { r: r, hay: norm(r.q + " " + r.a + " " + (r.ref || "")) };
  });
  var clauses = (D.clauses || []).map(function (c) {
    return { c: c, hay: norm(c.heading + " " + c.text) };
  });

  function hits(words, hay) {
    return words.every(function (w) {
      return hay.some(function (h) { return h.indexOf(w) === 0; });
    });
  }

  function card(r) {
    return '<div class="res"><p class="rq">' + r.q + '</p>' +
      '<p class="ra">' + r.a + "</p>" +
      (r.ref ? '<span class="cite">' + r.ref + "</span>" : "") + "</div>";
  }

  function render(q) {
    var out = document.getElementById("results");
    var words = norm(q).filter(function (w) { return !STOP[w] && w.length > 1; });
    if (!words.length) {
      out.innerHTML = bank.slice(0, 3).map(function (b) { return card(b.r); }).join("");
      return;
    }
    var found = bank.filter(function (b) {
      return hits(words, b.hay) &&
             (b.r.side === "both" || b.r.side === side || !b.r.side);
    });
    if (found.length) {
      out.innerHTML = found.slice(0, 6).map(function (b) { return card(b.r); }).join("");
      return;
    }
    // Nothing in the bank. Fall back to the contract text so the floor is
    // always "here is the actual clause", never "no results".
    var inText = clauses.filter(function (c) { return hits(words, c.hay); });
    if (inText.length) {
      out.innerHTML = '<p class="hint">No prepared answer. From the contract text:</p>' +
        inText.slice(0, 4).map(function (c) {
          return '<div class="res text"><p class="rq">' + c.c.heading + "</p>" +
            '<p class="ra">' + c.c.text + "</p>" +
            '<span class="cite">' + c.c.ref + "</span></div>";
        }).join("");
      return;
    }
    out.innerHTML = '<p class="hint">Nothing on this page answers that. ' +
      'Send it to ' + D.escalate.team + ' using the button below — ' +
      'your question travels with the contract reference.</p>';
  }

  var ask = document.getElementById("ask");
  ask.addEventListener("input", function () { render(ask.value); });
  render("");

  // ---- escalation ------------------------------------------------------
  // The point of this button is not the email, it is the context. A legal
  // team gets "quick question about the Acme contract?" all day; this
  // arrives with the reference, the side and the actual question attached.
  document.getElementById("escalate").addEventListener("click", function (e) {
    e.preventDefault();
    var q = ask.value.trim() || "(question)";
    var body = "Question: " + q + "\n\n" +
      "Contract: " + D.title + " (" + D.ref + ")\n" +
      "Parties: " + D.parties.map(function (p) {
        return p.name + " — " + p.role; }).join("; ") + "\n" +
      "I am on the " + side + " side.\n" +
      "Summary: " + location.href + "\n";
    location.href = "mailto:" + D.escalate.to +
      "?subject=" + encodeURIComponent(D.ref + " — contract question") +
      "&body=" + encodeURIComponent(body);
  });

  // ---- audio -----------------------------------------------------------
  var au = document.getElementById("au");
  var btn = document.getElementById("play");
  if (au && btn) {
    var wave = document.querySelector(".wave");
    btn.addEventListener("click", function () {
      if (au.paused) { au.play(); } else { au.pause(); }
    });
    au.addEventListener("play", function () {
      wave.classList.add("on");
      btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>';
    });
    function stopped() {
      wave.classList.remove("on");
      btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
    }
    au.addEventListener("pause", stopped);
    au.addEventListener("ended", stopped);
  }
})();
"""


def bars() -> str:
    h = [40, 70, 95, 55, 80, 35, 65, 90, 45, 72, 30, 60]
    return "".join(f'<i style="height:{n}%"></i>' for n in h)


def page(d: dict, product: str, has_audio: bool) -> str:
    chips = [f'<span class="chip live">{esc(d["status"])}</span>']
    for p in d["parties"]:
        chips.append(f'<span class="chip">{esc(p["name"])} &mdash; {esc(p["role"])}</span>')
    chips.append('<span class="chip">%s &ndash; %s</span>'
                 % (esc(fmt(d["term_start"])), esc(fmt(d["term_end"]))))
    chips.append('<span class="chip ref">%s &middot; executed %s</span>'
                 % (esc(d["ref"]), esc(fmt(d["executed"]))))

    cards = "".join(
        f'<div class="card"><p class="q">{esc(h["q"])}</p>'
        f'<p class="a">{h["a"]}</p>'
        f'<span class="cite">{esc(h["ref"])}</span></div>'
        for h in d["headline"])

    audio = ""
    if has_audio:
        audio = f"""
  <div class="audio">
    <button class="playbtn" id="play" type="button" aria-label="Play the spoken brief">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
    </button>
    <div class="meta">
      <b>Listen &mdash; the whole agreement, spoken</b>
      <span>For the drive to the meeting. Nothing to install.</span>
    </div>
    <div class="wave" aria-hidden="true">{bars()}</div>
    <audio id="au" src="brief.mp3" preload="none"></audio>
  </div>"""

    data = json.dumps({
        "title": d["title"], "ref": d["ref"], "parties": d["parties"],
        "dates": d["dates"], "qa": d["qa"], "clauses": d.get("clauses", []),
        "escalate": d["escalate"],
    }, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="referrer" content="no-referrer">
<title>{esc(d['title'])} &mdash; contract summary</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">

  <header class="masthead">
    <span class="eyebrow">{esc(product)} &middot; summary of the contract in your hand</span>
    <h1>{esc(d['title'])}</h1>
    <div class="idrow">{''.join(chips)}</div>
  </header>

  <div class="sidebar-row">
    <div class="seg" role="group" aria-label="Which side are you on">
      <button type="button" data-side="customer" aria-pressed="true">I'm the customer</button>
      <button type="button" data-side="supplier" aria-pressed="false">I'm the supplier</button>
    </div>
    <span class="sidenote" id="sidenote">Answers below are written for the customer side.</span>
  </div>
{audio}
  <div class="sechead"><h2>Dates that matter</h2><span class="eyebrow">counted from today</span></div>
  <div class="dates" id="dates"></div>

  <div class="sechead"><h2>The five questions</h2><span class="eyebrow">plain language</span></div>
  <div class="qa">{cards}</div>

  <div class="sechead"><h2>Ask something else</h2>
    <span class="eyebrow">{len(d['qa'])} answers on this page</span></div>
  <div class="askbox">
    <input id="ask" type="text" autocomplete="off"
           placeholder="e.g. can we assign this, who owns the data, what notice for a price rise">
    <div class="results" id="results"></div>
    <p class="hint">No prepared answer? The search falls back to the contract text,
      so you always land on the actual clause.</p>
  </div>

  <div class="escalate">
    <p><b>Still not answered?</b> Send it to {esc(d['escalate']['team'])} with the contract
      reference, your side and the question already attached.</p>
    <a class="btn" id="escalate" href="#">Ask your legal contact</a>
  </div>

  <div class="optional">
    <p><b>Ask an approved assistant</b> &mdash; not configured. This page calls nothing by
      default and sends nothing anywhere. Where an organisation already has an approved
      contract assistant, it is enabled with a single configuration value.</p>
    <button class="btn" type="button" disabled>Not configured</button>
  </div>

  <footer>
    <p><b>Why you can see this.</b> The summary discloses nothing beyond the contract you are
      already holding. Access follows the document: deployed inside an organisation this page
      sits in the same SharePoint or CLM location, under the same permissions.</p>
    <p><b>Not advice, and not the agreement.</b> Where the two differ the executed contract
      governs. Illustrative contract &mdash; parties, figures and clause numbers are invented.</p>
  </footer>

</div>
<script>window.__CONTRACT__ = {data};</script>
<script>{SCRIPT}</script>
</body>
</html>
"""


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt(iso: str) -> str:
    y, m, dd = iso.split("-")
    return f"{int(dd)} {MONTHS[int(m) - 1]} {y}"


COVER = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title} - page 1</title>
<style>
  @page {{ size: A4; margin: 0; }}
  body {{ margin:0; font-family:Georgia,serif; color:#111;
         width:210mm; min-height:297mm; padding:28mm 24mm; background:#fff; }}
  .rule {{ border-top:2px solid #111; margin:0 0 10mm; }}
  h1 {{ font-size:22pt; font-weight:400; line-height:1.2; margin:0 0 4mm; }}
  .sub {{ font-size:11pt; color:#444; margin:0 0 14mm; }}
  dl {{ font-size:11pt; line-height:1.7; margin:0 0 16mm; }}
  dt {{ float:left; width:42mm; color:#555; clear:left; }}
  .scan {{ display:flex; gap:7mm; align-items:center; border:1pt solid #bbb;
          padding:6mm; width:max-content; margin-top:6mm; }}
  .scan img {{ width:30mm; height:30mm; }}
  .scan .t {{ font-family:Helvetica,Arial,sans-serif; font-size:10pt;
             line-height:1.45; max-width:72mm; }}
  .scan .t b {{ display:block; font-size:11pt; margin-bottom:1.5mm; }}
  .scan .t span {{ color:#555; }}
  .foot {{ position:absolute; bottom:22mm; font-size:9pt; color:#777; }}
</style></head>
<body>
  <div class="rule"></div>
  <h1>{title}</h1>
  <p class="sub">{type} &middot; {ref}</p>
  <dl>
    <dt>Between</dt><dd>{p0}</dd>
    <dt>and</dt><dd>{p1}</dd>
    <dt>Commencement</dt><dd>{start}</dd>
    <dt>Expiry</dt><dd>{end}</dd>
    <dt>Executed</dt><dd>{executed}</dd>
  </dl>

  <div class="scan">
    <img src="qr.png" alt="">
    <div class="t">
      <b>Read or listen to the summary</b>
      <span>Scan with any phone camera. Plain-language answers, the dates that
      matter, and a spoken brief. No app, no sign-in.</span>
    </div>
  </div>

  <p class="foot">Illustrative document. Parties and figures are invented.</p>
</body></html>
"""


# ---------------------------------------------------------------- build

def build(src: Path, product: str, audio: bool) -> None:
    d = json.loads(src.read_text(encoding="utf-8"))
    out = SITE / d["slug"]
    out.mkdir(parents=True, exist_ok=True)
    print(f"  {src.name}  ->  docs/{d['slug']}/")

    url = BASE.rstrip("/") + "/" + d["slug"] + "/"
    qr_png(url, out / "qr.png")

    has_audio = False
    if audio and d.get("brief"):
        has_audio = say(d["brief"], out / "brief.mp3")

    (out / "index.html").write_text(page(d, product, has_audio), encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

    (out / "cover.html").write_text(COVER.format(
        title=esc(d["title"]), type=esc(d["type"]), ref=esc(d["ref"]),
        p0=esc(f'{d["parties"][0]["name"]} ({d["parties"][0]["role"]})'),
        p1=esc(f'{d["parties"][1]["name"]} ({d["parties"][1]["role"]})'),
        start=esc(fmt(d["term_start"])), end=esc(fmt(d["term_end"])),
        executed=esc(fmt(d["executed"]))), encoding="utf-8")

    print(f"    {len(d['qa'])} answers, {len(d['dates'])} dates, "
          f"audio: {'yes' if has_audio else 'no'}")
    print(f"    {url}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("sources", nargs="*", type=Path)
    ap.add_argument("--name", default=PRODUCT, help="product name shown on the page")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--check-audio", action="store_true",
                    help="say one line and report exactly what fails")
    ap.add_argument("--voices", action="store_true",
                    help="list the English voices available")
    a = ap.parse_args()

    if a.check_audio:
        sys.exit(check_audio())
    if a.voices:
        sys.exit(list_voices())

    srcs = a.sources or sorted(CONTRACTS.glob("*.json"))
    if not srcs:
        sys.exit("no contract records found in contracts/")

    SITE.mkdir(exist_ok=True)
    (SITE / ".nojekyll").touch()
    print(f"Building {len(srcs)} contract(s) as “{a.name}”")
    for s in srcs:
        build(s, a.name, not a.no_audio)

    index = "\n".join(
        f'<li><a href="{json.loads(p.read_text(encoding="utf-8"))["slug"]}/">'
        f'{esc(json.loads(p.read_text(encoding="utf-8"))["title"])}</a></li>'
        for p in srcs)
    (SITE / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Samples</title>"
        "<meta name=robots content=noindex>"
        "<body style='font-family:Georgia,serif;max-width:34rem;margin:3rem auto;padding:0 1rem'>"
        f"<h1 style='font-weight:400'>{esc(a.name)}</h1>"
        "<p>Demonstration pages. Each would normally be reached by scanning the "
        "QR code printed on page 1 of the contract.</p>"
        f"<ul style='line-height:2'>{index}</ul></body>", encoding="utf-8")
    print(f"\nDone. Open {SITE / 'index.html'}")


if __name__ == "__main__":
    main()
