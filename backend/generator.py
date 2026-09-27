from __future__ import annotations

import io
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TEMPLATES = {
    "complaint_letter": "COMPLAINT LETTER\n\nDate: {date}\n\nFrom:\n{name}\n{address}\n\nSubject: Complaint\n\nI am writing to raise the following complaint:\n{issue_description}\n\nI request timely resolution of this matter.\n\nSincerely,\n{name}",
    "rental_agreement": "RENTAL AGREEMENT\n\nDate: {date}\n\nThis Rental Agreement is made with {name}, residing at {address}.\n\nTerms:\n{issue_description}\n\nBoth parties agree to comply with the rental terms stated above.",
}


def render_template(template_type: str, payload: dict[str, str]) -> str:
    template = TEMPLATES.get(template_type)
    if not template:
        raise ValueError("Unsupported template type")
    return template.format(**payload)


def build_pdf(content: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y_position = height - 50
    for line in content.splitlines():
        wrapped_lines = wrap(line, width=95) or [""]
        for wrapped_line in wrapped_lines:
            pdf.drawString(40, y_position, wrapped_line)
            y_position -= 18
            if y_position < 60:
                pdf.showPage()
                y_position = height - 50
    pdf.drawString(40, 30, "This platform provides AI-generated legal assistance and does not replace a licensed lawyer.")
    pdf.save()
    return buffer.getvalue()
