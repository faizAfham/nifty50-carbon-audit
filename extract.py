"""Parse NSE BRSR XBRL files (data/raw/*_FY24.xml) into data/brsr_emissions.csv.

Every number comes straight from a tagged XBRL fact. Nothing is estimated.
One FY2023-24 BRSR filing carries both the current year (context DCYMain = FY2023-24)
and the previous year (DPYMain = FY2022-23), so each file gives up to 2 rows.
"""
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "brsr_emissions.csv"

TAGS = {
    "scope1_tco2e": "TotalScope1Emissions",          # unit "MtCO2e" in SEBI taxonomy = metric tonnes CO2e
    "scope2_tco2e": "TotalScope2Emissions",
    "energy_gj": "TotalEnergyConsumedFromRenewableAndNonRenewableSources",
    "energy_renewable_gj": "TotalEnergyConsumedFromRenewableSources",
    "revenue_inr": "RevenueFromOperations",
    "revenue_total_inr": "TotalRevenueOfTheCompany",  # fallback when RevenueFromOperations is absent/zero
}
CRORE = 1e7
# ponytail: Nifty 50 companies all have revenue > Rs 500 cr, so a value tagged "INR" that is below
# Rs 10 cr (1e8) can only be a filer typing the figure in Rs crore. We keep the raw filed number too.
MIN_PLAUSIBLE_INR = 1e8
CTX = {"FY2023-24": "DCYMain", "FY2022-23": "DPYMain"}
COLS = ["company", "symbol", "sector", "fy", "scope1_tco2e", "scope2_tco2e", "energy_gj",
        "energy_renewable_gj", "revenue_cr", "revenue_filed_value", "revenue_note", "qa_note", "reporting_boundary", "source_url", "pdf_url"]


def fact(xml, tag, ctx):
    m = re.search(rf'<in-capmkt:{tag} contextRef="{ctx}"[^>]*>([^<]*)<', xml)
    if not m or not m.group(1).strip():
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def text(xml, tag):
    m = re.search(rf'<in-capmkt:{tag} contextRef="[^"]*"[^>]*>([^<]*)<', xml)
    return m.group(1).strip() if m else ""


# Filers that typed revenue in Rs million under an INR tag. Evidence in README (HCL: the filing's
# RevenueFromOperations / TotalRevenue(USD mn) = 82.8, i.e. the INR/USD rate, so the figure is Rs mn).
REVENUE_IN_MILLION = {"HCLTECH"}


def revenue_cr(sym, cands):
    """Pick revenue from the filing. Returns (revenue_cr, filed_value, note)."""
    for val, tag in cands:  # 1) a value that is plausibly in rupees
        if val and val >= MIN_PLAUSIBLE_INR:
            return val / CRORE, val, tag
    for val, tag in cands:  # 2) a small value: filer typed crore (or million) under the INR tag
        if val:
            if sym in REVENUE_IN_MILLION:
                return val / 10, val, tag + "; filed in Rs million under INR tag, /10 to crore"
            return val, val, tag + "; filed in Rs crore under INR tag, used as crore"
    return None, None, "no revenue tagged"


def load_fixes():
    """data/corrections.csv: XBRL values whose unit the filing's own PDF contradicts."""
    p = ROOT / "data" / "corrections.csv"
    if not p.exists():
        return {}
    return {(r["symbol"], r["fy"], r["field"]): (float(r["corrected_value"]) if r["corrected_value"] else None,
                                                  r["reason"]) for r in csv.DictReader(open(p))}


def main():
    fixes = load_fixes()
    nifty = {r["Symbol"]: r for r in csv.DictReader(open(RAW / "nifty50.csv"))}
    filings = json.load(open(RAW / "fy24_filings.json"))  # [symbol, submitted, revised, xbrl_url, pdf_url]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        for sym, _, _, xbrl_url, pdf_url in filings:
            p = RAW / f"{sym}_FY24.xml"
            if not p.exists():
                print("MISSING", sym)
                continue
            xml = p.read_text(errors="ignore")
            for fy, ctx in CTX.items():
                v = {k: fact(xml, t, ctx) for k, t in TAGS.items()}
                cands = [(v.pop("revenue_inr"), "RevenueFromOperations"),
                         (v.pop("revenue_total_inr"), "TotalRevenueOfTheCompany")]
                rev_cr, rev, note = revenue_cr(sym, cands)
                qa = []
                for (fsym, ffy, field), (val, why) in fixes.items():
                    if fsym == sym and ffy == fy:
                        v[field] = val
                        qa.append(f"{field}: {why}")
                w.writerow({
                    "company": nifty[sym]["Company Name"], "symbol": sym,
                    "sector": nifty[sym]["Industry"], "fy": fy, **v,
                    "revenue_cr": None if rev_cr is None else round(rev_cr, 2),
                    "revenue_filed_value": rev, "revenue_note": note, "qa_note": "; ".join(qa),
                    "reporting_boundary": text(xml, "ReportingBoundary"),
                    "source_url": xbrl_url, "pdf_url": pdf_url,
                })
            f.flush()  # progress saved per company
            print("ok", sym)


if __name__ == "__main__":
    main()
