# Progress

Live: https://ahmet-dedeler.github.io/eliminate-cigarettes/
Repo: https://github.com/Ahmet-Dedeler/eliminate-cigarettes
Outreach inbox: nicotine-ad-evidence@agentmail.to
Filing account: potheadache370@gmail.com (secondary Google user, not the main one)

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

Account: pathetic370@gmail.com. **The URL param is `?authuser=3`, NOT `/u/3/`** —
the `/u/N/` path breaks the Ads Transparency Center and falls through to a
political-ads page.

Channel: https://support.google.com/ads/troubleshooter/4578507
Path: "It violates Google policies" -> "It promotes a restricted product or
service (Alcohol, tobacco, ...)" -> paste creative URL -> Submit.
Confirmation: "Your report has been submitted."

**Filed: 2 of 30.**
- CR12030441792550731777 Skruf Snus AB
- CR02749812069204230145 SNUS VIKINGS LTD

**Blocked on a hard throttle.** The form accepts ~2 submissions per session,
then the sub-form silently stops expanding on selecting option 1 — no error,
it just never renders. Retried across ~40 minutes and several fresh loads; still
throttled. Needs pacing over hours or days, not a tighter loop.

Deliberately NOT worked around by spreading submissions across Ahmet's other
Google accounts. The rate limit is a platform control and evading it would
undermine the credibility the whole project depends on.

Remaining 28 creative URLs are queued in the DB (`experiment` table,
`arm='reported' AND reported_at IS NULL`).

UI notes: clicking the radio's *label* is what works; clicking the aria radio
node does nothing. Refs renumber on every read, so each report needs
find -> click -> find -> fill -> submit.

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

## In flight
- [ ] Re-check loop to measure removal rate vs control
- [ ] TikTok at scale (needs proxy rotation)

## Notes

TikTok library rate limit: ~12 req/IP then multi-minute cooldown. 48 ads
harvested so far. Needs rotation to be useful.
