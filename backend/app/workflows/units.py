"""Machine-readable units, defined once.

The platform has always carried units in field names (`waterUsed` is litres, `co2Removed` grams)
and in prose descriptions. A client that wants to label an axis or convert a value therefore has to
read English, which is exactly the kind of implicit contract that breaks silently when someone adds
a field.

Every quantity a workflow returns is registered here with its canonical unit, the dimension it
belongs to, and a note on anything a reader could get wrong. The workflows expose a `units` map
alongside their numbers, so a chart library, a CSV export or a validation script can be unit-aware
without parsing descriptions.

This module does not convert anything. Converting silently is the failure mode it exists to
prevent: a value is always reported in the unit its producer measured or computed it in, and the
conversion, if needed, is the caller's explicit choice.
"""

from __future__ import annotations

from typing import Any

# canonical unit -> (dimension, description, cautions)
UNITS: dict[str, tuple[str, str, list[str]]] = {
    "mm/day": ("flux", "millimetres of water depth per day",
               ["a depth, not a volume: converting to litres needs an area",
                "1 mm over 1 m2 is exactly 1 L"]),
    "L/day": ("flow", "litres of water per day", ["volume at the plant or canopy, not at the meter"]),
    "L": ("volume", "litres of water", []),
    "L/m2/day": ("flux", "litres of water per square metre of surface per day",
                 ["the surface matters: canopy area and ground area give different answers"]),
    "mL/pot/day": ("flow", "millilitres of water per pot per day",
                   ["per pot, and the pot's surface area is what makes it a flux"]),
    "mL": ("volume", "millilitres of water", []),
    "mm2": ("area", "square millimetres of leaf surface",
            ["leaf area is a surface, not a ground area; the two scale very differently",
             "leaf area per plant, not per square metre of bench: the two are not interchangeable"]),
    "kg/m2": ("mass flux", "kilograms of harvested grain per square metre of growing area",
              ["grain mass at field moisture as harvested, not dry matter and not edible "
               "fraction; wheat in the controlled-environment series, never converted to fresh "
               "mass or to another crop"]),
    "g/m2": ("mass flux", "grams of fresh mass per square metre of growing area",
             ["this is an areal yield, not a per-plant mass: dividing by density assumes the "
              "per-area yield is independent of density, which the model itself warns is not "
              "true above ~200 plants/m2"]),
    "g/plant": ("mass", "grams of fresh or dry mass per individual plant",
                ["a per-plant mass is not an areal yield; multiplying by density assumes every "
                 "plant occupies its nominal area and competes equally",
                 "fresh mass, dry mass and edible yield per square metre are three different "
                 "quantities; the field name says which one was measured"]),
    "g": ("mass", "grams", []),
    "degC": ("temperature", "degrees Celsius", []),
    "K": ("temperature", "kelvin", []),
    "kPa": ("pressure", "kilopascal", ["VPD is a pressure deficit, not a concentration"]),
    "Pa": ("pressure", "pascal", []),
    "%": ("fraction", "percent", ["fractions in the API are 0-1 unless the field name says Pct"]),
    "fraction": ("dimensionless", "a ratio in the closed interval [0, 1]", []),
    "m2": ("area", "square metres",
           ["ground area and canopy area are different quantities with the same unit"]),
    "m/s": ("speed", "metres per second", ["wind is at 2 m height in FAO-56, not at 10 m"]),
    "MJ/m2/day": ("energy flux", "megajoules of radiant energy per square metre per day",
                  ["solar radiation is not PAR and is not ionising radiation"]),
    "mol/m2/day": ("photon flux", "moles of photosynthetically active photons per square metre per day",
                   ["PAR only; this is not total solar radiation"]),
    "umol/m2/s": ("photon flux density", "micromoles of photons per square metre per second", []),
    "day": ("time", "days", ["calendar days of crop cycle, counted from the stated origin"]),
    "h/day": ("time", "hours per day", []),
    "degree": ("angle", "decimal degrees", ["latitude north positive"]),
    "m": ("length", "metres above mean sea level", []),
    "plant": ("count", "number of plants", []),
    "plant/m2": ("count density", "plants per square metre of growing area",
                 ["the model does not learn how per-area yield changes with density; it only "
                  "divides by it"]),
    "ppm": ("mole fraction", "parts per million by volume in air", []),
    "dimensionless": ("dimensionless", "a pure number", []),
    "mm": ("water depth", "millimetres of water depth, where 1 mm over 1 m2 is 1 litre",
           ["a depth is not a volume: litres require an area, and this registry never multiplies "
            "one by the other"]),
    # `g/plant` and `mm2` are defined once, above. A second definition of the same key in this
    # literal silently replaced the first - Python keeps the last - so the registry served one
    # wording and dropped the other's caution. There is one entry per unit by construction now.
    "count": ("count", "a whole-number count of organs or events", []),
    "mg/g fresh weight": ("concentration", "milligrams of a compound per gram of fresh mass",
                          ["a fresh-mass basis, not dry mass; the two are not interchangeable"]),
    "mg quercetin equiv/g FW": ("concentration", "milligrams of quercetin equivalents per gram "
                                 "of fresh mass", ["an equivalent-mass basis defined by one assay"]),
    "mg gallic acid equiv/g FW": ("concentration", "milligrams of gallic acid equivalents per gram "
                                  "of fresh mass", ["an equivalent-mass basis defined by one assay"]),
    "umol quercetin equiv": ("amount", "micromoles of quercetin equivalents in the extracted "
                             "sample", ["a per-sample amount, not a concentration; the sample mass "
                                        "is not in this table"]),
    "spad-index": ("index", "a dimensionless relative chlorophyll index from a SPAD meter",
                   ["an index, not a chlorophyll concentration; it cannot be converted to mg/g "
                    "without a calibration this platform does not have"]),
}

DIMENSIONS = sorted({entry[0] for entry in UNITS.values()})


def describe(unit: str) -> dict[str, Any]:
    """One unit's metadata. Unknown units are reported as unknown, never guessed."""
    if unit not in UNITS:
        return {"unit": unit, "dimension": "unknown", "description": "",
                "cautions": ["this unit is not registered, so its dimension is unknown"],
                "registered": False}
    dimension, description, cautions = UNITS[unit]
    return {"unit": unit, "dimension": dimension, "description": description,
            "cautions": cautions, "registered": True}


def block(**quantities: str) -> dict[str, dict[str, Any]]:
    """A units map for a response: field name -> unit metadata.

    Usage: ``units=units.block(waterDemandLD="L/day", et0MmPerDay="mm/day")``
    """
    out: dict[str, dict[str, Any]] = {}
    for field, unit in quantities.items():
        out[field] = describe(unit)
    return out


def registry() -> dict[str, Any]:
    """Every unit the platform names, with its dimension."""
    return {
        "units": {name: describe(name) for name in sorted(UNITS)},
        "dimensions": DIMENSIONS,
        "note": ("Values are always reported in the unit their producer used. Nothing here "
                 "converts; a conversion is the caller's explicit choice."),
    }
