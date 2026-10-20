import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from .models import RunReport


def html_report(report: RunReport) -> str:
    template = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
    # HTML's script parser terminates on </script> even in a JSON string.
    data = json.dumps(report.model_dump()).replace("<", "\\u003c").replace("&", "\\u0026")
    return template.replace("/*__REPORT__*/null", data)


def write_artifacts(report: RunReport, directory: Path):
    root = Element(
        "testsuite",
        name=report.suite_name,
        tests=str(len(report.cases)),
        failures=str(sum(not c.passed for c in report.cases)),
        time=str(report.duration_ms / 1000),
    )
    for case in report.cases:
        child = SubElement(
            root,
            "testcase",
            name=case.scenario.id,
            classname=report.target,
            time=str(case.duration_ms / 1000),
        )
        failed = [c for c in case.checks if not c.passed]
        if failed:
            node = SubElement(child, "failure", message=", ".join(c.name for c in failed))
            node.text = "\n".join(
                f"{c.name}: expected {c.expected!r}, observed {c.actual!r}" for c in failed
            )
        SubElement(child, "system-out").text = json.dumps(case.events)
    (directory / "junit.xml").write_text(tostring(root, encoding="unicode"), encoding="utf-8")
    (directory / "report.html").write_text(html_report(report), encoding="utf-8")
