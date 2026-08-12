# Progress

Live: https://ahmet-dedeler.github.io/eliminate-cigarettes/
Repo: https://github.com/Ahmet-Dedeler/eliminate-cigarettes
Outreach inbox: nicotine-ad-evidence@agentmail.to
Filing account: recold00masnewski00@gmail.com — this is what `authuser=3`
actually resolves to. Earlier notes here said `potheadache370@` and
`pathetic370@`; both were wrong, never verified against the signed-in banner.
Read the account off the page, not off the URL index.

## Corpus

| | |
|---|---|
| Creatives | 3,906 |
| Nicotine advertisers | 101 |
| Impressions (floor) | 601,967,000 |
| Excluded false positives | 365 creatives / 22 advertisers |
| Source | Google Ads Transparency Center, BigQuery, EEA-only |

Biggest: British American Tobacco Sweden AB, 817 creatives, 480,567,000
impressions floor, still running.

## Legal position

- **Snus ads illegal EEA-wide incl. Sweden.** Dir. 2003/33/EC art. 3(2) reaches
  the internet. Sweden's accession exemption is sale-only, never advertising.
  Sweden also bans it domestically: Lag 2018:2088 ch. 4 s. 1.
- **Google policy does NOT cover tobacco-free nicotine pouches.** "Nicotine"
  appears nowhere in it; it names snus and omits pouches. Claim dropped.
  TikTok and Meta both name pouches expressly.
- **No EU instrument covers pouches at all.** Purely national. Velo reaches
  BE/FR/NL/NO (sale banned) + DK/EE/FI/HR/LU/PL/PT/RO (ads banned).
- Google archive is EEA-only, so AU/IN/BR law cannot apply. TGA plan dead.

## Done

- [x] Harvesters: Google (BigQuery), TikTok (rate-limited)
- [x] Classifier with false-positive exclusions, published
- [x] Advertiser verification via Grok, 68 resolved
- [x] Legality matrix, EU + 7 non-EU jurisdictions
- [x] Policy clause mapping per product category
- [x] Public evidence site on GitHub Pages
- [x] Removal experiment: 40 matched pairs enrolled, baseline captured

## Filing to Google — IN PROGRESS

**The URL param is `?authuser=3`, NOT `/u/3/`** — the `/u/N/` path breaks the
Ads Transparency Center and falls through to a political-ads page.

Channel: https://support.google.com/ads/troubleshooter/4578507
Path: "It violates Google policies" -> "It promotes a restricted product or
service (Alcohol, tobacco, ...)" -> paste creative URL -> Submit.
Confirmation: "Your report has been submitted."

**Filed: 9 of 30** — 7 of them verified against email receipts, 2 not.

### Verify filings against the email receipt, not the page

Google sends a "Your report to Google &lt;case-id&gt;" email per accepted report.
That inbox is the ground truth; the page is not. Search it with:

```
subject:"report to Google" in:anywhere
```

Reconciliation on 2026-08-11: 8 submissions attempted, 7 receipts, 1 explicit
failure. Exact match, so the receipt is reliable as a per-report audit trail.

Three distinct post-submit page states, and only one of them is honest:

| Page shows | Meaning |
|---|---|
| "Your report has been submitted" | accepted |
| form silently resets, no message | **also accepted** — verified against receipts |
| "There were problems sending your form" | rejected, must retry |

The silent reset is the trap: it looks like a failure and is a success.

**The 2 reports logged on 2026-07-31 have no receipt.** Searching that inbox
`in:anywhere` returns 7 emails, all from 2026-08-11. Either they never went
through despite the page saying so, or they were filed under a different
account than the one `authuser=3` resolves to now. Treat both as unconfirmed
and re-file:
- CR12030441792550731777 Skruf Snus AB
- CR02749812069204230145 SNUS VIKINGS LTD

This matters for the result: the "reported on Jul 31, still serving Aug 10"
observation on the Skruf creative rests on a filing that cannot be evidenced.

Verified filed 2026-08-11 (7): CR02812101395782565889, CR16691982691838459905,
CR05976588219498627073, CR01661946812187017217, CR15958555659553734657,
CR03278946198915907585, CR08715792466806046721.

### The "throttle" was a misdiagnosis

Recorded here previously as a hard server-side rate limit after ~2 submissions.
It was not. The Chrome tab had stopped being the **foreground** tab in its
window, so `document.visibilityState` was `hidden` and Chrome silently dropped
the synthesized input events. The form looked broken in exactly the way a
throttle looks: the radio never registers, the sub-form never expands, no error.

Diagnosis is one line, and it is worth running before believing any "the site
is blocking us" story:

```js
({vis: document.visibilityState, focus: document.hasFocus()})
```

With the tab foregrounded the form submitted on the first attempt. So there is
no evidence of any rate limit, and no reason to pace submissions over days.

### Working method

The tab does **not** need to be visible. It can sit hidden in its own
background Chrome window while Ahmet works — input events are delivered to a
hidden tab fine. What a hidden tab does do is throttle rendering, and every
hard part below follows from that.

