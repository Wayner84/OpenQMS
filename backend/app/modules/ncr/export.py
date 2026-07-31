"""PDF export for NCR reports, per docs/modules/NCR.md and the Milestone 4 plan's
design decision 8: `reportlab` (pure-Python, no native system dependencies), not
`WeasyPrint` or a headless browser. An incomplete NCR (`status != closed`) still
renders every section, but the parts that aren't finished yet (root cause summary,
investigation tools, closed date) show a blank/placeholder line instead of being
omitted, matching the spec's "export incomplete NCRs with blank printable
sections" requirement; a closed NCR renders as a fully-populated report.

`gather_ncr_export_data` resolves human-readable labels (person names, product
part numbers, supplier company names, document titles) via each owning module's
own `service.py` functions, never their models directly, per the module-isolation
rule. `render_ncr_pdf` is a pure function (data in, PDF bytes out) so it can be
unit-tested without a database.
"""

import io
import uuid
from dataclasses import dataclass
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.service import DocumentNotFoundError, get_document
from app.modules.ncr.models import (
    Ncr,
    NcrAction,
    NcrAttachment,
    NcrInvestigationTool,
    NcrInvestigationToolType,
    NcrStatus,
    NcrStatusHistory,
)
from app.modules.ncr.service import get_ncr
from app.modules.people.service import get_company, get_person
from app.modules.products.service import get_product
from app.modules.suppliers.service import get_supplier

NOT_YET_COMPLETED = "Not yet completed"
NOT_STARTED = "Not started"
DOCUMENT_UNAVAILABLE = "[Document no longer available]"


@dataclass
class NcrExportData:
    ncr: Ncr
    raised_by_name: str
    product_label: str | None
    supplier_label: str | None
    status_history: list[NcrStatusHistory]
    actions: list[tuple[NcrAction, str | None]]
    tools: dict[NcrInvestigationToolType, NcrInvestigationTool | None]
    attachments: list[tuple[NcrAttachment, str]]


async def _resolve_document_title(
    session: AsyncSession, *, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> str:
    """A document attached to an NCR can later be soft-deleted independently (the
    Document Management module has no awareness of NCR attachments, per the
    module-isolation rule, so nothing blocks this) -- unlike `product_id`/
    `supplier_id`/`raised_by_id`/`owner_id`, which are protected by a plain FK
    with no `ON DELETE`, making the referenced row un-deletable while the NCR
    exists. Falls back to a placeholder rather than failing the whole export."""
    try:
        document = await get_document(
            session, organisation_id=organisation_id, document_id=document_id
        )
    except DocumentNotFoundError:
        return DOCUMENT_UNAVAILABLE
    return document.title


async def gather_ncr_export_data(
    session: AsyncSession, *, organisation_id: uuid.UUID, ncr_id: uuid.UUID
) -> NcrExportData:
    """Raises `NcrNotFoundError` (via `get_ncr`) if the NCR doesn't exist in the
    caller's organisation."""
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)

    raised_by = await get_person(
        session, organisation_id=organisation_id, person_id=ncr.raised_by_id
    )
    raised_by_name = f"{raised_by.first_name} {raised_by.last_name}"

    product_label = None
    if ncr.product_id is not None:
        product = await get_product(
            session, organisation_id=organisation_id, product_id=ncr.product_id
        )
        product_label = f"{product.part_number} — {product.description}"

    supplier_label = None
    if ncr.supplier_id is not None:
        supplier = await get_supplier(
            session, organisation_id=organisation_id, supplier_id=ncr.supplier_id
        )
        company = await get_company(
            session, organisation_id=organisation_id, company_id=supplier.company_id
        )
        supplier_label = company.name

    status_history = list(
        (
            await session.execute(
                select(NcrStatusHistory)
                .where(NcrStatusHistory.ncr_id == ncr_id)
                .order_by(NcrStatusHistory.changed_at)
            )
        )
        .scalars()
        .all()
    )

    action_rows = list(
        (
            await session.execute(
                select(NcrAction).where(NcrAction.ncr_id == ncr_id).order_by(NcrAction.created_at)
            )
        )
        .scalars()
        .all()
    )
    actions: list[tuple[NcrAction, str | None]] = []
    for action in action_rows:
        owner_name = None
        if action.owner_id is not None:
            owner = await get_person(
                session, organisation_id=organisation_id, person_id=action.owner_id
            )
            owner_name = f"{owner.first_name} {owner.last_name}"
        actions.append((action, owner_name))

    tool_rows = list(
        (
            await session.execute(
                select(NcrInvestigationTool).where(NcrInvestigationTool.ncr_id == ncr_id)
            )
        )
        .scalars()
        .all()
    )
    tools_by_type = {tool.tool_type: tool for tool in tool_rows}
    tools = {tool_type: tools_by_type.get(tool_type) for tool_type in NcrInvestigationToolType}

    attachment_rows = list(
        (
            await session.execute(
                select(NcrAttachment)
                .where(NcrAttachment.ncr_id == ncr_id)
                .order_by(NcrAttachment.created_at)
            )
        )
        .scalars()
        .all()
    )
    attachments: list[tuple[NcrAttachment, str]] = []
    for attachment in attachment_rows:
        title = await _resolve_document_title(
            session, organisation_id=organisation_id, document_id=attachment.document_id
        )
        attachments.append((attachment, title))

    return NcrExportData(
        ncr=ncr,
        raised_by_name=raised_by_name,
        product_label=product_label,
        supplier_label=supplier_label,
        status_history=status_history,
        actions=actions,
        tools=tools,
        attachments=attachments,
    )


