#!/usr/bin/env python3
"""
Render the same passage in several voices, so a human can pick one.

    python3 try_voices.py                 # the shortlist, from the MSA brief
    python3 try_voices.py --all-en        # every English voice the service has
    python3 try_voices.py --list          # just list voices, synthesise nothing
    python3 try_voices.py --seconds 25    # how much of the brief to render

Writes voice-samples/<voice>.mp3 and an index.html that plays them one after
another, so the comparison is made on the same words at the same pace rather
than on three different scripts recorded on three different days.

Choosing a voice is a judgement nobody can make from a spec sheet, and the
one argument that is not taste: an Indian English voice pronounces Bhiwandi,
Hosur, crore and lakh correctly, and most others do not. Listen for those
before you decide on the accent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).parent
OUT = ROOT / "voice-samples"

# A starting point, not a recommendation. en-IN first because of the
# place names and the crore/lakh problem; the rest are there to be
# ruled out quickly.
SHORTLIST = [
    "en-IN-PrabhatNeural",      # current
    "en-IN-NeerjaNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "en-GB-ThomasNeural",
    "en-AU-WilliamNeural",
    "en-US-GuyNeural",
]


def passage(record: Path, seconds: int) -> str:
    """The opening of a real brief, cut to roughly N seconds of speech."""
    d = json.loads(record.read_text(encoding="utf-8"))
    words = d["brief"].split()
    return " ".join(words[:int(seconds * 150 / 60)])


async def available() -> list[dict]:
    import edge_tts
    return await edge_tts.list_voices()


async def render(text: str, voices: list[str], rate: str) -> list[str]:
    import edge_tts
    sys.path.insert(0, str(ROOT))
    from generate import normalise_mp3
    done = []
    for v in voices:
        out = OUT / f"{v}.mp3"
        try:
            await edge_tts.Communicate(text, v, rate=rate).save(str(out))
        except Exception as e:
            print(f"  {v:<26} failed: {type(e).__name__}: {e}")
            continue
        normalise_mp3(out)
        kb = out.stat().st_size / 1024
        print(f"  {v:<26} {kb:>6.0f} KB")
        done.append(v)
    return done


def index(voices: list[str], text: str) -> None:
    rows = "".join(
        f'<li><b>{v}</b><audio controls preload="none" src="{v}.mp3"></audio></li>'
        for v in voices)
    (OUT / "index.html").write_text(f"""<!doctype html><meta charset="utf-8">
<title>Voice samples</title><meta name="robots" content="noindex">
<style>body{{font-family:Georgia,serif;max-width:46rem;margin:3rem auto;
padding:0 1rem;color:#202e4c;background:#e0f3fa}}
h1{{font-weight:400}}p.t{{background:#fff;border:1px solid #aed6e8;
border-radius:4px;padding:1rem;font-size:.95rem;line-height:1.5}}
ul{{list-style:none;padding:0}}li{{background:#fff;border:1px solid #cbe6f1;
border-radius:4px;padding:.7rem 1rem;margin-bottom:.5rem;display:flex;
align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
b{{font-family:ui-monospace,Menlo,monospace;font-size:.85rem}}</style>
<h1>Same words, different voices</h1>
<p class="t">{text}</p><ul>{rows}</ul>
<p style="font-size:.85rem;color:#4a5878">Listen for the place names and for
crore and lakh. Then set VOICE in generate.py, or add "voice" to a contract
record to use a different one for that contract.</p>""", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--record", type=Path,
                    default=ROOT / "contracts" / "msa-0418.json")
    ap.add_argument("--seconds", type=int, default=25)
    ap.add_argument("--rate", default="+4%")
    ap.add_argument("--all-en", action="store_true",
                    help="every English voice, not the shortlist")
    ap.add_argument("--list", action="store_true",
                    help="list the English voices and exit")
    a = ap.parse_args()

    try:
        import edge_tts                                   # noqa: F401
    except ImportError:
        sys.exit("needs edge-tts:  pip install edge-tts")

    if a.list or a.all_en:
        try:
            vs = asyncio.run(available())
        except Exception as e:
            sys.exit(f"could not reach the speech service: "
                     f"{type(e).__name__}: {e}")
        en = sorted((v for v in vs if v["Locale"].startswith("en-")),
                    key=lambda v: v["ShortName"])
        if a.list:
            for v in en:
                print(f"  {v['ShortName']:<30} {v['Gender']:<7} {v['Locale']}")
            print(f"\n{len(en)} English voices")
            return
        voices = [v["ShortName"] for v in en]
    else:
        voices = SHORTLIST

    text = passage(a.record, a.seconds)
    OUT.mkdir(exist_ok=True)
    print(f"{len(voices)} voice(s), {len(text.split())} words, rate {a.rate}\n")
    done = asyncio.run(render(text, voices, a.rate))
    if not done:
        sys.exit("\nnothing rendered")
    index(done, text)
    print(f"\nOpen {OUT / 'index.html'} and listen to them back to back.")


if __name__ == "__main__":
    main()
