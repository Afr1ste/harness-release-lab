from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import compare, read_report, run_suite
from .scenarios import load_suite


def main():
    parser = argparse.ArgumentParser(prog="hrl", description="State-based agent release gates")
    parser.add_argument("--root", type=Path, default=Path(".lab"), help="artifact directory")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run a release contract")
    run.add_argument("--target", default="reference-fixed")
    run.add_argument("--suite", type=Path)
    run.add_argument("--label", default="", help="release or experiment label")
    run.add_argument(
        "--dsh-patch",
        type=Path,
        action="append",
        default=[],
        help="additional native DSH profile patch (repeatable)",
    )
    demo = commands.add_parser("demo", help="run a faulty/fixed pair of controls")
    demo.add_argument("--dsh", action="store_true", help="use the real DSH runtime")
    diff = commands.add_parser("compare", help="compare JSON reports from the same suite")
    diff.add_argument("baseline", type=Path)
    diff.add_argument("candidate", type=Path)
    serve = commands.add_parser("serve", help="open the local dashboard service")
    serve.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    try:
        if args.command == "run":
            report = run_suite(
                load_suite(args.suite),
                args.target,
                args.root,
                dsh_patches=tuple(args.dsh_patch),
                label=args.label,
            )
            summarize(report, args.root)
            return 0 if report.passed else 1
        if args.command == "demo":
            prefix = "dsh" if args.dsh else "reference"
            suite = load_suite()
            baseline = run_suite(suite, prefix + "-broken", args.root)
            candidate = run_suite(suite, prefix + "-fixed", args.root)
            summarize(baseline, args.root)
            summarize(candidate, args.root)
            result = compare(baseline, candidate)
            print(json.dumps(result, indent=2))
            return 0 if candidate.passed and not baseline.passed else 1
        if args.command == "compare":
            result = compare(read_report(args.baseline), read_report(args.candidate))
            print(json.dumps(result, indent=2))
            return 0 if result["release_allowed"] else 1
        if args.command == "serve":
            import uvicorn

            from .webapp import create_app

            print(f"Harness Release Lab: http://127.0.0.1:{args.port}")
            uvicorn.run(create_app(args.root), host="127.0.0.1", port=args.port)
            return 0
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"hrl: {exc}\n")


def summarize(report, root):
    count = sum(c.passed for c in report.cases)
    print(
        f"\n{'PASS' if report.passed else 'BLOCK'} {report.target}: "
        f"{count}/{len(report.cases)} contracts"
    )
    for case in report.cases:
        failed = ", ".join(c.name for c in case.checks if not c.passed)
        print(
            f"  {'PASS' if case.passed else 'FAIL'} {case.scenario.id}"
            + (f" [{failed}]" if failed else "")
        )
        if case.error:
            print(f"    {case.error[:600]}")
    print(f"  Report: {(root / 'runs' / report.id / 'report.html').resolve()}")


if __name__ == "__main__":
    raise SystemExit(main())
