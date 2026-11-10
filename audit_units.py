"""Cross-check XBRL units against the human-readable BRSR PDF (data/raw/pdf/*.txt from `pdftotext -layout`).

XBRL forces Scope 1/2 into tCO2e and energy into GJ, but many filers typed the number from their PDF table,
which is in kilo/million tonnes or MJ/TJ/PJ. This script prints the unit words the PDF uses next to the
Scope 1 row and in the energy table, so every mismatch can be logged in data/corrections.csv.
Output: data/pdf_unit_audit.csv
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
PDF = ROOT / "data" / "raw" / "pdf"
EMIS_UNIT = re.compile(r"(million|mn|mt\b|kilo|'000|000 t|thousand|lakh|metric\s+ton|tonnes?|tons?|tco2)", re.I)
ENERGY_UNIT = re.compile(r"\b(GJ|TJ|PJ|MJ|giga\s*joules?|tera\s*joules?|peta\s*joules?|mega\s*joules?|MWh|kWh|GWh)\b", re.I)


def scan(txt):
    lines = txt.splitlines()
    s1 = next((i for i, l in enumerate(lines) if re.search(r"total\s+scope\s*1\s+emissions", l, re.I)), None)
    emis = sorted({m.lower() for l in lines[s1:s1 + 3] for m in EMIS_UNIT.findall(l)}) if s1 is not None else []
    e0 = next((i for i, l in enumerate(lines) if re.search(r"details of total energy consumption", l, re.I)), None)
    e1 = next((i for i in range(e0 or 0, len(lines)) if re.search(r"total energy consumed\s*\(A", lines[i], re.I)), None) if e0 is not None else None
    energy = sorted({m.upper().replace(" ", "") for l in lines[e0:(e1 or e0) + 3] for m in ENERGY_UNIT.findall(l)}) if e0 is not None else []
    return ", ".join(emis), ", ".join(energy), lines[s1].strip()[:160] if s1 is not None else ""


rows = []
for p in sorted(PDF.glob("*.txt")):
    e, g, line = scan(p.read_text(errors="ignore"))
    rows.append({"symbol": p.stem, "scope1_unit_words": e, "energy_unit_words": g, "scope1_line": line})
out = pd.DataFrame(rows)
out.to_csv(ROOT / "data" / "pdf_unit_audit.csv", index=False)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 90)
print(out.to_string(index=False))
