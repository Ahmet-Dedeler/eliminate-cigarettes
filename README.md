# eliminate-cigarettes

Continuous surveillance of tobacco and nicotine advertising, built from the ad
archives platforms are legally required to publish.

## Why this exists

The tobacco endgame report ASH USA published in May 2026 argues the bottleneck
is not public opinion — 72% already support phasing out cigarettes — but
capacity. Tobacco control receives 0.3% of global health aid to fight a $965bn
industry.

Meanwhile there is a data source almost nobody is using. Article 39 of the EU
Digital Services Act requires very large platforms to publish a public,
queryable archive of every ad they serve. Those same platforms ban nicotine
advertising outright. So the archives are, in effect, the platforms publishing
evidence of their own policy failures — and as of this writing exactly one
peer-reviewed tobacco study has ever used one.

Everyone else in this field attacks the hard surface: organic and influencer
content on gated platforms. That work matters and is much harder. The paid-ad
surface is open, structured, updated daily, and unwatched. Notably, Vital
Strategies' Canary — the only continuous tobacco marketing monitor in existence
— explicitly excludes paid advertising from its methodology.

## What's here

```
src/tiktok_harvest.py    TikTok Commercial Content Library harvester
src/google_harvest.py    Google Ads Transparency Center harvester (BigQuery)
src/evidence.py          Corpus -> evidence packets with policy citations
data/ads.db              SQLite corpus
evidence/                Generated reports
```

## Current state

Google harvester works and is the workhorse: 3,905 tobacco/nicotine creatives
from 123 advertisers, 1,124 of them shown in the last 60 days. Fifteen are
subsidiaries of Big Tobacco — British American Tobacco, Japan Tobacco, Imperial
Tobacco — advertising across up to 32 regions.

TikTok harvester works but is rate-limited to roughly 12 requests per IP before
a multi-minute cooldown. A full sweep needs proxy rotation. The archive is large
(18,998 ads match "vape" in France alone), so this is worth doing properly.

Meta is deliberately not implemented. Meta retains no archive for commercial
ads — only political and social-issue ads are kept — so paused ads vanish and
the surface is not observable this way.

## Running it

```bash
python3 src/google_harvest.py --limit 50000
python3 src/evidence.py
```

The Google harvester needs a billing-enabled GCP project. The table is ~146 GB
and BigQuery bills roughly $0.73/TB scanned, so queries select narrowly.

```bash
python3 src/tiktok_harvest.py --regions FR,DE,GB --max-per-query 200
```

## Precision over recall, deliberately

This produces accusatory output about named companies, so the matching is
tuned to avoid false positives even at the cost of missing real ones.

Advertisers are matched on their **registered legal name**, not on creative
content. Known collisions are excluded by hand — for instance *Philip Morris &
Son* is a countrywear retailer in Hereford with no connection to Philip Morris
International, and naming them would be defamatory.

The consequence is low recall. Any advertiser whose registered name doesn't
name the product is invisible to this method, which is probably most of the
grey market. Closing that gap means classifying creative content, and that
should not ship until its error rate is measured.

## What this does not do

It does not file anything. Generating an evidence packet and submitting it to a
regulator are separate steps, and submission is a human decision.

## Where complaints would go

Researched but not acted on:

- **UK ASA** — ruled out, and it is worth saying why. The ASA looked like the
  strongest single lever: one complaint can trigger action, and ASH, STOP and
  CTFK jointly got BAT banned from Instagram e-cigarette promotion in 2019. But
  the ASA's remit is advertising addressed to UK consumers, and **this corpus
  contains zero creatives served to GB.** Not few — none.

  The trap was that UK-*registered* advertisers are all over the corpus: Velo
  Marketing Limited (476 creatives), SNUS VIKINGS LTD (39), even Imperial
  Tobacco Holdings (2007) Limited. Every one of them serves into EEA states and
  Turkey, never into the UK. Advertiser HQ is not ad reach, and reading the
  first as the second would have produced a complaint about ads that never
  appeared in the country. Google's DSA archive covers the EEA because the DSA
  is EU law; post-Brexit the UK simply is not in it.
- **FDA CTP** — Form 3779, open to anyone, but the entire national public
  complaint channel handles ~6,000 reports/year and follow-through is weak
  (43% of warned retailers still sold the flagged products).
- **EU DSA Article 22 trusted flagger** — status granted by a national Digital
  Services Coordinator, EU-based entities only, covers Meta/TikTok/YouTube
  EU-wide. There is currently **no tobacco or public-health trusted flagger
  among the 70+ designated.** That slot is empty.

## Sources

- ASH USA, *Tobacco Endgame Report*, May 2026
- Google Ads policy: "Ads for tobacco or any products containing tobacco are
  not allowed" — https://support.google.com/adspolicy/answer/16489929
- TikTok ad policy: "We do not allow ad content and landing pages to show,
  promote, or sell tobacco, nicotine, or related products" —
  https://ads.tiktok.com/help/article/tiktok-ads-policy-dangerous-products-or-services
