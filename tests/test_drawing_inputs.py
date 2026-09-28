"""Real PDF rasterization tests; never start Codex or call CATIA."""

import pytest

from scripts import drawing_inputs as drawing

Image = pytest.importorskip("PIL.Image")
pytest.importorskip("pypdfium2")


def pdf_fixture(pages=2):
    """Tiny vector drawing with explicit page order, labels and dimensions."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               (f"<< /Type /Pages /Count {pages} /Kids [" +
                " ".join(f"{4 + i * 2} 0 R" for i in range(pages)) + "] >>").encode(),
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for i in range(pages):
        objects.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 300] "
                        "/Resources << /Font << /F1 3 0 R >> >> "
                        f"/Contents {5 + i * 2} 0 R >>").encode())
        stream = ("2 w 80 80 240 120 re S "
                  "BT /F1 18 Tf 160 220 Td (40 mm) Tj ET "
                  "BT /F1 18 Tf 10 130 Td (20 mm) Tj ET "
                  f"BT /F1 14 Tf 80 40 Td (Drawing page {i + 1}) Tj ET").encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() +
                       stream + b"\nendstream")
    result = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{pos:010} 00000 n \n".encode() for pos in offsets[1:])
    return result + (f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                     f"startxref\n{xref}\n%%EOF\n").encode()


def test_pdf_all_pages_in_order_and_source_unchanged(tmp_path):
    source = tmp_path / "drawing.pdf"
    original = pdf_fixture()
    source.write_bytes(original)
    paths = drawing.prepare_drawing(source, tmp_path / "rendered")
    assert [p.name for p in paths] == ["page-001.png", "page-002.png"]
    assert source.read_bytes() == original
    for path in paths:
        with Image.open(path) as image:
            assert image.size == (800, 600)
            assert image.convert("L").getextrema() == (0, 255)
    assert paths[0].read_bytes() != paths[1].read_bytes()


def test_image_orientation_and_no_overwrite(tmp_path):
    source = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[274] = 6  # Camera orientation: rotate 90 degrees for display.
    with Image.new("RGB", (120, 60), "red") as image:
        image.save(source, exif=exif)
    original = source.read_bytes()
    first = drawing.prepare_drawing(source, tmp_path / "out")[0]
    second = drawing.prepare_drawing(source, tmp_path / "out")[0]
    assert first != second
    with Image.open(first) as image:
        assert image.size == (60, 120)
    assert source.read_bytes() == original


def test_pdf_does_not_silently_drop_pages(tmp_path):
    source = tmp_path / "too-many.pdf"
    source.write_bytes(pdf_fixture(drawing.MAX_PAGES + 1))
    with pytest.raises(ValueError, match="none were attached"):
        drawing.prepare_drawing(source, tmp_path / "out")
    assert not list((tmp_path / "out").rglob("*.png"))


@pytest.mark.parametrize("suffix", [".pdf", ".png"])
def test_corrupt_drawing_fails_without_attachment(tmp_path, suffix):
    source = tmp_path / ("bad" + suffix)
    source.write_bytes(b"not a drawing")
    with pytest.raises(ValueError, match="no pages attached"):
        drawing.prepare_drawing(source, tmp_path / "out")


def test_unsupported_missing_and_oversize_inputs(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="not found"):
        drawing.prepare_drawing(tmp_path / "missing.pdf", tmp_path / "out")
    source = tmp_path / "photo.heic"
    source.touch()
    with pytest.raises(ValueError, match="HEIC"):
        drawing.prepare_drawing(source, tmp_path / "out")
    source = tmp_path / "large.pdf"
    source.write_bytes(pdf_fixture())
    monkeypatch.setattr(drawing, "MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="50 MB"):
        drawing.prepare_drawing(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_large_image_is_bounded(tmp_path):
    source = tmp_path / "large.png"
    with Image.new("RGB", (5000, 100), "white") as image:
        image.save(source)
    with Image.open(drawing.prepare_drawing(source, tmp_path / "out")[0]) as image:
        assert max(image.size) <= drawing.MAX_SIDE
