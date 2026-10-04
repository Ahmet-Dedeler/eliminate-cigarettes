# Learning Eliminate Cigarettes: Open Data & Platform Transparency

This guide explains how public policy mandates under the EU Digital Services Act enable open-source compliance surveillance.

---

## 1. Regulatory Background: EU DSA Article 39

Under the European Union Digital Services Act (DSA), designated Very Large Online Platforms (VLOPs)—including Google, TikTok, Meta, and X—are legally mandated to maintain a public, machine-searchable repository of all advertisements served to users in the European Union.

These transparency repositories must include:
- The content and creative of the advertisement
- The person or entity paying for the ad
- The target audience parameters and impressions range
- The date range during which the ad was displayed

---

## 2. The Enforcement Gap

Major ad networks maintain explicit, strict terms of service banning tobacco, vape, e-cigarette, and nicotine product marketing:
- Google Ads Policy: *"Google prohibits advertising that promotes tobacco or products containing tobacco."*
- TikTok Commercial Content Policy: *"Ads promoting the sale or use of tobacco products, e-cigarettes, or nicotine are prohibited."*

However, automated brand name variations, shell LLCs, and indirect affiliate funnels routinely bypass initial ad review systems. Because the DSA mandates public transparency repositories, platforms are effectively publishing self-incriminating evidence of internal policy enforcement failures.

---

## 3. Data Pipeline Design

1. **Extraction:** Queries platform ad transparency APIs across designated EU member states and keywords (e.g. vape brands, heated tobacco units).
2. **Entity Resolution:** Maps shell advertiser accounts back to parent tobacco conglomerates (e.g. BAT, PMI, JTI).
3. **Evidence Packaging:** Exports verifiable evidence bundles capturing ad IDs, creative screenshots, targeting criteria, and exact policy violation clauses for watchdog and regulatory reporting.
