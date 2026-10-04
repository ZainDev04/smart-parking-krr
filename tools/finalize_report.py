"""Fill in the contents, figure and table lists and page numbers using Word.

    python tools/finalize_report.py [--pdf]

Needs Windows with Microsoft Word and pywin32. Opens the built report,
updates every field twice (page numbers settle on the second pass), saves
it, prints the page count and optionally exports a PDF next to it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "report" / "Smart_Parking_KRR_CCP_Report.docx"


def finalize(path: Path = REPORT, pdf: bool = False) -> int:
    import win32com.client

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(path.resolve()))
        # compact contents and caption lists: TOC 1, TOC 2, Table of Figures
        for style_id in (-20, -21, -36):
            st = doc.Styles(style_id)
            st.Font.Name = "Times New Roman"
            st.Font.Size = 10
            st.ParagraphFormat.SpaceBefore = 0
            st.ParagraphFormat.SpaceAfter = 0
            st.ParagraphFormat.LineSpacingRule = 0      # single
        for _ in range(2):
            doc.Fields.Update()
            for toc in doc.TablesOfContents:
                toc.Update()
            doc.Repaginate()
        pages = doc.ComputeStatistics(2)       # wdStatisticPages
        doc.Save()
        if pdf:
            # 17 = PDF; IncludeDocProps carries the title and authors into the PDF
            doc.ExportAsFixedFormat(OutputFileName=str(path.with_suffix(".pdf").resolve()),
                                    ExportFormat=17, IncludeDocProps=True)
        doc.Close(False)
    finally:
        word.Quit()
    print(f"  {path.name}: {pages} pages")
    return pages


if __name__ == "__main__":
    finalize(pdf="--pdf" in sys.argv)
