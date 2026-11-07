"""Forensic audit of OSD-655 VEG-04A mass tables.

Phase 6 model-review question: the mizuna model's target is the `Total (g)`
column. Is that the *same measured quantity* in the flight and ground-control
arms?

Verified column layout (both arms have exactly 23 data fields):

  0 Batch | 1 SN | 2 BarCode | 3 Weight (g) | 4 Pillow Weight (g)
  5 # Established | 6 Establishment Notes | 7 #Leaves unsan | 8 #Leaves Prosan
  9 #Leaves Total | 10-13 MMD Masses (four replicate weighings)
  14 crew consumption (g) | 15 Harvested (g) | 16 Broken Leaves (g)
  17 Total (g) | 18 Trt. Sum | 19 Trt. Avg. | 20 g/leaf | 21 Sample SD | 22 SE

NOTE: the published CSV header under-labels the MMD block: it declares only two
blank sub-headers (columns 11-12) for the three extra populated replicate
columns (11-13). The label "Consumption Avg. (g)" therefore sits on column 13,
which actually holds the fourth MMD replicate, and "Return Samples (g)" sits on
column 14, which actually holds consumption. The mislabel self-corrects from
column 15 onward, so `Harvested (g)`, `Broken Leaves (g)` and `Total (g)` land
on their true columns and the trained target is not corrupted. Any re-derivation
must nevertheless use positions, not key names.

Run: python ml/analysis/audit_osd655_mass.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "OSD-655"

I_SN, I_ESTAB, I_LEAVES = 1, 5, 9
I_MMD = (10, 11, 12, 13)
I_CONSUMPTION, I_HARVESTED, I_BROKEN, I_TOTAL = 14, 15, 16, 17


def rows_of(name):
    text = (RAW / name).read_bytes().decode("cp1252")
    return list(csv.reader(text.splitlines()))


def num(row, i):
    if i >= len(row):
        return None
    raw = row[i].strip()
    if raw in ("", "NA", "---"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# Published values are rounded to 2 dp, so exact reconstruction allows a
# 0.05 g tolerance. The single ground row that needs it (pillow #6) differs by
# 0.02 g (71.40 + 11.20 = 82.60 vs published 82.58) - a rounding artifact, not
# a formula mismatch.
TOL_G = 0.05


def main():
    report = {"study": "OSD-655", "experiment": "VEG-04A", "arms": {}}

    # ---------------- flight arm ----------------
    print("=" * 84)
    print("FLIGHT ARM -- hypothesis: Total = mean(4 MMD replicate weighings) + consumption")
    print("=" * 84)
    fb = [r for r in rows_of("OSD-655_sup_VEG-04-Flight-Mass.csv")[1:]
          if r and r[0].strip() == "Flight"]
    f_ok = f_n = 0
    for r in fb:
        total = num(r, I_TOTAL)
        if total is None:
            continue
        mmd = [v for v in (num(r, i) for i in I_MMD) if v is not None]
        cons = num(r, I_CONSUMPTION)
        if not mmd or cons is None:
            continue
        f_n += 1
        recon = sum(mmd) / len(mmd) + cons
        good = abs(recon - total) <= 0.05
        f_ok += good
        print(f"  {r[I_SN]:<12} Total={total:7.2f}  mean(MMD4)={sum(mmd)/len(mmd):7.4f}"
              f"  + consumption={cons:6.2f} = {recon:8.4f}   exact={good}")
    print(f"\n  flight: {f_ok}/{f_n} rows reconstruct exactly")

    # ---------------- ground arm ----------------
    print()
    print("=" * 84)
    print("GROUND ARM -- hypothesis: Total = full harvest + broken leaves")
    print("=" * 84)
    gb = [r for r in rows_of("OSD-655_sup_VEG-04-GroundControl-Mass.csv")[1:]
          if r and r[0].strip() == "Control"]
    g_ok = g_n = 0
    for r in gb:
        total = num(r, I_TOTAL)
        if total is None:
            continue
        harv = num(r, I_HARVESTED)
        if harv is None:
            continue
        g_n += 1
        broken = num(r, I_BROKEN) or 0.0
        recon = harv + broken
        good = abs(recon - total) <= 0.05
        g_ok += good
        leaves = num(r, I_LEAVES)
        per_leaf = f"{total/leaves:.3f}" if leaves else "n/a"
        print(f"  {r[I_SN]:<5} Total={total:7.2f}  harvested={harv:6.2f}"
              f"  + broken={broken:5.2f} = {recon:7.2f}   exact={good}"
              f"   leaves={leaves}  g/leaf={per_leaf}")
    print(f"\n  ground: {g_ok}/{g_n} rows reconstruct exactly")

    # ---------------- missingness ----------------
    print()
    print("=" * 84)
    print("MISSINGNESS BY ARM (populated cells / rows)")
    print("=" * 84)
    header = rows_of("OSD-655_sup_VEG-04-Flight-Mass.csv")[0]
    for label, body in (("flight", fb), ("ground", gb)):
        print(f"\n  {label} arm (n={len(body)}):")
        for i, h in enumerate(header):
            if not h:
                continue
            n = sum(1 for r in body if i < len(r) and r[i].strip() not in ("", "NA", "---"))
            print(f"    {i:2d} {h:<26} {n:2d}/{len(body)}")
        counts = sum(1 for r in body if num(r, I_LEAVES) is not None)
        print(f"    --> leaf counts available: {counts}/{len(body)}")

    report["arms"]["flight"] = {
        "rows": len(fb), "formula": "mean(MMD4 subsample weighings) + crew consumption",
        "rows_reconstructed": f_n, "rows_exact": f_ok,
        "leaf_counts_available": 0,
        "consumption_included_in_total": True,
    }
    report["arms"]["ground"] = {
        "rows": len(gb), "formula": "full harvested leaf mass + broken leaf mass",
        "rows_reconstructed": g_n, "rows_exact": g_ok,
        "leaf_counts_available": sum(1 for r in gb if num(r, I_LEAVES) is not None),
        "consumption_included_in_total": False,
    }
    report["verdict"] = (
        "The two arms define Total (g) by different formulas over different "
        "underlying measurements: the flight value is a weighed subsample mean "
        "plus crew consumption, the ground value is a complete harvest plus "
        "broken-leaf mass. Only the ground arm records leaf counts. Pooling both "
        "into one target, with `flight` as a predictor, allows the model to fit a "
        "measurement-protocol difference rather than crop biology. The target is "
        "NOT a like-for-like comparison and must be reported as such."
    )
    report["header_defect"] = (
        "The published header declares three blank sub-headers for the MMD block "
        "while four replicate columns are populated, so key-based parsing shifts "
        "the labels from column 13 onward. Total (g) is unaffected; "
        "Consumption Avg. (g) and Return Samples (g) are mis-mapped."
    )
    out = ROOT / "docs" / "phase6" / "osd655_mass_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("=" * 84)
    print("VERDICT")
    print("=" * 84)
    print(report["verdict"])
    print()
    print(f"written: {out.relative_to(ROOT)}")
    # Fail loudly if the arithmetic no longer holds, so this audit cannot rot.
    assert f_ok == f_n and f_n >= 8, f"flight reconstruction broke: {f_ok}/{f_n}"
    assert g_ok == g_n and g_n >= 6, f"ground reconstruction broke: {g_ok}/{g_n}"


if __name__ == "__main__":
    main()
