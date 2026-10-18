"""``geovision`` command-line entry point."""

import argparse
import json
import sys

from geovision.core.logging import configure_logging


def _validate_aoi(args: argparse.Namespace) -> int:
    from geovision.ingest.aoi import AOIValidationError, read_aoi, validate_aoi
    from geovision.modules import load_module

    limits = load_module(args.module).aoi
    try:
        aoi = validate_aoi(
            read_aoi(args.path),
            min_area_ha=limits.get("min_area_ha", 0.01),
            max_area_ha=limits.get("max_area_ha", 50_000),
        )
    except AOIValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "area_ha": round(aoi.area_ha, 4),
                "perimeter_m": round(aoi.perimeter_m, 1),
                "utm_crs": aoi.utm_crs.to_string(),
                "bbox": [round(v, 6) for v in aoi.bbox],
                "warnings": list(aoi.warnings),
            },
            indent=2,
        )
    )
    return 0


def _schemas(args: argparse.Namespace) -> int:
    from geovision.contracts import export_schemas

    for p in export_schemas(args.out):
        print(p)
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="geovision")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-aoi", help="Validate an AOI file and print its summary")
    p.add_argument("path")
    p.add_argument("--module", default="site_screening_in")
    p.set_defaults(func=_validate_aoi)

    p = sub.add_parser("schemas", help="Export JSON Schemas for the data contracts")
    p.add_argument("--out", default="docs/schemas")
    p.set_defaults(func=_schemas)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
