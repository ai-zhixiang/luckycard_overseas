# hicard.world — Site Chronicle

> Being written down from dictation… shell-era details still waiting for boonxiong2
> Origin: Dad (Shanghai) handed the phone to his son (boonxiong2, Hong Kong) and asked him to help build a website — the son started building, and the first thing he added was the BIOS animation
> Background: Dad built the **domestic version** first — a plain page, one click straight to the main page, no boot animation, UI colors picked by an AI (Adobe-ish look). The son's hicard.world is the **overseas version** — same features, completely different look (XP theme + BIOS boot animation + region detection, code name luckycard_overseas)

## Chapter 0: The empty shell (around 2026-02) — you clicked and got a 404
- The domain was up with no pages at all; every visit returned only a 404
- Dad's requirements → construction begins
- **Tag-team from day one**: the son added the **BIOS boot animation** (the very first feature); Dad **directed an AI** to build the **light-colored main page** — a big **LUCKY** logo centered, with a row of buttons underneath (nobody hand-writes code 😂)
- **Anecdote**: the son never told Dad that the animation was supposed to hand over to the main page → Dad wired it so the animation simply **vanished** when it finished, with nothing behind it (requirements not aligned 😂)
- Afterwards the son decided to rebuild the whole thing as an XP shell (Dad: "pretty cool, keep going")

## Chapter 1: The XP shell takes shape
- **The XP shell was written by an AI (Hermes) at the son's request** — the early session records were lost along with an old API key, so even the AI doesn't remember writing it; this chapter exists so it is never forgotten again 📜
- XP-themed desktop: Start menu / windows / taskbar (xp.js XPShell)
- bios.js: boot & startup + China-visitor notice overlay + BSOD simulation
- The XP look went through **several iterations**
- **Anecdote**: Dad dropped a **flat blue** block in as the desktop wallpaper; the son's inner monologue: "Can't you just go online and find Bliss?!" (the blue sky and grass one came later)
- **Why XP and not 95/98**: he regularly listens to **音MAD** (speech input garbles the word into "音麦"), and all the Windows sounds used in those videos are XP system sounds → after hearing them enough times he settled on XP (Dad's verdict: "pretty cool", approval granted)

## Milestones (traceable from session records; dates still to be filled in)
- [around 2026-06-20] The China-visitor notice overlay was blocking clicks on the Start menu (z-index 200000) — fixed → Start menu usable
- [2026-07] Lucky Card generation (DeepSeek writes poems + Doubao reads images + Seedream stylization)
- [2026-07-21] _Win11LPC v0.2 Chinese-syntax programming language goes live (compiles to C++)
- [2026-08-02] WinDOS.bak.zip uploaded (UEFI Rust bootloader + C++ kernel backup)
- [2026-08] Lucky Point wallet billing ($1 = 100 pts; poem 10 / vision 10 / image 15 / stylize 15; 3 free per IP per day)
- [2026-09-02] Front-end UI locked to English, back-end errors stay Chinese (for debugging), DEV test grant button
- [2026-09] Chinese Culture desktop app (43 rotating themed days)
- [2026-09-11] Crypto Challenge wall upgraded: public leaderboard + solver certificate + Lucky Points paid on solve (wallet credit for logged-in users only, guests can still rank) + context-aware/idle Clippy + `tools/make_challenge.py` authoring script

## Still to fill in
- The exact date of the empty-shell era, and what the first BIOS animation looked like
- The day the XP shell was thought up, and how
- Other important version milestones

---
*This is the English edition. The Chinese original is the file `/static/website-history.md` — use the "Switch Language" item in the menu bar to read it.*
