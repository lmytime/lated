"""Command-line interface: serve the web app, or fit from a JSON file.

  lated serve [--host H] [--port P]
  lated fit input.json          # {"photometry": {...}, "config": {...}}
  lated bands                   # list bundled filters
  lated lines                   # show the default line registry
"""

import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="lated",
        description=(__doc__ or "LATED inference").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_serve = sub.add_parser("serve", help="run the web application")
    ap_serve.add_argument("--host", default="127.0.0.1")
    ap_serve.add_argument("--port", type=int, default=8321)

    ap_fit = sub.add_parser("fit", help="fit photometry from a JSON file")
    ap_fit.add_argument("input", help="JSON with 'photometry' and 'config'")

    sub.add_parser("bands", help="list available filters")
    sub.add_parser("lines", help="show the default line registry")

    args = ap.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn
        from .server.app import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port)
    elif args.cmd == "fit":
        from pydantic import ValidationError

        from .config import FitConfig
        from .engine import fit
        try:
            with open(args.input) as fh:
                payload = json.load(fh)
            phot_in = payload["photometry"]
            cfg = FitConfig.model_validate(payload["config"])
            phot = {b: (float(v[0]), float(v[1]))
                    for b, v in phot_in.items()}
            res = fit(phot, cfg)
        except KeyError as exc:
            sys.exit(f"error: input JSON needs 'photometry' (band -> "
                     f"[flux_uJy, err_uJy]) and 'config' (missing {exc})")
        except (ValidationError, ValueError, TypeError, OSError,
                json.JSONDecodeError) as exc:
            sys.exit(f"error: {exc}")
        json.dump(res.model_dump(), sys.stdout, indent=2, allow_nan=False)
        print()
    elif args.cmd == "bands":
        from .filters import default_filters, filter_group
        fs = default_filters()
        for name in fs.names():
            f = fs[name]
            print(f"{name:12s} {filter_group(name):22s} "
                  f"pivot {f.pivot:9.1f} AA")
    elif args.cmd == "lines":
        from .config import default_lines
        for l in default_lines():
            tie = (f" = {l.ratio:.4f} x {l.tied_to}" if l.role == "tied" else "")
            print(f"{l.name:12s} {l.rest_wave:9.2f} AA  {l.role:5s}{tie}")


if __name__ == "__main__":
    main()
