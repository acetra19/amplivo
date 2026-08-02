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

URLS = [
    "https://funnelmaster.de/impressum.php",
    "https://funnel-profi.de/impressum",
    "https://funnel-fox.de/impressum",
    "https://deinfunnelmitherz.de/impressum",
    "https://onlinemarketingcoach.de/impressum/",
    "https://www.sandra-dirks.de/impressum/",
    "https://www.annacrey.com/impressum/",
    "https://www.markus-eddy.de/impressum/",
    "https://www.stephan-heinrich.com/impressum/",
    "https://www.veit-lindau.de/impressum/",
    "https://www.boris-grundl.com/impressum/",
    "https://www.onlinebusinesshelden.de/impressum/",
    "https://www.kursmanufaktur.com/impressum/",
    "https://www.selfmade-business.de/impressum/",
    "https://www.tino-nitzsche.de/impressum/",
    "https://www.johannes-falkenstein.de/impressum/",
    "https://www.daniela-samson.de/impressum/",
    "https://www.alexandra-adler.de/impressum/",
    "https://www.sabrina-boger.de/impressum/",
    "https://www.nadine-grandmontagne.de/impressum/",
    "https://www.christiane-sauer.de/impressum/",
    "https://www.anja-von-ruetten.de/impressum/",
    "https://www.birgit-schuckert.de/impressum/",
    "https://www.katharina-templin.de/impressum/",
    "https://www.miriam-junius.de/impressum/",
    "https://www.bloggercoach.de/impressum/",
    "https://www.podcastliebe.de/impressum/",
    "https://www.sichtbarkeitsbooster.de/impressum/",
    "https://www.lauchhammer-coaching.de/impressum/",
    "https://www.erfolgsspur.de/impressum/",
    "https://www.businessheldin.de/impressum/",
    "https://www.gruendercoach.de/impressum/",
    "https://www.mindset-mentor.de/impressum/",
    "https://www.flow-business.de/impressum/",
    "https://www.freedom-business.de/impressum/",
    "https://www.startup-coach.de/impressum/",
    "https://www.potenzialentfaltung.com/impressum/",
    "https://www.selbststaendig-erfolgreich.de/impressum/",
    "https://www.karin-kuschik.de/impressum/",
    "https://www.mirjam-munsch.de/impressum/",
    "https://www.christian-baur.com/impressum/",
    "https://www.lisa-marie-navarro.de/impressum/",
    "https://www.nicole-jager.de/impressum/",
    "https://www.susanneschmidt.de/impressum/",
    "https://www.online-marketing-coach.de/impressum/",
    "https://connectcoach.de/impressum",
    "https://www.katrin-hill.de/impressum/",
    "https://www.marike-frick.de/impressum/",
    "https://www.kristin-woltmann.de/impressum/",
    "https://www.tanja-lenke.de/impressum/",
    "https://www.onlinekursfabrik.de/impressum/",
    "https://www.coachcampus.de/impressum/",
    "https://www.marketingheldinnen.de/impressum/",
    "https://www.sichtbarkeitsexpertin.de/impressum/",
    "https://www.contentloewin.de/impressum/",
    "https://www.linkedin-coach.de/impressum/",
    "https://www.verkaufstrainer.de/impressum/",
    "https://www.akquisecoach.de/impressum/",
    "https://www.onlinebusinessschule.de/impressum/",
    "https://www.mentoring-deutschland.de/impressum/",
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
    out = Path("data/leads-batch-2026-08-02-b.csv")
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
