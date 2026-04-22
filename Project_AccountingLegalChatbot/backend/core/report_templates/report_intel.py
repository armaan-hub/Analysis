"""
REPORT_INTEL — authoritative intelligence per report type.

Every entry provides:
  audience   : Who will read this report (persona description).
  purpose    : The primary purpose / job to be done.
  key_points : Ordered list of mandatory sections the LLM must address.
  tone       : Writing tone instruction.
  structure  : High-level document structure instruction.
"""

REPORT_INTEL: dict[str, dict] = {

    "mis": {
        "audience": (
            "C-suite executives (CEO, CFO, Board of Directors) who need a fast, "
            "data-dense snapshot of business performance. They are time-poor and "
            "want numbers first, narrative second."
        ),
        "purpose": (
            "Provide a concise Management Information System report summarising "
            "KPIs, financial highlights, and operational metrics for the period."
        ),
        "key_points": [
            "Executive summary: 3–5 bullet-point highlights",
            "Revenue vs budget / prior period (variance analysis)",
            "Gross margin, EBITDA, Net Profit with % change",
            "Cash position and working capital movement",
            "Top cost drivers and any abnormal items",
            "Departmental performance vs targets",
            "Key risks and mitigating actions",
            "Outlook / next-period guidance",
        ],
        "tone": "Concise, factual, executive-friendly. Use tables and bullet points.",
        "structure": (
            "1. Executive Summary  2. Financial Highlights (table)  "
            "3. Revenue Analysis  4. Cost Analysis  5. Cash Flow  "
            "6. Operational KPIs  7. Risks & Actions  8. Outlook"
        ),
    },

    "audit": {
        "audience": (
            "Audit committee, board of directors, and external stakeholders. "
            "Readers are financially literate but expect formal, precise language."
        ),
        "purpose": (
            "Present findings, opinions, and recommendations from an audit engagement "
            "in accordance with applicable auditing standards (ISA/IFRS/local GAAP)."
        ),
        "key_points": [
            "Auditor's independent opinion (unqualified/qualified/adverse/disclaimer)",
            "Basis of opinion — standards applied (e.g., ISAs issued by IAASB)",
            "Key audit matters (KAMs) with responses",
            "Going concern assessment",
            "Material misstatements found and management response",
            "Internal control deficiencies and recommendations",
            "Emphasis of matter paragraphs if applicable",
            "Comparative period figures and restatements",
        ],
        "tone": "Formal, precise, independent. Use passive voice where appropriate.",
        "structure": (
            "1. Auditor's Report  2. Basis of Opinion  3. Key Audit Matters  "
            "4. Going Concern  5. Responsibilities (Management / Auditor)  "
            "6. Internal Control Observations  7. Recommendations"
        ),
    },

    "tax_advisory": {
        "audience": (
            "Tax directors, CFOs, and legal counsel. They require technically precise "
            "advice with clear references to statutes, decrees, and precedents."
        ),
        "purpose": (
            "Deliver a professional tax advisory memo outlining exposure, "
            "planning opportunities, and compliance obligations."
        ),
        "key_points": [
            "Executive summary of tax position",
            "Applicable laws, decrees, and ministerial decisions cited by article/number",
            "Taxable vs exempt income/supply breakdown",
            "Tax base calculation with step-by-step workings",
            "Transfer pricing considerations (where relevant)",
            "Penalties and interest exposure for non-compliance",
            "Recommended tax planning strategies with risk ratings",
            "Filing deadlines and next action items",
        ],
        "tone": "Technical, precise, authoritative. Cite all statutory references.",
        "structure": (
            "1. Executive Summary  2. Background & Facts  3. Legal Analysis  "
            "4. Tax Calculation  5. Planning Options  6. Risks & Penalties  "
            "7. Recommendations  8. Next Steps"
        ),
    },

    "legal_memo": {
        "audience": (
            "Partners, senior counsel, or in-house legal teams. They require "
            "structured legal analysis with clear conclusions and risk ratings."
        ),
        "purpose": (
            "Analyse a legal question, contract, or dispute and provide a well-reasoned "
            "legal opinion with actionable recommendations."
        ),
        "key_points": [
            "Issue statement — precise legal question(s) being addressed",
            "Applicable law, jurisdiction, and governing legislation",
            "Facts and assumptions relied upon",
            "Legal analysis — case law, statutory interpretation",
            "Risk assessment (Low / Medium / High) with reasoning",
            "Counter-arguments and how they are addressed",
            "Clear conclusions and legal opinion",
            "Recommended course of action",
        ],
        "tone": "Formal legal prose. Precise, logical, objective.",
        "structure": (
            "1. Issue  2. Brief Answer  3. Facts  4. Analysis  "
            "5. Conclusion  6. Recommendations"
        ),
    },

    "due_diligence": {
        "audience": (
            "Investors, acquirers, and their advisors. Readers are sophisticated but "
            "need a balanced view of opportunities and risks to inform a transaction decision."
        ),
        "purpose": (
            "Provide comprehensive due diligence findings covering financial, legal, "
            "tax, and operational dimensions of a target entity."
        ),
        "key_points": [
            "Transaction overview and scope of review",
            "Financial due diligence — historical performance, quality of earnings",
            "Balance sheet review — asset quality, off-balance-sheet items",
            "Working capital analysis and normalised levels",
            "Legal due diligence — contracts, litigation, IP, regulatory licences",
            "Tax due diligence — exposures, filing history, disputes",
            "Operational and management team assessment",
            "Red flags, deal-breakers, and conditions precedent",
            "Valuation considerations and suggested adjustments",
        ],
        "tone": "Balanced, thorough, investor-oriented. Highlight red flags clearly.",
        "structure": (
            "1. Executive Summary  2. Scope & Limitations  3. Financial Analysis  "
            "4. Legal Review  5. Tax Review  6. Operational Review  "
            "7. Key Findings & Red Flags  8. Conditions & Recommendations"
        ),
    },

    "financial_analysis": {
        "audience": (
            "Finance managers, analysts, and business stakeholders who need a detailed "
            "quantitative and qualitative analysis of financial performance."
        ),
        "purpose": (
            "Analyse financial statements to assess profitability, liquidity, solvency, "
            "and efficiency, benchmarked against industry or prior periods."
        ),
        "key_points": [
            "Profitability ratios (GPM, NPM, EBITDA margin, ROE, ROA)",
            "Liquidity ratios (current, quick, cash ratios)",
            "Solvency / leverage ratios (D/E, interest coverage)",
            "Efficiency ratios (inventory turnover, receivables days, payables days)",
            "Trend analysis over 2–3 periods",
            "Variance analysis — actuals vs budget vs prior year",
            "Peer comparison / industry benchmark (where data available)",
            "Conclusion on financial health and investment attractiveness",
        ],
        "tone": "Analytical, data-driven. Use ratios, tables, and trend commentary.",
        "structure": (
            "1. Overview  2. Income Statement Analysis  3. Balance Sheet Analysis  "
            "4. Cash Flow Analysis  5. Ratio Summary Table  6. Benchmarking  "
            "7. Conclusions"
        ),
    },

    "compliance": {
        "audience": (
            "Compliance officers, regulators, and senior management. They need evidence "
            "of compliance posture and clear identification of gaps."
        ),
        "purpose": (
            "Document the entity's compliance status against applicable regulations, "
            "identify gaps, and recommend corrective actions."
        ),
        "key_points": [
            "Regulatory framework and applicable laws/standards",
            "Compliance assessment methodology",
            "Gap analysis — compliant vs non-compliant areas",
            "Severity rating for each gap (Critical / High / Medium / Low)",
            "Root cause analysis for non-compliances",
            "Corrective action plan with owners and deadlines",
            "Monitoring and testing procedures",
            "Management attestation requirements",
        ],
        "tone": "Systematic, evidence-based. Use gap matrices and RAG status indicators.",
        "structure": (
            "1. Scope  2. Regulatory Summary  3. Assessment Methodology  "
            "4. Gap Analysis Matrix  5. Root Cause Analysis  "
            "6. Corrective Action Plan  7. Monitoring Framework"
        ),
    },

    "board_pack": {
        "audience": (
            "Non-executive directors and board members. They require high-level strategic "
            "information, not operational detail. Time is extremely limited."
        ),
        "purpose": (
            "Provide a concise, decision-ready board pack covering performance, "
            "strategy, risk, and governance matters for the board meeting."
        ),
        "key_points": [
            "Agenda and purpose of the meeting",
            "Financial performance summary (one-page dashboard style)",
            "Strategic initiatives — progress vs plan",
            "Key risks and updated risk register",
            "Governance and compliance matters",
            "Capital allocation / investment decisions requiring approval",
            "CEO / MD operational update",
            "Resolutions to be passed",
        ],
        "tone": "Concise, strategic, decision-oriented. No operational minutiae.",
        "structure": (
            "1. Agenda  2. Financial Dashboard  3. Strategic Update  "
            "4. Risk Report  5. Governance  6. Resolutions"
        ),
    },

    "vat_filing": {
        "audience": (
            "Tax teams, CFOs, and UAE FTA (Federal Tax Authority) as the regulatory recipient. "
            "Must comply with FTA format requirements and be defensible under audit."
        ),
        "purpose": (
            "Prepare or review a UAE VAT return filing with full workings, "
            "reconciliation to accounting records, and supporting schedules."
        ),
        "key_points": [
            "Tax period covered and return reference",
            "Standard-rated supplies — Emirates-wise breakdown",
            "Zero-rated supplies (exports, international services)",
            "Exempt supplies",
            "Input tax credit claimed with eligibility analysis",
            "Input tax blocked/apportioned (partial exemption)",
            "Adjustment for previous period errors (where applicable)",
            "Net VAT payable / refundable with FTA reference",
            "Reconciliation to VAT control account in GL",
        ],
        "tone": "Regulatory-precise. Follow FTA VAT return box numbering.",
        "structure": (
            "1. Filing Summary  2. Output Tax Workings  3. Input Tax Workings  "
            "4. Adjustments  5. Net Position  6. GL Reconciliation  7. Supporting Schedules"
        ),
    },

    "aml_report": {
        "audience": (
            "Compliance officers, Money Laundering Reporting Officers (MLROs), and regulators "
            "(CBUAE, FSRA). Readers expect technical precision and regulatory alignment."
        ),
        "purpose": (
            "Document AML/CFT compliance findings, suspicious activity, and the "
            "entity's risk-based approach in line with FATF recommendations and UAE law."
        ),
        "key_points": [
            "Regulatory basis — UAE AML Law (Fed Decree 20/2018), Cabinet Decision 10/2019",
            "Risk appetite and methodology (FATF risk-based approach)",
            "Customer risk assessment — low/medium/high risk segmentation",
            "Transaction monitoring findings and alert statistics",
            "Suspicious Transaction Reports (STRs) filed in period",
            "Enhanced due diligence (EDD) cases and outcomes",
            "Sanctions screening results",
            "Training and awareness completion rates",
            "Gaps identified and remediation plan",
        ],
        "tone": "Regulatory, precise, risk-focused.",
        "structure": (
            "1. Executive Summary  2. Regulatory Framework  3. Risk Assessment  "
            "4. Transaction Monitoring  5. STR/SAR Summary  6. EDD Cases  "
            "7. Sanctions  8. Training  9. Gaps & Remediation"
        ),
    },

    "valuation": {
        "audience": (
            "Business owners, investors, banks, and courts. They need a defensible, "
            "methodology-driven value conclusion with clear assumptions."
        ),
        "purpose": (
            "Deliver a professional business or asset valuation using recognised methods "
            "(DCF, market multiples, net assets) with a concluded value range."
        ),
        "key_points": [
            "Purpose and scope of the valuation",
            "Standard of value used (fair market value, investment value, etc.)",
            "Valuation date and information relied upon",
            "Business / asset description and industry overview",
            "DCF analysis — projected cash flows, WACC, terminal value",
            "Market multiples approach — comparable transactions / trading multiples",
            "Net asset value approach (where applicable)",
            "Reconciliation and concluded value range",
            "Sensitivity analysis on key assumptions",
            "Limitations and disclaimer",
        ],
        "tone": "Professional, independent, methodology-transparent.",
        "structure": (
            "1. Executive Summary  2. Scope & Methodology  3. Business Overview  "
            "4. DCF Valuation  5. Market Multiples  6. NAV Approach  "
            "7. Reconciliation  8. Sensitivity  9. Conclusion & Disclaimer"
        ),
    },

    "contract_review": {
        "audience": (
            "Legal counsel, business managers, and counterparties. "
            "They need clear identification of risks, obligations, and negotiation points."
        ),
        "purpose": (
            "Review a contract or agreement and provide a structured summary of key "
            "terms, risks, and recommended amendments."
        ),
        "key_points": [
            "Parties, governing law, and jurisdiction",
            "Key commercial terms (price, payment, delivery, duration)",
            "Representations, warranties, and indemnities",
            "Limitation of liability and exclusion clauses",
            "Termination triggers and consequences",
            "Intellectual property rights and confidentiality",
            "Dispute resolution mechanism (arbitration/litigation/ADR)",
            "Unusual or one-sided clauses — flag and recommend amendments",
            "Missing standard protections (force majeure, change in law, etc.)",
        ],
        "tone": "Legal, analytical. Clearly flag risk items with RED / AMBER / GREEN ratings.",
        "structure": (
            "1. Contract Summary Table  2. Key Commercial Terms  3. Legal Risk Analysis  "
            "4. Clause-by-Clause Review  5. Red Flags  6. Recommended Amendments"
        ),
    },
}
