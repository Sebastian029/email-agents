"""20 Newsgroups — 6 wybranych kategorii (comp.* + sci.electronics)."""

NEWSGROUP_LABELS = [
    "comp.graphics",
    "comp.os.ms-windows.misc",
    "comp.sys.ibm.pc.hardware",
    "comp.sys.mac.hardware",
    "comp.windows.x",
    "sci.electronics",
]

CATEGORIES_DESCRIPTION = """
- comp.graphics (grafika komputerowa, formaty obrazów, renderowanie)
- comp.os.ms-windows.misc (system Microsoft Windows, konfiguracja, problemy)
- comp.sys.ibm.pc.hardware (sprzęt PC: płyty główne, dyski, pamięć)
- comp.sys.mac.hardware (sprzęt Apple Macintosh)
- comp.windows.x (środowisko graficzne X Window na Unix/Linux)
- sci.electronics (elektronika, układy, schematy, komponenty)
"""

DEFAULT_LABEL = "comp.graphics"
