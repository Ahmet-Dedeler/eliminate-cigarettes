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

Blocked: the form stopped expanding after 2 submissions in quick succession.
Looks like throttling. Retry with spacing.

UI notes: clicking the radio's *label* is what works; clicking the aria radio
node does nothing. Refs renumber on every read, so each report needs
find -> click -> find -> fill -> submit.

## Cohort correction

Dropped `mixed_nicotine` from the experiment. Spot-checking BAT Austria's live
creatives showed them to be VELO **nicotine pouch** ads ("Teste jetzt die VELO
Nicotine Pouches"). Google's policy does not cover pouches, and pouch
advertising is lawful in Austria until Feb 2028 — that would have been a losing
report. Cohort is now snus only, 30 reported / 30 control.

## In flight
- [ ] Re-check loop to measure removal rate vs control
- [ ] TikTok at scale (needs proxy rotation)

## Notes

TikTok library rate limit: ~12 req/IP then multi-minute cooldown. 48 ads
harvested so far. Needs rotation to be useful.
