# Sāra: the contract, said plainly

**Shailendra Chimade** · solo entry · RISE Legal India 2026

## The problem

Contracts are negotiated by lawyers and then lived with by everyone else.

The person who has to perform an agreement is rarely the person who reviewed it. A procurement manager, a site lead, an account owner. They hold a copy they will never read, and almost nobody goes back to a contract once it has been signed. Notice windows close without anyone noticing. Agreements renew themselves for another year. An obligation surfaces only when something has already gone wrong.

Working in contract operations I keep running into the same thing. The information is not missing. It sits in the document, in the drive, in the CLM. It just never reaches the person who needs it at the moment they need it.

## Who it affects

The business owner of the contract, rather than the lawyer who reviewed it. And the legal team that person interrupts. *"Quick question about the Acme contract?"* arrives with no reference, no clause, and nothing anyone can route.

## How it works

A QR code is printed on page 1 of the contract. Scan it with a phone camera and a plain language summary opens: what the agreement does, the dates that matter counted from today, and a spoken brief for the drive to a meeting. No app, no sign-in, nothing to install. **If you are holding the contract, you are already authorised to read its summary.**

The page answers in three tiers and never guesses. Five questions are answered up front. A search runs across prepared answers and falls back to the contract's own clause text, so the floor is always the real provision rather than *no results*. If none of that helps, one tap sends the question to a lawyer with the contract reference, the clause and the question already attached.

Underneath are two scripts, kept apart on purpose. **extract.py** reads the contract and produces a short fact sheet. That step is probabilistic, so a person checks the fact sheet, which takes about two minutes. **generate.py** renders it and can invent nothing. The review sits between them.

What gets published is a static page. It calls nothing and sends nothing. It recalculates its own dates in the reader's browser, so a page built in March still reads correctly in November. Inside an organisation the page is generated into the SharePoint or CLM folder where the contract already lives, inherits that document's permissions, and adds no new data processor.

The page carries a panel for an approved contract assistant such as Factor*AI*, which would take the questions the prepared set does not cover. It is built and capable, but left switched off here: this demonstration is hosted on public GitHub Pages, and a live model call did not belong in it. Turning it on inside an organisation is a single configuration value, pointing at an assistant that organisation has already cleared.

## What difference it makes

Dates get seen before they pass. The subscription sample opens with an assurance report that is already 44 days overdue, which no PDF will ever tell you. Questions reach legal in a form someone can act on. A non-lawyer gets a usable answer without a licence, a login, or any training at all.

## See it, by scanning from this page

Each code belongs to one contract, the same way it would on paper. Scanning from a screen works.