_TOOL_LABELS = {
    NcrInvestigationToolType.FIVE_WHY: "5 Why",
    NcrInvestigationToolType.FISHBONE: "Fishbone / Ishikawa",
    NcrInvestigationToolType.EIGHT_D: "8D",
    NcrInvestigationToolType.TEN_D: "10D",
}

_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
    ]
)


def render_ncr_pdf(data: NcrExportData) -> bytes:
    """Render `data` as a PDF report. Uncompressed (`pageCompression=0`) so the
    output's text is byte-searchable, which both keeps small reports simple and
    lets tests assert on rendered content without a PDF parser."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        pageCompression=0,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"NCR {data.ncr.number}",
    )
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("NcrHeading", parent=styles["Heading2"], spaceBefore=10, spaceAfter=4)
    body = styles["BodyText"]

    ncr = data.ncr
    is_closed = ncr.status == NcrStatus.CLOSED
    story: list[object] = []

    story.append(Paragraph(f"Non-Conformance Report {ncr.number}", styles["Title"]))
    story.append(
        Paragraph(
            "Final Report (Closed)" if is_closed else f"Draft — In Progress ({ncr.status.value})",
            styles["Heading3"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    metadata_rows = [
        ["Field", "Value"],
        ["Number", ncr.number],
        ["Type", ncr.type.value],
        ["Status", ncr.status.value],
        ["Raised by", data.raised_by_name],
        ["Product", data.product_label or "—"],
        ["Supplier", data.supplier_label or "—"],
        ["Created", ncr.created_at.isoformat(sep=" ", timespec="minutes")],
        [
            "Closed",
            ncr.closed_at.isoformat(sep=" ", timespec="minutes")
            if ncr.closed_at is not None
            else NOT_YET_COMPLETED,
        ],
    ]
    metadata_table = Table(metadata_rows, colWidths=[40 * mm, 120 * mm])
    metadata_table.setStyle(_TABLE_STYLE)
    story.append(metadata_table)

    story.append(Paragraph("Description", heading))
    story.append(Paragraph(escape(ncr.description), body))

    story.append(Paragraph("Root Cause Summary", heading))
    root_cause = escape(ncr.root_cause_summary) if ncr.root_cause_summary else NOT_YET_COMPLETED
    story.append(Paragraph(root_cause, body))

    story.append(Paragraph("Status History", heading))
    if data.status_history:
        history_rows = [["From", "To", "Changed at", "Comments"]]
        for entry in data.status_history:
            history_rows.append(
                [
                    entry.from_status.value if entry.from_status is not None else "—",
                    entry.to_status.value,
                    entry.changed_at.isoformat(sep=" ", timespec="minutes"),
                    entry.comments or "",
                ]
            )
        history_table = Table(history_rows, colWidths=[28 * mm, 28 * mm, 38 * mm, 66 * mm])
        history_table.setStyle(_TABLE_STYLE)
        story.append(history_table)
    else:
        story.append(Paragraph(NOT_YET_COMPLETED, body))

    story.append(Paragraph("Actions", heading))
    if data.actions:
        action_rows = [["Description", "Owner", "Due date", "Status"]]
        for action, owner_name in data.actions:
            action_rows.append(
                [
                    action.description,
                    owner_name or "—",
                    action.due_date.isoformat() if action.due_date is not None else "—",
                    action.status.value,
                ]
            )
        actions_table = Table(action_rows, colWidths=[70 * mm, 40 * mm, 25 * mm, 25 * mm])
        actions_table.setStyle(_TABLE_STYLE)
        story.append(actions_table)
    else:
        story.append(Paragraph("No actions recorded.", body))

    story.append(Paragraph("Investigation Tools", heading))
    for tool_type in NcrInvestigationToolType:
        story.append(Paragraph(_TOOL_LABELS[tool_type], styles["Heading4"]))
        tool = data.tools.get(tool_type)
        if tool is None or not tool.data:
            story.append(Paragraph(NOT_STARTED, body))
            continue
        for key in sorted(tool.data.keys()):
            # tool.data is arbitrary, user-supplied JSON (an evolving worksheet, per
            # NcrInvestigationTool's docstring) -- both the key and the value must be
            # escaped before being interpolated into a Paragraph's markup, or a key/
            # value containing something reportlab's mini-markup parses as a tag
            # (e.g. an unterminated "<b>") raises a ValueError and 500s the export.
            escaped_key = escape(str(key))
            escaped_value = escape(str(tool.data[key]))
            story.append(Paragraph(f"<b>{escaped_key}:</b> {escaped_value}", body))

    story.append(Paragraph("Attachments", heading))
    if data.attachments:
        attachment_rows = [["Document", "Description"]]
        for attachment, title in data.attachments:
            attachment_rows.append([title, attachment.description or ""])
        attachments_table = Table(attachment_rows, colWidths=[70 * mm, 90 * mm])
        attachments_table.setStyle(_TABLE_STYLE)
        story.append(attachments_table)
    else:
        story.append(Paragraph("No attachments.", body))

    doc.build(story)
    return buffer.getvalue()
