from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_home_is_local_simple_and_has_no_rejected_archive_controls(monkeypatch, tmp_path):
    monkeypatch.setenv("INFOGRAPHICS_STORAGE_MODE", "persistent")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    button_labels = [button.label for button in app.button]
    assert "Novo infográfico" in button_labels
    assert any("Estúdio de Infográficos" in markdown.value for markdown in app.markdown)
    rejected = {
        "Modo legado", "Salvar no acervo", "Usar base do acervo", "Carregar matriz institucional vazia",
        "Baixar CSV atual", "Reorganizar grade", "Adicionar campo", "Migrar para JSON",
    }
    assert rejected.isdisjoint(button_labels)
    assert not any(expander.label == "Importar trabalho antigo" for expander in app.expander)
    assert not app.exception


def test_editor_has_compact_global_toolbar(monkeypatch):
    monkeypatch.setenv("INFOGRAPHICS_STORAGE_MODE", "persistent")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    next(button for button in app.button if button.label == "Novo infográfico").click()
    app.run()
    labels = [button.label for button in app.button]
    for expected in ("Início", "Novo", "Salvar", "Atualizar dados", "Exportar"):
        assert expected in labels
    assert "Voltar para infográficos" not in labels
    assert not app.exception


def test_editor_labels_explain_source_filter_and_data_update(monkeypatch):
    monkeypatch.setenv("INFOGRAPHICS_STORAGE_MODE", "persistent")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    next(button for button in app.button if button.label == "Novo infográfico").click()
    app.run()

    assert any(text_input.label == "Fonte dos dados" for text_input in app.text_input)
    assert not any(text_input.label == "Buscar campo" for text_input in app.text_input)
    assert any(uploader.label == "Arquivo CSV" for uploader in app.file_uploader)
    assert not app.exception


def test_cloud_home_explains_private_temporary_workspace(monkeypatch):
    monkeypatch.setenv("INFOGRAPHICS_STORAGE_MODE", "ephemeral")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()

    assert any("temporária e privada" in warning.value for warning in app.warning)
    assert not app.exception
