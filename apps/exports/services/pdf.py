"""Render a tabular report (catalog payload) to PDF via WeasyPrint.

WeasyPrint is imported lazily so importing this module never fails if the native
rendering libraries are unavailable in a given environment.
"""

from html import escape


def report_to_html(report):
    """Minimal printable HTML for a ``{title, columns, rows}`` report payload."""
    head = "".join(f"<th>{escape(str(c))}</th>" for c in report["columns"])
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row) + "</tr>"
        for row in report["rows"]
    )
    return (
        "<html><head><style>"
        "body{font-family:sans-serif;font-size:11px}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccc;padding:4px;text-align:right}"
        "th:first-child,td:first-child{text-align:left}"
        "h2{font-size:14px}"
        "</style></head><body>"
        f"<h2>{escape(report.get('title', 'Report'))}</h2>"
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</body></html>"
    )


def report_to_pdf_bytes(report):
    """Return PDF bytes for a report payload (renders the HTML via WeasyPrint)."""
    from weasyprint import HTML  # lazy: native libs only needed when actually used

    return HTML(string=report_to_html(report)).write_pdf()
