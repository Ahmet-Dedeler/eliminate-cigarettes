"""
Which rule does a given ad actually breach?

Two separate questions, deliberately never merged:

  1. Does it breach the PLATFORM'S advertising policy? A contract question.
     Remedy: the ad comes down.
  2. Is it UNLAWFUL where it ran? A legal question, jurisdiction by jurisdiction.
     Remedy: a regulator acts, and penalties can be severe.

Conflating the two is how a complaint gets dismissed, so each claim carries its
own citation and each is asserted only where it actually holds.

The single most important finding encoded here: **Google's advertising policy
does not cover tobacco-free nicotine pouches.** The word "nicotine" appears
nowhere in it. The policy enumerates "Cigarettes, cigars, snus, chewing tobacco,
rolling tobacco, pipe tobacco" -- naming the tobacco-containing oral product
while omitting the tobacco-free one. Under expressio unius that omission argues
against coverage. Citing Google's tobacco clause against Velo or ZYN is a claim
that loses. TikTok and Meta both name nicotine pouches expressly, so the same
ad breaches their policies and not Google's.

Policy text retrieved 2026-07-31. Google's help pages carry no revision date,
so citations are dated by retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

RETRIEVED = "2026-07-31"


class Coverage(str, Enum):
    COVERED = "covered"        # named or unambiguously within the clause
    AMBIGUOUS = "ambiguous"    # arguable, do not lead with it
    NOT_COVERED = "not_covered"  # the text does not reach this product


@dataclass(frozen=True)
class PolicyClaim:
    platform: str
    coverage: Coverage
    clause: str
    url: str
    note: str = ""


# ---------------------------------------------------------------------------
# Platform advertising policies, per product category.
# ---------------------------------------------------------------------------

_G_TOBACCO = ("Ads for tobacco or any products containing tobacco are not "
              "allowed.")
_G_SIMULATE = ("Ads for products designed to simulate tobacco smoking are not "
               "allowed.")
_G_URL = "https://support.google.com/adspolicy/answer/16489929"

_TT_CLAUSE = ("We do not allow ad content and landing pages to show, promote, "
              "or sell tobacco, nicotine, or related products.")
_TT_URL = ("https://ads.tiktok.com/help/article/"
           "tiktok-ads-policy-dangerous-products-or-services")

_META_CLAUSE = ("Ads must not promote the sale or use of tobacco or nicotine "
                "products and related paraphernalia.")
_META_URL = ("https://transparency.meta.com/policies/ad-standards/"
             "restricted-goods-services/tobacco-related-products/")

PLATFORM_POLICY: dict[str, dict[str, PolicyClaim]] = {
    "combustible_tobacco": {
        "google": PolicyClaim("Google Ads", Coverage.COVERED, _G_TOBACCO, _G_URL,
                              "'Cigarettes, cigars' named in the examples."),
        "tiktok": PolicyClaim("TikTok Ads", Coverage.COVERED, _TT_CLAUSE, _TT_URL),
        "meta": PolicyClaim("Meta Ads", Coverage.COVERED, _META_CLAUSE, _META_URL),
    },
    "snus_oral_tobacco": {
        "google": PolicyClaim("Google Ads", Coverage.COVERED, _G_TOBACCO, _G_URL,
                              "'snus' is named outright in the policy examples."),
        "tiktok": PolicyClaim("TikTok Ads", Coverage.COVERED, _TT_CLAUSE, _TT_URL),
        "meta": PolicyClaim("Meta Ads", Coverage.COVERED, _META_CLAUSE, _META_URL),
    },
    "nicotine_pouch": {
        # The important one. Do not assert a Google breach for this category.
        "google": PolicyClaim(
            "Google Ads", Coverage.NOT_COVERED, _G_TOBACCO, _G_URL,
            "A tobacco-free pouch contains no tobacco, is not a component part "
            "of a tobacco product, and does not simulate smoking. Google's "
            "policy never uses the word 'nicotine' and names snus but not "
            "tobacco-free pouches. Enforcement practice may differ from the "
            "text, but the text does not support this claim."),
        "tiktok": PolicyClaim(
            "TikTok Ads", Coverage.COVERED, _TT_CLAUSE, _TT_URL,
            "'nicotine pouches' enumerated by name; the operative sentence is "
            "disjunctive ('tobacco, nicotine, or related products')."),
        "meta": PolicyClaim(
            "Meta Ads", Coverage.COVERED, _META_CLAUSE, _META_URL,
            "'Nicotine pouches' appears as its own bullet in the guidelines."),
    },
    "vape_ends": {
        "google": PolicyClaim("Google Ads", Coverage.COVERED, _G_SIMULATE, _G_URL,
                              "'electronic cigarettes, e-cigarettes' named."),
        "tiktok": PolicyClaim("TikTok Ads", Coverage.COVERED, _TT_CLAUSE, _TT_URL),
        "meta": PolicyClaim("Meta Ads", Coverage.COVERED, _META_CLAUSE, _META_URL),
    },
    "heated_tobacco": {
        "google": PolicyClaim("Google Ads", Coverage.AMBIGUOUS, _G_TOBACCO, _G_URL,
                              "'heated tobacco' is not enumerated. Coverage is "
                              "inferred: the consumable contains tobacco, and "
                              "the device is a component part. Sound, but "
                              "inference rather than an express example."),
        "tiktok": PolicyClaim("TikTok Ads", Coverage.COVERED, _TT_CLAUSE, _TT_URL),
        "meta": PolicyClaim("Meta Ads", Coverage.COVERED, _META_CLAUSE, _META_URL,
                            "Meta names heated tobacco products expressly."),
    },
    # An advertiser selling across categories breaches on its strongest category.
    "mixed_nicotine": {
        "google": PolicyClaim("Google Ads", Coverage.COVERED, _G_TOBACCO, _G_URL,
                              "Advertiser markets tobacco-containing products."),
        "tiktok": PolicyClaim("TikTok Ads", Coverage.COVERED, _TT_CLAUSE, _TT_URL),
        "meta": PolicyClaim("Meta Ads", Coverage.COVERED, _META_CLAUSE, _META_URL),
    },
}


# ---------------------------------------------------------------------------
# National law. Only jurisdictions where the research established a specific
# instrument are listed; silence here means "not established", never "lawful".
#
# Compiled 2026-07-31 from primary instruments where retrievable. Entries
# flagged uncertain are excluded from filing-grade output.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LegalClaim:
    country: str
    sale_banned: bool
    ad_banned: bool
    instrument: str
    note: str = ""
    uncertain: bool = False


AU = "Australia"
IN_ = "India"
BR = "Brazil"
TR = "Turkey"
EEA = "EU / EEA"

# ---------------------------------------------------------------------------
# EU-level instruments. These matter most, because Google's DSA ad archive is
# EEA-only: no creative in this corpus reaches Australia, India, Brazil or the
# United States, so their law is irrelevant to what we can actually see.
#
# The structural fact that drives everything: Directive 2003/33/EC art. 2
# defines a tobacco product as one "intended to be smoked, sniffed, sucked or
# chewed" and "made, even partly, of tobacco". Tobacco-FREE nicotine pouches
# contain no tobacco and fall entirely outside it. TPD art. 20(5) was enacted to
# close that gap for e-cigarettes only. Nothing at EU level closes it for
# pouches, so pouch advertising law is purely national.
# ---------------------------------------------------------------------------

_ART_3_2 = ("Directive 2003/33/EC art. 3(2): advertising not permitted in the "
            "press 'shall not be permitted in information society services' "
            "-- i.e. the prohibition expressly reaches the internet")

EU_LAW: dict[str, list[LegalClaim]] = {
    "snus_oral_tobacco": [
        LegalClaim(
            EEA, True, True,
            _ART_3_2 + "; Directive 2014/40/EU art. 17 (sale)",
            "Snus is a tobacco product under Directive 2003/33/EC art. 2 -- it "
            "is sucked and made of tobacco -- so the internet advertising "
            "prohibition applies across the EEA. Sweden's exemption (Art. 151 "
            "and Annex XV ch. X of the 1994 Act of Accession, cross-referenced "
            "by TPD art. 17) is a placing-on-the-market derogation ONLY. It "
            "creates no parallel licence to advertise. Sweden separately bans "
            "snus advertising in domestic law at Lag (2018:2088) ch. 4 s. 1, "
            "with only a narrow point-of-sale exception at ch. 4 s. 2."),
    ],
    "combustible_tobacco": [
        LegalClaim(EEA, False, True,
                   _ART_3_2 + "; art. 4 (radio); art. 5 (cross-border sponsorship)"),
    ],
    "heated_tobacco": [
        LegalClaim(EEA, False, True,
                   _ART_3_2 + "; Delegated Directive (EU) 2022/2100",
                   "Heated tobacco consumables contain tobacco and are "
                   "therefore tobacco products under art. 2."),
    ],
    "vape_ends": [
        LegalClaim(EEA, False, True,
                   "Directive 2014/40/EU (TPD) art. 20(5): commercial "
                   "communications for e-cigarettes and refill containers "
                   "prohibited in information society services, the press and "
                   "radio; Directive 2010/13/EU (AVMSD) art. 9(1)(d)",
                   "Art. 20(5) exists precisely because 2003/33/EC does not "
                   "reach nicotine products containing no tobacco."),
    ],
    # Deliberately absent: nicotine_pouch. No EU instrument covers it.
}

# National pouch rules, since EU law is silent. Sale bans first.
POUCH_SALE_BANNED = {
    "BE": "Arrete royal of 14 March 2023, in force 1 October 2023",
    "NL": "Tabaks- en rookwarenwet amendment, in force 1 January 2025 "
          "(Stb. 2024, 89 and 378)",
    "FR": "Decret n. 2025-898 of 5 September 2025; sale prohibited from "
          "1 April 2026. The Conseil d'Etat suspension of 22 December 2025 "
          "touched only manufacture, production and export -- the sale ban "
          "stands",
    "NO": "Approval regime for novel nicotine products under the 2021 "
          "tobacco-substitute regulations; no product has been approved. "
          "Advertising separately banned by Tobakksskadeloven s. 22, which "
          "expressly extends to tobacco surrogates and nicotine-free products",
}

# Pouch advertising bans, where sale itself remains lawful.
POUCH_AD_BANNED = {
    "DK": "Lov om tobaksvarer m.v. (LBK 1161/2024), 'tobakssurrogater'",
    "EE": "Tubakaseadus, 'tobacco-resembling products'",
    "FI": "Tupakkalaki: marketing and display ban",
    "HR": "NN 98/2025 of 4 July 2025, arts. 22-23",
    "LU": "Loi n. 8333, adopted 23 October 2025, in force 1 January 2026",
    "PL": "Dz.U. 2025 poz. 427 and Dz.U. 2025 poz. 799",
    "PT": "Framework approved 7 May 2026, including influencer marketing "
          "(decree-law number not yet published)",
    "RO": "Legea 232/2024 of 25 July 2024",
}

# Where pouch advertising is lawful today, so no claim is made.
POUCH_AD_LAWFUL = {
    "SE": "Lawful but restricted -- Lag (2022:1257) ss. 9-12 require "
          "'sarskild mattfullhet'; TV and radio banned, online permitted",
    "ES": "Draft Real Decreto TRIS-notified in 2025 but not adopted",
    "GR": "No instrument identified",
    "MT": "Essentially unregulated; only an excise measure (LN 38/2026)",
    "CZ": "Not specifically restricted for pouches",
    "AT": "Advertising lawful until the phased ban completes in February 2028",
    "CH": "Restricted by channel under TabPG art. 18, not banned",
}

NATIONAL_LAW: dict[str, list[LegalClaim]] = {
    "snus_oral_tobacco": [
        LegalClaim(AU, True, True,
                   "Consumer Protection Notice No. 10 of 1991, given effect "
                   "under Australian Consumer Law s.114(1)(a) (Competition and "
                   "Consumer Act 2010 (Cth) Sch. 2)",
                   "Commercial supply of oral snuff/snus banned since 1991."),
        LegalClaim(BR, True, True,
                   "Lei 9.294/1996 (as amended by Lei 12.546/2011); ANVISA "
                   "mandatory product registration under Lei 9.782/1999",
                   "No snus product holds ANVISA registration, so sale is "
                   "unlawful by default rather than by a named prohibition.",
                   uncertain=True),
    ],
    "nicotine_pouch": [
        LegalClaim(AU, True, True,
                   "Therapeutic Goods Act 1989 (Cth); Poisons Standard "
                   "Schedule 4 reclassification (Jan 2026); TGA closure of all "
                   "remaining access pathways effective 24 July 2026",
                   "As of 24 July 2026 there is no lawful pathway to supply or "
                   "import nicotine pouches in Australia."),
    ],
    "vape_ends": [
        LegalClaim(AU, False, True,
                   "Public Health (Tobacco and Other Products) Act 2023 (Cth) "
                   "ss. 42-43 (e-cigarette advertising), ss. 65-66 (sponsorship)",
                   "Sale is lawful only through pharmacies; advertising is "
                   "prohibited outright."),
        LegalClaim(IN_, True, True,
                   "Prohibition of Electronic Cigarettes Act 2019 (PECA), "
                   "s. 3(d) definition; production, sale, storage and "
                   "advertisement all prohibited"),
        LegalClaim(BR, True, True,
                   "ANVISA RDC no 855/2024 (in force 2 May 2024), which revoked "
                   "and replaced RDC no 46/2009",
                   "Bans manufacture, import, commercialisation, distribution "
                   "and advertising."),
        LegalClaim(TR, True, True,
                   "Law No. 4207 arts. 2(6) and 3; Presidential Decree No. 2149 "
                   "(Resmi Gazete No. 31050, 25 Feb 2020)",
                   "Import banned by decree; advertising banned by statute.",
                   uncertain=True),
    ],
    "heated_tobacco": [
        LegalClaim(IN_, True, True,
                   "Prohibition of Electronic Cigarettes Act 2019 (PECA), "
                   "s. 3(d), which names 'Heat Not Burn Products' expressly"),
        LegalClaim(AU, True, True,
                   "Customs (Prohibited Imports) Regulations 1956 reg. 5A; TGA "
                   "final decision declining to amend the Poisons Standard",
                   uncertain=True),
    ],
    "combustible_tobacco": [
        LegalClaim(AU, False, True,
                   "Public Health (Tobacco and Other Products) Act 2023 (Cth) "
                   "ss. 19-20 (advertising), ss. 38-39 (sponsorship)"),
        LegalClaim(IN_, False, True,
                   "Cigarettes and Other Tobacco Products Act 2003 (COTPA) s. 5"),
        LegalClaim(BR, False, True,
                   "Lei 9.294/1996 art. 3, as amended by Lei 12.546/2011",
                   "All advertising banned except point-of-sale display."),
        LegalClaim(TR, False, True,
                   "Law No. 4207 art. 3, as amended by Law No. 7151 (2018)"),
    ],
}

# Regions where a product is lawful to sell and advertise, so no claim is made.
# Sweden's snus exemption was negotiated in its 1995 EU accession treaty and is
# the reason a large share of this corpus is lawful where it ran.
LAWFUL_EXCEPTIONS = {
    ("snus_oral_tobacco", "SE"): (
        "Snus is lawful to sell in Sweden under its 1995 EU accession "
        "exemption from the oral tobacco ban in Directive 2014/40/EU art. 17."),
    ("snus_oral_tobacco", "NO"): (
        "Snus is lawful in Norway, which is in the EEA but not the EU and is "
        "not bound by the Tobacco Products Directive's oral tobacco ban."),
}


def platform_claim(category: str, platform: str = "google") -> PolicyClaim | None:
    return PLATFORM_POLICY.get(category, {}).get(platform)


def legal_claims(category: str, filing_grade: bool = True) -> list[LegalClaim]:
    """EU-level claims first -- they are the ones this corpus can support."""
    claims = EU_LAW.get(category, []) + NATIONAL_LAW.get(category, [])
    return [c for c in claims if not (filing_grade and c.uncertain)]


def pouch_assessment(regions: list[str]) -> dict:
    """Nicotine pouches have no EU rule, so status is country by country."""
    rs = set(regions)
    return {
        "sale_banned": {r: POUCH_SALE_BANNED[r] for r in sorted(rs & POUCH_SALE_BANNED.keys())},
        "ad_banned": {r: POUCH_AD_BANNED[r] for r in sorted(rs & POUCH_AD_BANNED.keys())},
        "lawful": {r: POUCH_AD_LAWFUL[r] for r in sorted(rs & POUCH_AD_LAWFUL.keys())},
    }


# Which region codes put an advertiser inside each jurisdiction's reach. A law
# only bites if the ad actually served there, and Google's archive is EEA-only,
# so most non-EU entries below can never match on this corpus. Keeping them
# costs nothing and makes the omission explicit rather than accidental.
EEA_CODES = {
    "EEA", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
    "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO",
    "SK", "SI", "ES", "SE", "IS", "LI", "NO",
    # French overseas departments, which are part of the EU customs territory
    "MQ", "RE", "GP", "GF", "MF", "YT",
}
JURISDICTION_CODES = {
    EEA: EEA_CODES,
    "Turkey": {"TR"},
    "Australia": {"AU"},
    "India": {"IN"},
    "Brazil": {"BR"},
}


def applicable_claims(category: str, regions: list[str],
                      filing_grade: bool = True) -> list[LegalClaim]:
    """Only claims for jurisdictions the ad actually reached."""
    rs = set(regions)
    out = []
    for c in legal_claims(category, filing_grade=filing_grade):
        codes = JURISDICTION_CODES.get(c.country)
        if codes is None or (rs & codes):
            out.append(c)
    return out


def assess(category: str, regions: list[str], platform: str = "google") -> dict:
    """Return the defensible claims for one advertiser."""
    pc = platform_claim(category, platform)
    lawful_here = [
        (r, LAWFUL_EXCEPTIONS[(category, r)])
        for r in regions if (category, r) in LAWFUL_EXCEPTIONS
    ]
    result = {
        "platform_policy": pc,
        "platform_breach": bool(pc and pc.coverage == Coverage.COVERED),
        "legal_claims": applicable_claims(category, regions),
        "lawful_exceptions": lawful_here,
    }
    if category == "nicotine_pouch":
        result["pouch"] = pouch_assessment(regions)
    return result


if __name__ == "__main__":
    for cat in PLATFORM_POLICY:
        g = platform_claim(cat, "google")
        t = platform_claim(cat, "tiktok")
        laws = legal_claims(cat)
        print(f"{cat}")
        print(f"   google : {g.coverage.value}")
        print(f"   tiktok : {t.coverage.value}")
        print(f"   laws   : {', '.join(c.country for c in laws) or 'none established'}")
