# PathShalaAI — Business Model & Go-To-Market Plan

> **Note:** Every unverified figure below is explicitly labeled **ASSUMPTION**. All institutions listed are **TARGET PARTNERS** (no formal partnership exists yet).

## 1. Users & Stakeholders
- **Primary Beneficiaries:** Primary school students in Bangladesh (Classes 1–5, ages 6–11) and their parents.
- **Institutional Users:** Primary school teachers (via the `/teacher` analytics dashboard) and school administrators.
- **Target Distribution & Funding Partners (Targets, Not Existing Partners):**
  - NGOs operating primary education networks (e.g., BRAC Education, JAAGO Foundation — *target partners*).
  - Government digital-education initiatives (e.g., a2i / Muktopaath / Directorate of Primary Education — *target partners*).
  - Corporate CSR programs & telecom zero-rating/data-bundle sponsors (*target partners*).

## 2. Problem & Value Proposition
- Many primary students in Bangladesh rely on paid private coaching or guidebooks to understand NCTB textbooks.
- **ASSUMPTION:** Typical urban/semi-urban private coaching costs BDT 1,000–3,000/month per student (exact household spend varies by district and requires local survey validation).
- **PathShalaAI Value:** Free, 24/7 Bangla textbook-grounded tutor with verifiable chapter/chunk citations, honest refusal on off-syllabus topics (100% on 32/32 eval items), voice/photo input, and adaptive chapter mastery—eliminating hallucinated answers while giving teachers class-level gap visibility.

## 3. Business Model (Freemium + Institutional B2B/B2G)
1. **Students & Parents — Free Forever:** Zero-login, zero-paywall access to text/voice/photo Q&A, citations, and adaptive practice.
2. **Schools & NGOs — Paid Institutional Dashboard (SaaS):**
   - **ASSUMPTION:** BDT 150–300 / teacher / month (or ~USD 1.50–3.00) for school-wide analytics, weak-chapter alerts, weekly CSV/digest exports, and priority capacity.
3. **B2G / CSR Sponsorship:**
   - Sponsored district-level deployments funded by CSR/development grants at fixed per-school annual licensing.

## 4. Unit Economics (Grounded in Measured Cost)
- **Measured Inference Cost:** **\$0.00078 / query** (measured mean across `n = 187` golden-set queries in `eval/results.json`).
- **ASSUMPTION — Monthly Usage:** 60 queries per active student per month (~2 queries/day).
- **Estimated Variable AI Cost per Active Student / Month:** `60 × \$0.00078 = \$0.0468 / month` (~BDT 5.6 / month at 120 BDT/USD — **ASSUMPTION**).
- **ASSUMPTION — Hosting & DB Overhead:** ~\$25–\$50/month for managed Postgres (`pgvector`) + API container supporting up to ~5,000 monthly active students (~$\$0.005\text{–}\$0.01$/student/month at scale).
- **Total Variable + Infra Cost at Scale (ASSUMPTION):** ~\$0.06 / active student / month.
- **Margin Implication:** One paying teacher/school seat (**ASSUMPTION:** \$2.00/month covering 30–40 students) or a modest CSR grant covers variable AI cost for ~30+ free students.

## 5. 12-Month Go-To-Market Plan & 3 Core KPIs
| Phase | Timeline | Focus |
|---|---|---|
| **Pilot** | Months 1–3 | 1–2 partner schools/NGO learning centers; 100+ real student/teacher queries; validate latency & Bangla UX |
| **Expand** | Months 4–6 | Add Classes 6–8 NCTB textbooks; launch paid teacher analytics pilot; low-bandwidth PWA + Telegram channel |
| **Scale** | Months 7–12 | Multi-district NGO/CSR rollout; target 10+ schools and 2,000+ weekly active students (**ASSUMPTION**) |

**3 Core KPIs:**
1. **Weekly Active Students (WAS):** Distinct anonymous sessions asking >= 3 textbook questions/week.
2. **Answer-Helpful Rate:** `%` of thumbs-up (`👍`) feedback on `/feedback`.
3. **Grounded Citation Rate:** `%` of non-refused answers with verified textbook citations (`clean_citations` enforced).

## 6. Key Risks & Mitigations
- **LLM API Quota / Cost Spikes:** Mitigated via in-memory + DB caching, conditional query rewrite, high-score verifier skip, and multi-model fallback.
- **Low-Bandwidth / Device Constraints:** Mitigated via lightweight Next.js UI, SSE streaming, and low-RAM FTS fallback.
- **Child Safety & Curriculum Trust:** Mitigated via deterministic distress gate (`1098` helpline), strict textbook-only citations, and zero PII/photo storage.
