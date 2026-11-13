"""Downloadable export of a guided-workflow selection: the measured group, in a file.

Why this exists
---------------
The controlled-environment panel could show a measured band on screen and nothing else. A user who
wanted to keep the result had to copy a table out of the browser, which loses the provenance, the
units and the limitations that make the numbers interpretable - and the Mission Control export is a
JSON dump of a simulation, which is neither the same content nor readable.

What a file contains
--------------------
Every export carries the same four things, in this order, because a number without them is not
evidence:

1. **Provenance** - dataset id, DOI, licence, citation, raw-file digest, and the note that the
   measurements come from published experiments rather than from this platform.
2. **The selection** - the factor, the band and its exact bounds, so a reader can tell which
   experiments were included and why, including whether the band is open-ended.
3. **The measurements** - one row per experiment with its environment, and the group summary
   (n, mean, median, sd, range, and the interval only where the sample supports one).
4. **Methodology and limitations**, including the statement that no predictive model is served.

CSV is the default: it opens in every spreadsheet, it diffs, and it survives a decade. PDF is
offered for a file that can be read without a tool. Both are generated from the same in-memory
result the API returns, so a file can never disagree with the screen.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.workflows import cea_evidence

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = 40
TOP = PAGE_HEIGHT - 50
LINE = 14


def filename(format: str, selections: list[dict[str, Any]]) -> str:
    """A name that says what is inside, and sorts by date.

    `spaceagrisim-cea-wheat-co2Ppm-ambient-20261113.csv` - the workflow, the factor and band, and
    the day it was produced. Two exports of different bands cannot silently overwrite each other in
    a downloads folder, which an undifferentiated `export.csv` would.
    """
    described = "-".join(
        f"{item['factor']}-{item['band']}" for item in selections[:cea_evidence.MAX_SELECTIONS]
    ) or "no-selection"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"spaceagrisim-cea-wheat-{described}-{stamp}.{format}"


def _summary_lines(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for group in result["groups"]:
        measured = group["measured"]
        interval = (
            f"{measured['meanCiLow']} to {measured['meanCiHigh']}"
            if measured.get("meanCiLow") is not None
            else f"not reported ({measured['ciStatus']})"
        )
        lines.append(
            f"{group['label']}: n={measured['n']}, mean={measured.get('mean')} kg/m2, "
            f"median={measured.get('median')}, sd={measured.get('sd')}, "
            f"range={measured.get('min')} to {measured.get('max')}, 95% interval={interval}"
        )
    return lines


def render_csv(result: dict[str, Any], configuration: dict[str, Any] | None = None) -> str:
    """The selection as CSV: metadata as `#` lines, then experiments, then the group summary."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    provenance = result["provenance"]["source"]
    method = result["method"]

    writer.writerow(["# SpaceAgriSim guided workflow export (controlled-environment wheat)"])
    writer.writerow(["# Evidence class", result["evidenceClass"],
                     "measured observations; no prediction is included"])
    writer.writerow(["# Dataset", provenance["title"]])
    writer.writerow(["# Dataset id", provenance["dataset"], "DOI", provenance["doi"]])
    writer.writerow(["# Licence", provenance["license"]])
    writer.writerow(["# Citation", provenance["citation"]])
    writer.writerow(["# Measurement basis", provenance["measurementBasis"]])
    writer.writerow(["# Raw file sha256", result["provenance"]["rawFileSha256"]])
    writer.writerow(["# Crop", result["provenance"].get("crop", "wheat cv. Apogee")])
    writer.writerow(["# Method", method["name"]])
    writer.writerow(["# Unit of independence", method["unitOfIndependence"]])
    writer.writerow(["# Interval", method["interval"]])
    writer.writerow(["# Note", method["noTest"]])
    writer.writerow(["# Generated", datetime.now(timezone.utc).isoformat(timespec="seconds")])

    for group in result["groups"]:
        bounds = group["bandBounds"]
        # The bounds carry the factor's unit, and the open top band prints as an open inequality
        # rather than against the sentinel ceiling it is stored with.
        unit = (group.get("unitSymbol") or "").strip()
        lower = f"{bounds['min']} {unit}".strip()
        if bounds["openUpper"]:
            extent = f"> {lower}"
        else:
            extent = (f"{lower} {'<=' if bounds['minInclusive'] else '<'} value "
                      f"{'<=' if bounds['maxInclusive'] else '<'} {bounds['max']} {unit}".strip())
        writer.writerow(["# Selection", group["factor"], group["band"], group["bandLabel"], extent,
                         "open-ended" if bounds["openUpper"] else "bounded"])

    if configuration:
        # The mission the user was looking at, not a second simulation: these are the inputs the
        # Mission Control page would have sent, recorded so the file is self-describing.
        for key, value in configuration.items():
            writer.writerow(["# Mission configuration", key, value])

    writer.writerow([])
    writer.writerow(["selected_factor", "selected_band", "band_label", "experiment_id",
                     "grain_yield_kg_per_m2", "ppfd_umol_per_m2_s", "photoperiod_h_per_day",
                     "co2_ppm", "air_temperature_c"])
    for row in result["rows"]:
        writer.writerow([row["factor"], row["band"], row["label"], row["experimentId"],
                         row["grainYieldKgPerM2"], row["ppfdUmolPerM2S"], row["photoperiodHours"],
                         row["co2Ppm"], row["airTemperatureC"]])

    writer.writerow([])
    writer.writerow(["band_label", "experiments_n", "mean_kg_per_m2", "median_kg_per_m2",
                     "sd_kg_per_m2", "min_kg_per_m2", "max_kg_per_m2",
                     "ci95_low_kg_per_m2", "ci95_high_kg_per_m2", "ci_status", "ci_note"])
    for group in result["groups"]:
        measured = group["measured"]
        writer.writerow([group["label"], measured["n"], measured.get("mean"),
                         measured.get("median"), measured.get("sd"), measured.get("min"),
                         measured.get("max"), measured.get("meanCiLow"),
                         measured.get("meanCiHigh"), measured["ciStatus"],
                         measured.get("ciNote", "")])

    writer.writerow([])
    writer.writerow(["# Correlations"])
    relationship = result["dliRelationship"]
    writer.writerow(["# Pearson", relationship["pearson"], "Spearman", relationship["spearman"],
                     relationship["note"]])
    writer.writerow(["# Predictive model", "not served", result["predictiveModel"]["reason"]])
    writer.writerow(["# Limitations"])
    for item in result["limitations"]:
        writer.writerow(["#", item])
    return stream.getvalue()


