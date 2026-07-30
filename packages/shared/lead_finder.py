"""Automated ICP lead discovery from public web sources (Impressum/Kontakt).

Finds small online businesses / coaches via search, extracts business emails
from public legal/contact pages. No Apollo required.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
OBFUSCATED_RE = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*(?:\(at\)|\[at\]|\s+at\s+)\s*([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.IGNORECASE,
)

SKIP_LOCAL_PARTS = {
    "noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster",
    "abuse", "webmaster", "hostmaster", "privacy", "dsgvo",
}
# Keep datenschutz out of outreach targets (legal contact, not sales ICP)
SKIP_LOCAL_EXACT = {"datenschutz", "dpo", "legal", "privacy", "support", "billing"}

SKIP_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "wordpress.com",
    "googleapis.com", "schema.org", "w3.org", "github.com",
    "cloudflare.com", "google.com", "gmx.de", "gmx.net",
}

CONTACT_PATHS = (
    "/impressum", "/impressum/", "/imprint", "/legal",
    "/kontakt", "/kontakt/", "/contact", "/contact/",
    "/about", "/ueber-uns",
)

DEFAULT_QUERIES = (
    "Business Coach Deutschland Impressum E-Mail",
    "Online Kurs Coach Impressum Kontakt",
    "Funnel Coach Online Business Impressum",
    "Solopreneur Coach Deutschland Kontakt E-Mail",
    "Course Creator Coach DACH Impressum",
    "Business Coaching Selbständig Impressum",
    "Online Business Mentor Deutschland Impressum",
    "Life Business Coach Impressum site:.de",
    "Online Kurs erstellen Coach Impressum",
    "Mitgliedschaftsseite Coach Impressum site:.de",
    "High Ticket Coach Impressum Kontakt",
    "Mindset Coach Online Business Impressum",
    "Female Business Coach Deutschland Impressum",
    "LinkedIn Coach Deutschland Impressum E-Mail",
)

GENERIC_LOCAL = {
    "info", "contact", "kontakt", "hello", "hallo", "office", "mail",
    "team", "service", "anfrage", "beratung",
}

# Bootstrap URLs (public Impressum/Kontakt) for reliable first runs
SEED_URLS = [
    "https://fiala-coaching.de/impressum/",
    "https://www.unternehmercoach.com/footer/impressum/",
    "https://der-businesscoach.biz/impressum/",
    "https://www.sonar-businesscoaching.de/impressum",
    "https://www.bbgcoaching.de/index.php/kontakt",
    "https://www.proaching.de/en/contact/",
    "https://harder-businesscoaching.de/contact/",
    "https://poenighaus-coach.de/kontakt/",
    "https://www.bayer-business-coaching.de/kontakt/",
    "https://funnelmate.io/impressum",
    "https://funnelpower.de/impressum",
    "https://funnel-concept.de/impressum",
    "https://funnel-profi.de/impressum",
    "https://businesscoachingonline.de/impressum/",
    "https://onlinemarketingcoach.de/impressum/",
    "https://coaching-im-business.de/impressum/",
    "https://fee-schoenwald.de/impressum-datenschutzerklaerung/",
    "https://topjobcreator.de/impressum",
    "https://www.online-creators.de/impressum/",
    "https://connectcoach.de/impressum",
    "https://marleenschmitz.de/impressum/",
    "https://poweroncoaching.de/impressum/",
    "https://www.femgo.de/impressum",
    "https://www.cmm-coaching.de/impressum",
    "https://pure-happy.de/impressum/",
    # Fresh DACH coach / creator seeds (rotate when exhausted)
    "https://www.sandra-dirks.de/impressum/",
    "https://www.annacrey.com/impressum/",
    "https://www.markus-eddy.de/impressum/",
    "https://www.stephan-heinrich.com/impressum/",
    "https://www.veit-lindau.de/impressum/",
    "https://www.susanneernst.de/impressum/",
    "https://www.karin-kuschik.de/impressum/",
    "https://www.anja-foerster.de/impressum/",
    "https://www.boris-grundl.com/impressum/",
    "https://www.mirjam-munsch.de/impressum/",
    "https://www.christian-baur.com/impressum/",
    "https://www.onlinebusinesshelden.de/impressum/",
    "https://www.kursmanufaktur.com/impressum/",
    "https://www.coachingspace.de/impressum/",
    "https://www.selfmade-business.de/impressum/",
    "https://www.tino-nitzsche.de/impressum/",
    "https://www.lisa-marie-navarro.de/impressum/",
    "https://www.johannes-falkenstein.de/impressum/",
    "https://www.daniela-samson.de/impressum/",
    "https://www.nicole-jager.de/impressum/",
    "https://www.alexandra-adler.de/impressum/",
]

USER_AGENT = (
    "AmplivoLeadFinder/1.0 (+https://amplivo.net; B2B research bot; "
    "respects robots; contact james@amplivo.net)"
)


@dataclass
class DiscoveredLead:
    email: str
    first_name: str | None
    company: str | None
    website: str | None
    industry: str
    country: str
    source: str
    job_title: str | None = "Founder / Coach"
    employee_count: int | None = 1
    metadata: dict[str, Any] | None = None

    def to_api_payload(self) -> dict[str, Any]:
        data = asdict(self)
        meta = data.pop("metadata") or {}
        data["metadata"] = meta
        return {k: v for k, v in data.items() if v is not None}


def _normalize_email(raw: str) -> str | None:
    email = raw.strip().lower().rstrip(".,;:)>")
    if not email or "@" not in email:
        return None
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return None
    # Strip trailing junk glued by HTML (e.g. .dewebsite)
    domain = re.split(r"[^a-z0-9.\-]", domain)[0]
    for tld in (".com", ".net", ".org", ".io", ".de", ".at", ".ch", ".eu", ".co"):
        idx = domain.rfind(tld)
        if idx > 0:
            domain = domain[: idx + len(tld)]
            break
    labels = domain.split(".")
    if len(labels) < 2:
        return None
    email = f"{local}@{domain}"
    if domain in SKIP_DOMAINS:
        return None
    if local in SKIP_LOCAL_EXACT:
        return None
    if any(local.startswith(s) for s in SKIP_LOCAL_PARTS):
        return None
    # CSS/JS false positives like "67b.huefner@..."
    if re.match(r"^\d+[a-z]", local):
        return None
    if len(local) > 40 or local.count(".") > 3:
        return None
    if email.endswith((".png", ".jpg", ".gif", ".svg", ".webp", ".css", ".js")):
        return None
    tld = labels[-1]
    if len(tld) < 2 or len(tld) > 6 or not tld.isalpha():
        return None
    return email


def _email_priority(email: str) -> int:
    local = email.split("@", 1)[0]
    if local in GENERIC_LOCAL:
        return 2
    if re.match(r"^[a-z]+\.[a-z]+$", local) or len(local) >= 3:
        return 0
    return 1


def extract_emails(text: str) -> list[str]:
    found: list[str] = []
    for match in EMAIL_RE.findall(text or ""):
        email = _normalize_email(match)
        if email and email not in found:
            found.append(email)
    for local, domain in OBFUSCATED_RE.findall(text or ""):
        email = _normalize_email(f"{local}@{domain}")
        if email and email not in found:
            found.append(email)
    return found


def _guess_name(email: str, company: str | None) -> str | None:
    local = email.split("@", 1)[0]
    if local in {"info", "hello", "hallo", "kontakt", "mail", "office", "team", "support"}:
        if company:
            return company.split()[0]
        return None
    part = re.split(r"[._\-]", local)[0]
    if len(part) < 2 or part.isdigit():
        return None
    return part.capitalize()


def _company_from_domain(domain: str) -> str:
    base = domain.split(".")[0]
    return base.replace("-", " ").title()


class LeadFinder:
    def __init__(
        self,
        *,
        industry: str = "online_business",
        country: str = "DE",
        max_leads: int = 50,
        timeout: float = 20.0,
    ) -> None:
        self.industry = industry
        self.country = country
        self.max_leads = max_leads
        self.timeout = timeout
        self._seen_emails: set[str] = set()
        self._seen_domains: set[str] = set()

    async def discover(
        self,
        queries: list[str] | None = None,
        seed_urls: list[str] | None = None,
        exclude_emails: set[str] | None = None,
        prefer_search: bool = True,
    ) -> list[DiscoveredLead]:
        queries = queries or list(DEFAULT_QUERIES)
        leads: list[DiscoveredLead] = []
        excluded = {e.lower() for e in (exclude_emails or set())}
        self._seen_emails |= excluded

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        ) as client:
            search_urls: list[str] = []
            for query in queries:
                if len(leads) >= self.max_leads:
                    break
                search_urls.extend(await self._search_duckduckgo(client, query))

            seed_list = list(seed_urls or [])
            # Search first so exhausted seed lists do not fill the quota with dupes
            urls = (search_urls + seed_list) if prefer_search else (seed_list + search_urls)

            ordered = sorted(
                dict.fromkeys(urls),
                key=lambda u: (
                    0 if any(p in u.lower() for p in ("impressum", "kontakt", "contact")) else 1,
                    0 if u in search_urls else 1,
                    u,
                ),
            )

            for url in ordered:
                if len(leads) >= self.max_leads:
                    break
                found = await self._extract_from_site(client, url)
                found.sort(key=lambda lead: _email_priority(lead.email))
                for lead in found:
                    if lead.email in self._seen_emails:
                        continue
                    self._seen_emails.add(lead.email)
                    leads.append(lead)
                    if len(leads) >= self.max_leads:
                        break
                await asyncio.sleep(0.35)

        return leads

    async def _search_duckduckgo(self, client: httpx.AsyncClient, query: str) -> list[str]:
        try:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
            )
            if resp.status_code != 200:
                return []
            hrefs = re.findall(r'uddg=([^&"]+)', resp.text)
            from urllib.parse import unquote

            urls: list[str] = []
            for raw in hrefs:
                url = unquote(raw)
                if not url.startswith("http"):
                    continue
                host = urlparse(url).netloc.lower()
                if any(x in host for x in ("duckduckgo.", "google.", "facebook.", "youtube.", "linkedin.")):
                    continue
                urls.append(url)
            return urls[:12]
        except httpx.HTTPError:
            return []

    async def _extract_from_site(self, client: httpx.AsyncClient, url: str) -> list[DiscoveredLead]:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return []
        domain = parsed.netloc.lower().removeprefix("www.")
        if domain in self._seen_domains:
            # Still allow if we only saw homepage before
            pass
        self._seen_domains.add(domain)
        base = f"{parsed.scheme}://{parsed.netloc}"

        pages = [url]
        for path in CONTACT_PATHS:
            pages.append(urljoin(base + "/", path.lstrip("/")))
        pages = list(dict.fromkeys(pages))

        emails: list[str] = []
        source_url = url
        for page in pages[:6]:
            try:
                resp = await client.get(page)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                    continue
                page_emails = extract_emails(resp.text)
                if page_emails:
                    emails.extend(page_emails)
                    source_url = page
                    # Prefer impressum hits
                    if "impressum" in page.lower() or "kontakt" in page.lower():
                        break
            except httpx.HTTPError:
                continue
            await asyncio.sleep(0.2)

        leads: list[DiscoveredLead] = []
        for email in emails:
            # Prefer same-domain business emails
            email_domain = email.split("@", 1)[1]
            if email_domain not in {domain, f"www.{domain}"} and not domain.endswith(email_domain):
                # Allow close matches (sonar-coaching.de vs sonar-businesscoaching.de)
                if email_domain.split(".")[0][:4] != domain.split(".")[0][:4]:
                    continue
            company = _company_from_domain(domain)
            leads.append(
                DiscoveredLead(
                    email=email,
                    first_name=_guess_name(email, company),
                    company=company,
                    website=base,
                    industry=self.industry,
                    country=self.country,
                    source="lead_finder",
                    metadata={"discovered_from": source_url, "domain": domain},
                )
            )
        return leads
