"""Prepare bounded visual inputs locally. Never modify the user's drawing."""

from __future__ import annotations

import math
import tempfile
from contextlib import closing
from pathlib import Path

MAX_PAGES = 12
MAX_SIDE = 4096
MAX_FILE_BYTES = 50 * 1024 * 1024


def choose_drawing() -> Path | None:
    try:
        import tkinter
        from tkinter import filedialog

        window = tkinter.Tk()
        window.withdraw()
        try:
            selected = filedialog.askopenfilename(
                title="Select a CATIA reference drawing (PNG, JPEG or PDF)",
                filetypes=[("Drawings", "*.png *.jpg *.jpeg *.pdf")])
        finally:
            window.destroy()
    except Exception as exc:
        raise ValueError("File picker unavailable. Use windows_launcher.py start "
                         "--drawing PATH, or paste a PNG into START_CATIA_AI.cmd's chat.") from exc
    return Path(selected) if selected else None


def prepare_drawing(source: Path, output_root: Path) -> list[Path]:
    """Render all PDF pages or normalize photo orientation into fresh PNGs.

    144 dpi, capped at 4096 pixels per side. Reject oversized documents instead
    of silently omitting sheets. The agent must still ask about unreadable sizes.
    """
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"Drawing not found: {source}")
    if source.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise ValueError("Use PNG, JPEG or PDF. Export HEIC to PNG/JPEG first.")
    if source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Drawing exceeds 50 MB. Provide a smaller file or selected sheets.")
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError("Drawing dependencies missing. Run INSTALL.cmd.") from exc
    output_root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="drawing-", dir=output_root)).resolve()
    try:
        if source.suffix.lower() != ".pdf":
            with Image.open(source) as original:
                if getattr(original, "n_frames", 1) != 1:
                    raise ValueError("Animated/multiframe images are not supported.")
                with ImageOps.exif_transpose(original) as oriented:
                    oriented.thumbnail((MAX_SIDE, MAX_SIDE))
                    path = folder / "page-001.png"
                    oriented.save(path, format="PNG")
            return [path]

        import pypdfium2 as pdfium

        paths = []
        with pdfium.PdfDocument(source) as document:
            if not 1 <= len(document) <= MAX_PAGES:
                raise ValueError(f"PDF must contain 1-{MAX_PAGES} pages; none were attached.")
            for index in range(len(document)):
                with closing(document[index]) as page:
                    width, height = page.get_size()
                    if any(not math.isfinite(v) or v <= 0 for v in (width, height)):
                        raise ValueError(f"Invalid size on PDF page {index + 1}")
                    scale = min(2.0, MAX_SIDE / max(width, height))
                    with closing(page.render(scale=scale)) as bitmap, bitmap.to_pil() as picture:
                        path = folder / f"page-{index + 1:03}.png"
                        picture.save(path, format="PNG")
                        paths.append(path)
        return paths
    except Exception as exc:
        # Keep partial output for diagnosis; never attach a partial drawing.
        raise ValueError(f"Cannot prepare drawing; no pages attached: {exc}") from exc