def render_pdf(result: dict[str, Any], configuration: dict[str, Any] | None = None) -> bytes:
    """A readable report of the same content, in the project's existing reportlab style."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("SpaceAgriSim controlled-environment wheat: measured group export")
    y = TOP

    def write(text: str, *, size: int = 9, gap: int = LINE, bold: bool = False) -> None:
        nonlocal y
        import textwrap

        for segment in textwrap.wrap(str(text), width=104) or [""]:
            if y < 60:
                pdf.showPage()
                y = TOP
            pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            pdf.drawString(LEFT, y, segment)
            y -= gap

    provenance = result["provenance"]["source"]
    write("SPACEAGRISIM / GUIDED WORKFLOW EXPORT", size=13, bold=True, gap=18)
    write("Measured observations from published experiments. No prediction is included.", bold=True)
    y -= 6
    write(f"Dataset: {provenance['title']}")
    write(f"Dataset id: {provenance['dataset']}    DOI: {provenance['doi']}")
    write(f"Licence: {provenance['license']}")
    write(f"Citation: {provenance['citation']}")
    write(f"Measurement basis: {provenance['measurementBasis']}")
    write(f"Raw file sha256: {result['provenance']['rawFileSha256']}")
    write(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    y -= 8

    write("SELECTION", bold=True)
    for group in result["groups"]:
        bounds = group["bandBounds"]
        write(f"{group['factor']} = {group['band']} ({group['label']})  "
              f"bounds: {bounds['min']} {'inclusive' if bounds['minInclusive'] else 'exclusive'} to "
              f"{'no upper limit' if bounds['openUpper'] else bounds['max']}"
              f"{' ' + (group.get('unitSymbol') or '').strip() if (group.get('unitSymbol') or '').strip() else ''}"
              f"{'' if bounds['openUpper'] else (' inclusive' if bounds['maxInclusive'] else ' exclusive')}")
    y -= 8

    write("MEASURED GROUPS", bold=True)
    for line in _summary_lines(result):
        write(line)
    y -= 8

    write("EXPERIMENTS", bold=True)
    write("id | factor | band | yield kg/m2 | ppfd | photoperiod h | co2 ppm | temperature C",
          size=8)
    for row in result["rows"]:
        write(f"{row['experimentId']} | {row['factor']} | {row['band']} | "
              f"{row['grainYieldKgPerM2']} | {row['ppfdUmolPerM2S']} | {row['photoperiodHours']} | "
              f"{row['co2Ppm']} | {row['airTemperatureC']}", size=8, gap=11)
    y -= 8

    if configuration:
        write("MISSION CONFIGURATION", bold=True)
        write(", ".join(f"{key}={value}" for key, value in configuration.items()))
        y -= 8

    write("METHOD", bold=True)
    write(result["method"]["name"])
    write(f"Unit of independence: {result['method']['unitOfIndependence']}")
    write(f"Interval: {result['method']['interval']}")
    write(result["method"]["noTest"])
    y -= 8

    write("CORRELATION (association, not a response function)", bold=True)
    write(f"Pearson {result['dliRelationship']['pearson']}, Spearman "
          f"{result['dliRelationship']['spearman']}. {result['dliRelationship']['note']}")
    y -= 8

    write("PREDICTIVE MODEL", bold=True)
    write(f"Not served. {result['predictiveModel']['reason']}")
    y -= 8

    write("LIMITATIONS", bold=True)
    for item in result["limitations"]:
        write(f"- {item}")
    pdf.save()
    return buffer.getvalue()


def build(selections: list[dict[str, Any]], format: str,
          configuration: dict[str, Any] | None = None) -> tuple[bytes | str, str, str]:
    """Run the selection and render it. Returns (payload, media type, filename).

    The renderer reads `cea_evidence.run`, the same function the JSON endpoint calls, so an export
    cannot contain a number the API would not return for the same selection.
    """
    result = cea_evidence.run(selections)
    name = filename(format, selections)
    if format == "csv":
        return render_csv(result, configuration), "text/csv; charset=utf-8", name
    if format == "pdf":
        return render_pdf(result, configuration), "application/pdf", name
    raise ValueError(f"unsupported export format {format!r}; supported formats: csv, pdf")