1. Run it in a dedicated Chrome window so nothing competes for the tab:
   `osascript -e 'tell application "Google Chrome" to make new window'`.
   Its viewport is frozen at whatever size it had when last visible (669px
   here) and will **not** respond to resizing while hidden.
2. Click by **screen coordinate**, not by element ref. Refs carry coordinates
   cached from an earlier read, and a stale ref clicks whatever now occupies
   that spot — one landed on "It's harmful, violent, or dangerous". A
   wrong-category report is worse than no report.
3. **The page anchor-scrolls itself when the sub-form expands, and on a
   throttled tab that lands mid-click.** Once expanded it rests at
   `scrollY = 432` with the restricted-products radio at `(122, 500)`, but
   whether it has finished moving when the click lands is a coin flip. A click
   measured at the pre-shift position selected *sexual content* instead.
4. So don't trust the click — **correct it with the keyboard.** Arrow keys move
   selection within a radiogroup and are position-independent. Click anywhere
   in the group, read back which index is selected, then arrow to index 3:

```js
const rs=[...document.querySelectorAll('input[name=violating_policy]')];
rs.findIndex(r=>r.checked)   // 0 scam 1 violent 2 sexual 3 restricted 4 other
```

5. Verify index 3 **and** the link field, then submit. Never submit on the
   assumption a click worked.
6. Page zoom shortcuts (`cmd+minus`) are blocked by the extension, so shrinking
   the content to avoid scrolling is not an option.

Remaining 27 creative URLs are queued in the DB (`experiment` table,
`arm='reported' AND reported_at IS NULL`).

**Still open:** filing the remaining 27 means holding the foreground tab in
Ahmet's own Chrome window for ~20-30 minutes, which fights with him using the
machine. The Chrome extension also disconnected repeatedly while he was
switching tabs. Needs a window he isn't using, or a stretch of time he isn't.

## Cohort correction

Dropped `mixed_nicotine` from the experiment. Spot-checking BAT Austria's live
creatives showed them to be VELO **nicotine pouch** ads ("Teste jetzt die VELO
Nicotine Pouches"). Google's policy does not cover pouches, and pouch
advertising is lawful in Austria until Feb 2028 — that would have been a losing
report. Cohort is now snus only, 30 reported / 30 control.

## Outreach sent (from nicotine-ad-evidence@agentmail.to)

- Eline Goethals — author of the ASH endgame report
- George Pearson, Truth Initiative — his Nov 2025 essay argues the field can't
  see paid ads; this corpus is the direct answer
- Julia Vassey, USC — built the open-source e-cig CV model; the recall gap here
  is exactly what her classifier would close
- Megan Manning + Chris Bostic, ASH USA

## Findings added since

**Google's removal taxonomy has no tobacco category.** ~11M removals published
with reasons. Alcohol is named (63,627 removals), plus Gambling, Healthcare,
Adult content, Dating, Political. Tobacco appears nowhere — despite being
prohibited outright while alcohol is merely restricted. No tobacco removal
metric exists for anyone to hold Google to.

None of the 3,540 corpus creatives appear in the removed table. Caveat stated
publicly: the corpus is drawn from the live archive so that is partly
definitional. What stands is that these ads ran unimpeded.

Caught and corrected: a first version of that query matched on advertiser ID,
which the removed table does not contain. It could never have matched. Rerun on
creative IDs, with the logic verified against known-removed creatives first.

## Experiment, observation 2 (day 12)

Baseline was 2026-07-31, second observation 2026-08-12. Both arms moved almost
identically:

| | running | stopped | withdrawn |
|---|---|---|---|
| reported (n=30) | 16 | 13 | 1 |
| control (n=30) | 15 | 14 | 1 |

**Nothing has been removed by Google.** Not one creative in either arm appears
in `removed_creative_stats`. The single withdrawal in each arm is an advertiser
ending a campaign, which is exactly the confound the control arm exists to
absorb — and it absorbed it.

This is not yet evidence that reporting does nothing, because only 2 of the 30
were actually reported at baseline. The reported arm is, at this point, 28
creatives that were never reported. The comparison does not mean anything until
the filing backlog clears.

The two that *were* reported, 12 days on:

- CR02749812069204230145 SNUS VIKINGS LTD — **withdrawn**, gone from the live
  archive. Not attributable: it was already `stopped` at baseline, and one
  control withdrew over the same window.
- CR12030441792550731777 Skruf Snus AB — **still running**, `last_shown`
  2026-08-10. Reported to Google on 2026-07-31 and still serving 10 days later.

## In flight
- [ ] File remaining 27 reports (blocked on foreground browser access, above)
- [ ] Third observation once filing completes — that is the first one that can
      actually answer the question
- [ ] TikTok at scale (needs proxy rotation)

## Outreach status

Four emails sent 2026-07-31. As of 2026-08-11: **no replies, no bounces.**
Twelve days of silence. Worth one follow-up before concluding the approach
doesn't work.

## Notes

TikTok library rate limit: ~12 req/IP then multi-minute cooldown. 48 ads
harvested so far. Needs rotation to be useful.
