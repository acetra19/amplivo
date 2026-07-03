# Affiliate Product Comparison Matrix

> Scoring model for autonomous agentic sales. Higher **Agent Score** = better fit for full automation.

## Scoring Criteria (1–10 each)

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Recurring LTV | 25% | Expected commission over 24 months |
| Trial/Self-Serve | 20% | Can agent onboard without human? |
| ICP Clarity | 15% | How well-defined is the target audience? |
| API & Docs | 15% | RAG + demo automation possible? |
| Cookie Duration | 10% | Attribution window for long B2B cycles |
| Competition | 10% | Saturation of affiliate marketers |
| Compliance Risk | 5% | Legal/regulatory burden (lower = better) |

---

## Top 5 Products – Detailed Matrix

### 1. GoHighLevel ⭐ Recommended Primary

| Field | Value |
|-------|-------|
| Category | Agency SaaS (white-label CRM + funnels) |
| Monthly Price | $97 – $497 |
| Commission | ~40% recurring |
| Cookie | 90 days |
| Trial | 14 days |
| **Est. LTV (24mo)** | **$950 – $4,750** per conversion |
| ICP | Local marketing agencies, SMMA, freelancers |
| API | Yes – extensive |
| Agent Score | **9.2 / 10** |

**Pros:** Perfect meta-fit (sales agency selling agency tool). High ticket, strong community, clear pain points.  
**Cons:** Saturated affiliate space – differentiation via AI outreach required.  
**Agent Strategy:** Outbound to agencies < 20 employees, voice follow-up on trial day 3.

---

### 2. Systeme.io

| Field | Value |
|-------|-------|
| Category | All-in-one marketing (funnels, email, courses) |
| Monthly Price | $27 – $97 |
| Commission | 40% lifetime recurring |
| Cookie | 60 days |
| Trial | Free tier + paid upgrade |
| **Est. LTV (24mo)** | **$260 – $930** |
| ICP | Solopreneurs, course creators, small coaches |
| API | Limited |
| Agent Score | **7.8 / 10** |

**Pros:** Lifetime recurring is exceptional. Lower price = easier conversion.  
**Cons:** Lower ticket, weaker API, more price-sensitive audience.  
**Agent Strategy:** Content-led inbound + chat qualifier, less cold outreach.

---

### 3. Semrush

| Field | Value |
|-------|-------|
| Category | SEO / Marketing intelligence |
| Monthly Price | $129 – $499 |
| Commission | 40% recurring (first 12 months typical) |
| Cookie | 120 days |
| Trial | 7 days |
| **Est. LTV (12mo)** | **$620 – $2,400** |
| ICP | SEO agencies, content teams, in-house marketers |
| API | Yes – excellent for agent demos |
| Agent Score | **8.5 / 10** |

**Pros:** Strong B2B ICP, long cookie, technical agents can demo real value.  
**Cons:** Short trial (7 days), competitive market, needs SEO knowledge in prompts.  
**Agent Strategy:** Technical outbound to agencies already using free SEO tools.

---

### 4. HubSpot

| Field | Value |
|-------|-------|
| Category | CRM + Marketing Hub |
| Monthly Price | $800+ (Professional) |
| Commission | ~30% recurring (partner program) |
| Cookie | 180 days |
| Trial | 14 days |
| **Est. LTV (12mo)** | **$2,880+** |
| ICP | SMB sales teams, growing B2B |
| API | Yes – best-in-class |
| Agent Score | **7.5 / 10** |

**Pros:** Massive LTV, long cookie, excellent API.  
**Cons:** Partner program has approval process. Complex product – harder to automate demos. Long sales cycle.  
**Agent Strategy:** Better as upsell after agency tool conversion, not primary.

---

### 5. ClickFunnels

| Field | Value |
|-------|-------|
| Category | Funnel builder |
| Monthly Price | $147 – $297 |
| Commission | 30–40% recurring |
| Cookie | 45 days |
| Trial | 14 days |
| **Est. LTV (12mo)** | **$530 – $1,430** |
| ICP | Coaches, info products, e-commerce |
| API | Moderate |
| Agent Score | **7.0 / 10** |

**Pros:** Strong brand, proven affiliate program, clear use cases.  
**Cons:** Short cookie, coach market harder to cold-email, trust-heavy.  
**Agent Strategy:** Inbound funnels + webinar-style voice demos.

---

## Summary Ranking

| Rank | Product | Agent Score | Est. LTV | Best For |
|------|---------|-------------|----------|----------|
| 1 | GoHighLevel | 9.2 | $950–4,750 | Primary autonomous outbound |
| 2 | Semrush | 8.5 | $620–2,400 | Technical SEO niche |
| 3 | Systeme.io | 7.8 | $260–930 | Volume / inbound play |
| 4 | HubSpot | 7.5 | $2,880+ | High-ticket with human handoff |
| 5 | ClickFunnels | 7.0 | $530–1,430 | Content/inbound heavy |

---

## Recommended Stack Strategy

```
Primary:   GoHighLevel (80% of outbound effort)
Secondary: Systeme.io (downsell for non-agency leads)
Upsell:    Semrush (cross-sell to agencies already converted)
```

## Break-Even Math (GoHighLevel Example)

| Metric | Value |
|--------|-------|
| Avg commission/month | ~$119 (40% of $297 plan) |
| LTV (12 months) | ~$1,428 |
| Target CAC | < $430 (30% of LTV) |
| Cold email cost/lead | ~$0.05–0.15 |
| Leads needed at 1% conversion | ~700 emails → 7 trials → 1–2 conversions |
| Monthly tool cost (MVP) | ~$400–600 |
| Break-even | 1 conversion/month covers infra |

---

## Decision: Start With GoHighLevel

Best combination of:
- High recurring commission
- Clear ICP (agencies)
- Trial allows agent-led onboarding
- Meta-narrative: "AI sales agency powered by the tool we sell"

Update `AFFILIATE_PRODUCT_SLUG=gohighlevel` in `.env` after signing up for the affiliate program.
