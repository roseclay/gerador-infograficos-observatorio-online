import re

from src.free_canvas_component import COMPONENT_DIR, detect_image_mime, drag_canvas, image_data_url


def test_free_canvas_component_assets_are_packaged():
    index = COMPONENT_DIR / "index.html"
    text = index.read_text(encoding="utf-8")

    assert index.exists()
    assert "streamlit:componentReady" in text
    assert "streamlit:setComponentValue" in text
    assert "pointermove" in text
    assert "nwse-resize" in text
    assert "Campos disponíveis" in text
    assert "Buscar campo disponível" in text
    assert "startPalettePointer" in text
    assert "@media (max-width: 680px)" in text


def test_drag_updates_field_without_redrawing_the_canvas():
    text = (COMPONENT_DIR / "index.html").read_text(encoding="utf-8")
    match = re.search(r"function onPointerMove\(event\) \{(?P<body>.*?)\n    \}", text, re.DOTALL)

    assert match is not None
    assert "draw(false)" not in match.group("body")
    assert "updateFieldElement(field)" in match.group("body")
    assert "updateBadge()" in match.group("body")


def test_canvas_component_reports_field_placement():
    text = (COMPONENT_DIR / "index.html").read_text(encoding="utf-8")

    assert "placed: Boolean(field.placed)" in text
    assert "field.placed = true" in text
    assert "scrollMemory" in text


def test_canvas_only_draws_editing_handles_for_the_selected_field():
    text = (COMPONENT_DIR / "index.html").read_text(encoding="utf-8")

    assert "border: 1px solid transparent;" in text
    assert ".field.selected .handle" in text
    assert "display: none;" in text
    assert ".field:hover," not in text
    assert 'selectField("");' in text
    assert 'selectedId = fields[0]' not in text


def test_canvas_component_preserves_local_drop_until_streamlit_catches_up():
    text = (COMPONENT_DIR / "index.html").read_text(encoding="utf-8")

    assert "pendingLocalValue" in text
    assert "mergePendingLocalFields" in text
    assert "pendingIds.has" in text
    assert "pendingLocalValue.changed_ids" in text
    assert "font_size:" in text
    assert "originalFontSize" in text
    assert "faithfulPreview" in text
    assert "pending-sync" in text
    assert "syncStageFromArgs" in text
    assert "updatePreviewImage" in text
    assert "stage.dataset.ready" in text
    assert "fieldPreviewSrc" in text
    assert "field-render" in text
    assert "removeFieldFromCanvas" in text
    assert "Remover da arte" in text
    assert "onKeyDown" in text
    assert "ArrowLeft" in text
    assert "event.shiftKey ? 10 : 1" in text
    assert "Backspace" in text
    assert "scheduleComponentValue" in text
    assert "changedFieldIds" in text
    assert "changed_ids: Array.from(changedFieldIds)" in text
    assert "changedFieldProperties" in text
    assert "changed_properties: Object.fromEntries" in text
    assert 'changedMode === "resize" ? ["width", "height", "font_size"] : ["x", "y"]' in text
    assert "pendingLocalRenders" not in text
    assert "Campo e posição" in text
    assert "Situação" in text
    assert "field-meta" in text
    assert 'Math.max(1, field.font_size * scale)' in text


def test_drag_canvas_uses_renderer_preview_when_provided(monkeypatch):
    calls = []

    def fake_component():
        def invoke(**kwargs):
            calls.append(kwargs)
            return kwargs["default"]

        return invoke

    monkeypatch.setattr("src.free_canvas_component._component", fake_component)
    result = drag_canvas(
        b"\x89PNG\r\n\x1a\nbase",
        [{"id": "campo_001", "placed": True, "x": 10, "y": 20, "width": 30, "height": 40, "font_size": 50}],
        (100, 80),
        field_preview_bytes={"campo_001": b"\x89PNG\r\n\x1a\npreview"},
    )

    assert result["fields"][0]["font_size"] == 50
    assert result["changed_ids"] == []
    assert calls[0]["faithfulPreview"] is True
    assert calls[0]["image"] == calls[0]["baseImage"]
    assert "campo_001" in calls[0]["fieldPreviews"]


def test_image_data_url_encodes_bytes():
    data_url = image_data_url(b"abc", "image/png")

    assert data_url == "data:image/png;base64,YWJj"


def test_detects_png_and_jpeg_mime_from_bytes():
    assert detect_image_mime(b"\x89PNG\r\n\x1a\nabc") == "image/png"
    assert detect_image_mime(b"\xff\xd8\xffabc") == "image/jpeg"
