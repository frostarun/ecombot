"""Generate small eComBot PDF knowledge documents without extra dependencies.

Run from the ecombot directory:

    python scripts/generate_sample_pdfs.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT_DIR / "data" / "pdf"

DOCUMENTS = {
    "ecombot-support-policies.pdf": [
        (
            "eComBot Support Policies\n\n"
            "Returns and Replacements\n"
            "Most electronics are eligible for replacement within 7 days of delivery "
            "when the wrong item was delivered, the product is dead on arrival, or a "
            "verified hardware defect is found. Opened electronics are not eligible "
            "for return only because the customer changed their mind.\n\n"
            "Refund Processing\n"
            "Approved refunds are initiated within 2 business days after return "
            "validation. Bank and card processing can take 5 to 7 additional business "
            "days after the refund is initiated."
        ),
        (
            "eComBot Support Policies\n\n"
            "Warranty Claims\n"
            "To claim warranty, the customer should keep the invoice and contact "
            "support with the order ID, product name, purchase date, and issue "
            "description. Support should guide the customer to the relevant brand "
            "service process. Warranty generally covers manufacturing defects and "
            "does not cover physical damage, liquid damage, normal wear, or "
            "unauthorized repairs.\n\n"
            "Data Privacy\n"
            "Support should ask only for the minimum details needed to solve the "
            "case. Do not ask for card numbers, OTPs, passwords, or full payment "
            "credentials."
        ),
    ],
    "ecombot-shipping-guide.pdf": [
        (
            "eComBot Shipping Guide\n\n"
            "Standard Delivery\n"
            "Standard delivery usually takes 3 to 5 business days after dispatch "
            "for metro and tier-1 locations. Remote locations may take 6 to 8 "
            "business days depending on courier reach and weather conditions.\n\n"
            "Express Delivery\n"
            "Express delivery is available only for selected PIN codes and in-stock "
            "items. The checkout page shows express eligibility before payment."
        ),
        (
            "eComBot Shipping Guide\n\n"
            "Dispatch Rules\n"
            "Orders are dispatched only after payment authorization and inventory "
            "confirmation. Accessories that are in stock are usually dispatched "
            "within 24 hours. Large electronics may require additional protective "
            "packaging before dispatch.\n\n"
            "Tracking Help\n"
            "Customers should use the order ID for tracking questions. If the "
            "carrier tracking link is delayed, support should first verify the "
            "order status from the order system."
        ),
    ],
    "ecombot-product-warranty-guide.pdf": [
        (
            "eComBot Product Warranty Guide\n\n"
            "Galaxy A55 5G\n"
            "Galaxy A55 5G has a 1 year manufacturer warranty for device defects. "
            "Physical damage, liquid damage, and unauthorized repairs are excluded.\n\n"
            "Redmi Note 13 Pro\n"
            "Redmi Note 13 Pro has a 1 year manufacturer warranty for handset "
            "defects and 6 months warranty for in-box accessories."
        ),
        (
            "eComBot Product Warranty Guide\n\n"
            "StreamMax 4K TV Decoder\n"
            "StreamMax 4K TV Decoder has a 6 months service warranty for decoder "
            "hardware defects. Remote batteries and accidental damage are excluded.\n\n"
            "BassPro Wireless Earbuds\n"
            "BassPro Wireless Earbuds have a 6 months accessory warranty for "
            "manufacturing defects. Ear tips, scratches, and water damage beyond "
            "splash resistance are excluded."
        ),
    ],
}


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(text: str) -> bytes:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph.strip(), width=88))

    commands = ["BT", "/F1 11 Tf", "72 760 Td", "14 TL"]
    for line in lines:
        if line:
            commands.append(f"({_escape_pdf_text(line)}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def _write_pdf(path: Path, pages: list[str]) -> None:
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    page_object_numbers = [3 + index * 2 for index in range(len(pages))]
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))

    for index, page_text in enumerate(pages):
        page_obj_num = 3 + index * 2
        content_obj_num = page_obj_num + 1
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {3 + len(pages) * 2} 0 R >> >> "
                f"/Contents {content_obj_num} 0 R >>"
            ).encode("ascii")
        )
        stream = _page_stream(page_text)
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )

    path.write_bytes(pdf)


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for filename, pages in DOCUMENTS.items():
        _write_pdf(PDF_DIR / filename, pages)
        print(f"Wrote {PDF_DIR / filename}")


if __name__ == "__main__":
    main()
