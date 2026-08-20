"""One-shot multi-offer blast to unused personal leads."""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"c:/1agentur/data")
ALREADY = {
    "allsensesonlove@gmail.com",
    "gudrun@gudrunoechsl.de",
    "ab@medienbarone.de",
    "haas@phaas.de",
    "tk@gruender-ladies.de",
    "ernst@ernstneumeister.de",
    "sonia@floeckemeier.de",
    "bf@breakevenpoint.net",
    "patricia@kriess.de",
    "henry@znip.academy",
    "post@schoen-beraten.de",
    "coaching@janinereinisch.de",
    "franziska@empulse.rocks",
    "hallo@tinaroebel.de",
    "hallo@juliascholtes.de",
    "hallo@evalehmann.de",
    "julia.schaefer@coaching2change.de",
    "rainer.bielinski@iwp-training.de",
    "hallo@indieconcept.de",
    "hello@robert-wegner-coaching.com",
    "mail@nadinezimper.de",
    "hallo@smart-coaching-berlin.de",
    "mail@vpe-coaching.de",
    "mail@gerd-loeffler.com",
    "tantow@businessdialog.de",
    "ulf@scriptomania.de",
    "anita.stogel@business-coaching-academy.de",
    "omar@infinite-marketing.de",
    "kevin@kevinfiedler.de",
    "hi@lindaluk.de",
    "bockius@mpc-consulting.eu",
    "stefanie@malebenstefanie.de",
    "weiner@goernerweiner.de",
    "tlagemann@online-creators.de",
    "beratung@socialmediaakademie.de",
    "mb@monikabirknerfreedombusiness.de",
    "juliaherrmann.coach@web.de",
    "anfrage@tanjaerdmann.net",
}
STOP = {
    "a.niessen@creaconcept.de",
    "kontakt@birgitheuser.de",
    "kontakt@architekten-coaching.de",
    "hallo@business-boosters.de",
    "info@oliverzehnter.de",
    "hallo@fraukoenig.de",
    "kontakt@exnerundoehrle.de",
    "office@uwebothe.com",
}
GENERIC = {
    "info", "kontakt", "office", "hello", "hallo", "mail", "team",
    "service", "support", "contact", "post",
}


def api(method: str, path: str, data: dict | None = None) -> dict:
    req = urllib.request.Request(
        "https://api.amplivo.net" + path,
        method=method,
        data=(json.dumps(data).encode() if data is not None else None),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def main() -> None:
    seen: set[str] = set()
    picked: list[dict] = []
    for p in sorted(ROOT.glob("leads-batch-*.csv")):
        with p.open(encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                e = (row.get("email") or "").strip().lower()
                if not e or e in seen or e in ALREADY or e in STOP:
                    continue
                local = e.split("@")[0]
                if local in GENERIC:
                    continue
                if any(x in e for x in ("example.com", "amplivo", "test", "llm-probe")):
                    continue
                seen.add(e)
                picked.append(
                    {
                        "email": e,
                        "first_name": (row.get("first_name") or "").strip() or "dort",
                        "company": (row.get("company") or "dein Business").strip()[:40],
                        "industry": "online_business",
                        "source": "manual_impressum",
                        "country": "DE",
                        "employee_count": 1,
                        "job_title": "Founder",
                    }
                )
                if len(picked) >= 12:
                    break
        if len(picked) >= 12:
            break

    print("unique_batch", len(picked))
    for lead in picked:
        created = api("POST", "/leads", lead)
        lid = created["lead_id"]
        co = lead["company"]
        body = (
            f"Hallo {lead['first_name']},\n\n"
            f"fuer {co} drei Optionen:\n\n"
            "PACK 9 EUR https://www.amplivo.net/pack (antworte PACK)\n"
            "SETUP 197 EUR/48h https://www.amplivo.net/setup (antworte BUY)\n"
            "AUDIT https://www.amplivo.net/audit\n\n"
            "STOP zum Abmelden.\n\n"
            "James / Amplivo"
        )
        out = api(
            "POST",
            "/outbound/reply",
            {
                "lead_id": lid,
                "subject": f"9 EUR oder 197 EUR Setup – {co}",
                "body": body,
            },
        )
        print(lead["email"], out.get("sent"), out.get("skipped"))
        time.sleep(1.0)
    print("DONE", len(picked))


if __name__ == "__main__":
    main()
