# Scan to Read — contract summaries that reach the person holding the paper

A QR code on page 1 of a contract opens a plain-language summary that can be
read or listened to. No app, no sign-in, no special tools: a phone camera.

## Why

Contracts are negotiated by lawyers and lived with by everybody else. The
person who has to perform the thing — the procurement manager, the site lead,
the account owner — holds a copy they will never read, and nobody re-reads a
signed contract, so renewals pass unnoticed and notice windows close.

## What it produces

For each contract, `docs/<slug>/`:

| file | what it is |
|---|---|
| `index.html` | the summary page: one file, no framework, no build step |
| `summary.json` | the same facts as data |
| `brief.mp3` | the spoken brief |
| `qr.png` | QR code pointing at the page |
| `cover.html` | a mock contract front page carrying the QR, to print |

## Static page, live answers

The page is a static file, but everything relative to today — "in 50 days",
"overdue", the order of the diary — is computed in the reader's browser at
load time from stored ISO dates. A page generated in March still reads
correctly in November. The only reason to regenerate is that the contract
changed.

No server, no API call, nothing phoned home.

## Three tiers, and it never guesses

1. **Five questions** answered up front, in plain language.
2. **Search** over ~20 prepared answers per contract. When nothing matches, it
   falls back to the contract text itself, so the floor is always "here is the
   actual clause", never "no results".
3. **Escalate** to a human, with the contract reference, the reader's side and
   their question already attached — so the question arrives routable.

An approved AI assistant can be wired in as a fourth tier with one config
value. Nothing is called by default.

## Access

Possession of the document is the authorisation: the summary discloses nothing
beyond the contract the reader is already holding. Slugs are opaque, pages are
`noindex`, and in an enterprise deployment the page is generated *into* the
tenant's own SharePoint or CLM location, so it inherits the document's own
permissions. Nothing leaves their estate and there is no new data processor.

## Running it

    pip install qrcode[pil] edge-tts
    python3 generate.py                  # all contracts
    python3 generate.py --no-audio       # skip the spoken brief
    python3 generate.py --name "..."     # product name on the page

Set `BASE` in `generate.py` to the host before printing anything — the QR
encodes it.

Audio uses `edge-tts`, which needs network access to Microsoft's speech
endpoint. Where that is unavailable the page is generated without the player.

## Note

All contracts in `contracts/` are invented. No real client data is used
anywhere in this project.

## Two halves, on purpose

`extract.py` reads a contract and fills in the fact sheet. `generate.py`
renders the fact sheet and can invent nothing.

    contract.pdf  ->  extract.py  ->  contracts/x.json  ->  generate.py  ->  the page

The split is the quality gate. Extraction is probabilistic; rendering is
deterministic. Because the model's whole output is one short JSON file, a
lawyer reviews *that* - in about two minutes - before anything is published.
`extract.py` prints a review sheet and machine-checks what it can: date
formats, missing citations, an unguessable slug, a spoken brief with no
symbols in it, and every cited clause number actually existing in the
document.

No model ships with this. Point it at the endpoint your organisation has
already approved:

    set SARA_PROVIDER=anthropic     (or openai)
    set SARA_MODEL=<model name>
    set SARA_KEY=<your key>

    python extract.py contract.pdf --slug ab12cd34
    python extract.py contract.pdf --dry-run      # show the prompt, call nothing
    python extract.py contracts/x.json --check    # validate a sheet, call nothing

## Publishing

`docs/` is what GitHub Pages serves, so generating and publishing are the
same folder and there is no copy step to forget.

1. Push the repo to `chimade-iot/sara`.
2. Settings -> Pages -> Source: **Deploy from a branch**, branch `main`,
   folder **/docs**.
3. The pages appear at `https://chimade-iot.github.io/sara/<slug>/`, which
   is exactly what the QR codes encode.

Re-run `python generate.py` and push again whenever a contract record
changes. Nothing else needs touching: the countdowns recompute in the
reader's browser, so a page published today still reads correctly months
later without being regenerated.
