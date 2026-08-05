"""One-off: scrape Impressum pages into a lead CSV."""

from __future__ import annotations

import asyncio
import csv
import re
from pathlib import Path

import httpx

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)
OBF = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*(?:\(at\)|\[at\]|\s+at\s+)\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.I,
)
SKIP_LOCAL = {
    "noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster", "abuse",
    "webmaster", "hostmaster", "privacy", "dsgvo", "datenschutz", "dpo", "legal",
    "support", "billing", "menu_button", "flags", "email", "deine",
}
SKIP_DOM = {
    "example.com", "sentry.io", "wixpress.com", "googleapis.com", "schema.org",
    "w3.org", "github.com", "cloudflare.com", "google.com", "gmx.de", "gmx.net",
    "weka.de", "email.de", "digistore24.com", "elopage.com",
}
UA = "AmplivoLeadFinder/1.0 (+https://amplivo.net; B2B research)"

# Rotate this list when ready-pool is empty — prefer personal founder sites.
URLS = [
    "https://kurse.christamanske-coaching.de/impressum/",
    "https://www.christamanske.de/impressum/",
    "https://businesscoach-ihk.de/impressum/",
    "https://www.coaching-akademie-muenchen.de/impressum/",
    "https://www.coachyourlife.de/impressum/",
    "https://www.soulful-business.de/impressum/",
    "https://www.leichtigkeit-im-business.de/impressum/",
    "https://www.onlinekurscoach.de/impressum/",
    "https://www.kursheldin.de/impressum/",
    "https://www.mitgliedschaftsexpertin.de/impressum/",
    "https://www.high-ticket-coach.de/impressum/",
    "https://www.launchqueen.de/impressum/",
    "https://www.funnelqueen.de/impressum/",
    "https://www.salesqueen.de/impressum/",
    "https://www.sichtbarkeitscoach.de/impressum/",
    "https://www.personalbrandingcoach.de/impressum/",
    "https://www.instagramcoach.de/impressum/",
    "https://www.tiktokcoach.de/impressum/",
    "https://www.youtube-coach.de/impressum/",
    "https://www.podcastcoach.de/impressum/",
    "https://www.autorencoach.de/impressum/",
    "https://www.buchcoach.de/impressum/",
    "https://www.speakercoach.de/impressum/",
    "https://www.keynote-coach.de/impressum/",
    "https://www.mindsetcoach.de/impressum/",
    "https://www.erfolgsmindset.de/impressum/",
    "https://www.selbstliebe-coach.de/impressum/",
    "https://www.burnout-coach.de/impressum/",
    "https://www.resilienzcoach.de/impressum/",
    "https://www.karrierecoaching.de/impressum/",
    "https://www.bewerbungscoach.de/impressum/",
    "https://www.outplacement-coach.de/impressum/",
    "https://www.fuehrungskraeftecoach.de/impressum/",
    "https://www.teamcoaching.de/impressum/",
    "https://www.agile-coach.de/impressum/",
    "https://www.scrum-coach.de/impressum/",
    "https://www.produktcoach.de/impressum/",
    "https://www.innovationcoach.de/impressum/",
    "https://www.startupcoach.de/impressum/",
    "https://www.scaleup-coach.de/impressum/",
    "https://www.exit-coach.de/impressum/",
    "https://www.finanzcoach-online.de/impressum/",
    "https://www.geldmindset.de/impressum/",
    "https://www.immobilien-coach.de/impressum/",
    "https://www.passives-einkommen-coach.de/impressum/",
    "https://www.affiliate-marketing-coach.de/impressum/",
    "https://www.dropshipping-coach.de/impressum/",
    "https://www.ecommerce-coach.de/impressum/",
    "https://www.shopify-coach.de/impressum/",
    "https://www.amazon-fba-coach.de/impressum/",
    "https://www.nicole-jager.de/impressum/",
    "https://www.monika-birkner.de/impressum/",
    "https://www.regina-stoiber.de/impressum/",
    "https://www.vera-heim.de/impressum/",
    "https://www.susanneschmidt.de/impressum/",
    "https://www.susanneernst.de/impressum/",
    "https://www.karin-kuschik.de/impressum/",
    "https://www.anja-foerster.de/impressum/",
    "https://www.mirjam-munsch.de/impressum/",
    "https://www.christian-baur.com/impressum/",
    "https://www.lisa-marie-navarro.de/impressum/",
    "https://www.contentqueen.de/impressum/",
    "https://www.sichtbarkeitsbooster.de/impressum/",
    "https://www.potenzialentfaltung.com/impressum/",
    "https://www.selbststaendig-erfolgreich.de/impressum/",
    "https://www.startup-coach.de/impressum/",
    "https://www.mindset-mentor.de/impressum/",
    "https://www.freedom-business.de/impressum/",
    "https://www.online-creators.de/impressum/",
    "https://connectcoach.de/impressum",
    "https://funnelmate.io/impressum",
    "https://funnelpower.de/impressum",
    "https://onlinemarketingcoach.de/impressum/",
    "https://www.oliverzehnter.de/impressum/",
    "https://www.sandra-staub.de/impressum/",
    "https://www.eloha-lheana.de/impressum/",
]


def clean(email: str) -> str | None:
    e = email.lower().rstrip(".,;:)>\"'")
    if "@" not in e or len(e) > 70:
        return None
    local, _, dom = e.partition("@")
    if not local or not dom or "." not in dom:
        return None
    if local in SKIP_LOCAL or "noreply" in local or "datenschutz" in local:
        return None
    if dom in SKIP_DOM or any(x in dom for x in SKIP_DOM):
        return None
    if e.endswith((".png", ".jpg", ".gif", ".svg")):
        return None
    for junk in ("website", "impressum", "kontakt", "datenschutz"):
        if e.endswith(junk):
            e = e[: -len(junk)]
    return e


async def fetch(client: httpx.AsyncClient, url: str) -> list[tuple[str, str]]:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=18)
        if resp.status_code >= 400:
            return []
        text = resp.text
        found: set[str] = set()
        for match in EMAIL_RE.findall(text):
            email = clean(match)
            if email:
                found.add(email)
        for local, domain in OBF.findall(text):
            email = clean(f"{local}@{domain}")
            if email:
                found.add(email)
        return [(email, url) for email in sorted(found)[:4]]
    except Exception:
        return []


async def main() -> None:
    async with httpx.AsyncClient(headers={"User-Agent": UA}, verify=False) as client:
        results: list[tuple[str, str]] = []
        for i in range(0, len(URLS), 12):
            chunk = URLS[i : i + 12]
            parts = await asyncio.gather(*[fetch(client, u) for u in chunk])
            for part in parts:
                results.extend(part)

    by_email = {email: url for email, url in results}
    out = Path("data/leads-batch-2026-08-05.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "email", "first_name", "company", "job_title", "website",
                "industry", "employee_count", "country", "source",
            ],
        )
        writer.writeheader()
        for email, url in sorted(by_email.items()):
            host = email.split("@")[1].split(".")[0].replace("-", " ").title()
            website = url.rsplit("/impressum", 1)[0].rstrip("/") if "impressum" in url else url
            writer.writerow(
                {
                    "email": email,
                    "first_name": "",
                    "company": host,
                    "job_title": "Founder / Coach",
                    "website": website,
                    "industry": "online_business",
                    "employee_count": 1,
                    "country": "DE",
                    "source": "manual_impressum",
                }
            )
    print(f"FOUND {len(by_email)}")
    for email, url in sorted(by_email.items()):
        print(f"  {email} <- {url}")
    print(f"WROTE {out}")


if __name__ == "__main__":
    asyncio.run(main())
