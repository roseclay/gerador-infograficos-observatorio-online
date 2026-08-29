from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.configuration import empty_config
from src.metrics import MetricResult, write_audit
from src.templates.base import TemplateContext
from src.templates.institucional_claro_v1.layout import build_page_plan
from src.templates.registry import get_template_registry


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ICONS = {
    "pesquisadores",
    "grupos_pesquisa",
    "pos_graduacao",
    "instituicoes",
    "producao_cientifica",
    "municipios",
    "doutorado",
    "bolsa_produtividade",
    "producao_tecnica",
}


def _metric(index: int) -> MetricResult:
    icons = ["people", "network", "graduation", "institution", "globe", "pin", "medal", "award", "document"]
    labels = [
        "Pesqui" + "sadores",
        "Grupos de" + " pesquisa",
        "Programas de pós-graduação",
        "Instituições",
        "Produção científica",
        "Municípios",
        "Doutorado",
        "Bolsa de produtividade",
        "Produção técnica",
    ]
    section = "Indicadores principais" if index <= 4 else "Alcance" if index <= 6 else "Indicadores complementares"
    section_order = 1 if index <= 4 else 2 if index <= 6 else 3
    return MetricResult(
        f"m{index:02d}",
        labels[(index - 1) % len(labels)],
        section,
        "valor",
        "direct_value",
        "sem filtro",
        index,
        f"{index * 10}",
        "valor direto",
        "2026",
        "Fonte institucional de teste",
        icon=icons[(index - 1) % len(icons)],
        color="#0057B8",
        order=index,
        section_order=section_order,
    )


def _context(count: int) -> TemplateContext:
    metrics = [_metric(index) for index in range(1, count + 1)]
    metadata = {
        "header": "OBSERVATÓRIO DE CIÊNCIA, TECNOLOGIA E INOVAÇÃO DA BAHIA",
        "title": "Painel institucional",
        "subtitle": "Resumo dos dados carregados.",
        "source": "Fonte institucional de teste",
        "period": "2026",
        "updated_at": "25/08/2026",
        "cta": "Explore os dados",
    }
    return TemplateContext(
        metrics=metrics,
        metadata=metadata,
        assets={
            "observatorio_logo": ROOT / "assets" / "logo_inexistente.jpeg",
            "bahia_logo": ROOT / "assets" / "logo_estado_bahia.jpeg",
        },
        config=empty_config(["indicador", "valor"], "teste.csv"),
    )


def test_registry_lists_only_the_public_institutional_template():
    templates = get_template_registry().public_templates()

    assert [item.metadata.id for item in templates] == ["institucional_claro_v1"]
    metadata = templates[0].metadata
    assert metadata.name == "Institucional claro"
    assert metadata.version == "1.0"
    assert metadata.capacity_per_page == 9
    assert metadata.thumbnail.exists()
    assert metadata.reference.exists()
    assert metadata.production_base.exists()
    assert Image.open(metadata.production_base).size == (1122, 1402)


def test_template_icon_assets_exist_and_are_nonempty():
    icons_dir = ROOT / "assets" / "icons" / "institucional_claro_v1"

    for icon in EXPECTED_ICONS:
        path = icons_dir / f"{icon}.png"
        assert path.exists(), icon
        image = Image.open(path).convert("RGBA")
        assert image.getbbox(), icon


def test_renderer_uses_clean_matrix_and_never_opens_reference(monkeypatch, tmp_path: Path):
    from src.templates.institucional_claro_v1 import renderer as module

    opened: list[str] = []
    original_open = module.Image.open

    def tracked_open(path, *args, **kwargs):
        text = str(path)
        opened.append(text)
        assert "institucional_claro_v1_referencia" not in text
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(module.Image, "open", tracked_open)
    template = get_template_registry().get("institucional_claro_v1")
    report = template.render(_context(9), tmp_path / "info.png", tmp_path / "info.pdf")

    assert Path(report.output_png).exists()
    assert Path(report.output_pdf).exists()
    assert report.width == 1122
    assert report.height == 1402
    assert report.template_id == "institucional_claro_v1"
    assert any("base_9_indicadores.png" in path for path in opened)
    assert len(report.slot_map) == 9


def test_template_paginates_more_than_nine_indicators(tmp_path: Path):
    template = get_template_registry().get("institucional_claro_v1")

    ten = template.render_pages(_context(10), tmp_path, "dez", tmp_path / "dez.pdf")
    eighteen = template.render_pages(_context(18), tmp_path, "dezoito", tmp_path / "dezoito.pdf")

    assert len(ten.png_pages) == 2
    assert len(eighteen.png_pages) == 2
    assert Path(ten.output_pdf).exists()
    assert Path(eighteen.output_pdf).exists()
    assert all(Path(path).exists() for path in ten.png_pages + eighteen.png_pages)


def test_template_compacts_footer_when_call_to_action_is_empty(tmp_path: Path):
    template = get_template_registry().get("institucional_claro_v1")
    context = _context(9)
    compact_metadata = dict(context.metadata)
    compact_metadata["cta"] = ""
    compact = TemplateContext(context.metrics, compact_metadata, context.assets, context.config)

    report = template.render(compact, tmp_path / "compacto.png")
    image = Image.open(report.output_png)

    assert report.height < 1402
    assert image.size == (1122, report.height)


def test_layout_variants_do_not_plan_empty_slots():
    for count in range(1, 10):
        plan = build_page_plan([_metric(index) for index in range(1, count + 1)])
        assert len(plan.slots) == count


def test_audit_records_template_page_slot_and_icon(tmp_path: Path):
    template = get_template_registry().get("institucional_claro_v1")
    context = _context(2)
    report = template.render(context, tmp_path / "info.png")

    audit = write_audit(
        context.metrics,
        tmp_path / "auditoria.csv",
        template={"id": report.template_id, "version": report.template_version},
        slot_map=report.slot_map,
        mode="manual",
        csv_name="entrada.csv",
    )

    assert audit.iloc[0]["template"] == "institucional_claro_v1"
    assert audit.iloc[0]["versao do template"] == "1.0"
    assert audit.iloc[0]["pagina"] == 1
    assert audit.iloc[0]["slot"] == "principal_1"
    assert audit.iloc[0]["icone"] == "pesquisadores"
    assert audit.iloc[0]["arquivo CSV"] == "entrada.csv"
