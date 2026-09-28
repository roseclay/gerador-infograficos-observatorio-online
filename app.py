from __future__ import annotations

import base64
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
import hashlib
import uuid

import pandas as pd
from PIL import Image
import streamlit as st
import yaml

from src.configuration import (
    DEFAULT_HEADER,
    aggregate_indicators_from_dataframe,
    apply_sections_to_indicators,
    clear_indicators,
    config_compatibility,
    csv_schema_signature,
    duplicate_indicator,
    empty_config,
    export_names,
    new_indicator,
    normalize_config,
    remove_indicator,
    reorder_indicators,
    sections_from_indicators,
    update_schema,
)
from src.data_loader import load_csv, save_used_data
from src.data_binding import (
    fields_from_dataset_observations,
    make_chart_element,
    make_dimension_chart_element,
    rows_as_indicator_observations,
)
from src.free_canvas_component import drag_canvas
from src.local_workspace import (
    LocalInfographicWorkspace,
    LocalWorkspaceError,
    UpdatePreview,
    is_ephemeral_environment,
    sha256_bytes,
)
from src.free_mode import (
    ALIGN_OPTIONS,
    FIELD_COLUMNS,
    build_free_mode_config_with_name,
    changed_dragged_fields,
    fields_from_dataframe,
    fields_to_dataframe,
    free_mode_export_names,
    merge_dragged_fields,
    new_text_field,
    normalize_fields,
    render_free_field_preview_map,
    render_free_infographic,
    write_fields_csv,
)
from src.icon_registry import (
    DEFAULT_COLOR,
    DEFAULT_ICON,
    ICON_CATEGORIES,
    INSTITUTIONAL_PALETTE,
    apply_appearance_to_all,
    apply_appearance_to_indicator,
    apply_appearance_to_section,
    icon_label,
    icon_preview_image,
    icons_for_gallery,
    normalize_hex_color,
    normalize_icon_name,
)
from src.inference_engine import infer_config, write_automatic_audit
from src.metrics import OPERATION_LABELS, calculate_metrics, write_audit
from src.preview_state import DEFAULT_PREVIEW_RATIO, clamp_preview_ratio, fallback_preview_ratio, panel_widths
from src.renderer import (
    render_card_thumbnail,
    render_infographic as render_compat_infographic,
    render_infographic_pages as render_compat_infographic_pages,
    write_validation_report,
)
from src.semantic_rules import CUSTOM_RULES_PATH, normalize_text, save_custom_rule
from src.templates.base import LEGACY_TEMPLATE_ID, TemplateContext, normalize_template_config
from src.templates.registry import get_template_registry
from src.validation import validate_metric_configs, validate_required_metadata


ROOT = Path(__file__).parent
EXAMPLES_DIR = ROOT / "examples"
OUTPUT_DIR = ROOT / "output"
WORKSPACE_DIR = ROOT / "workspace"

SEPARATOR_OPTIONS = ["Automático", "Ponto e vírgula (;)", "Vírgula (,)", "Tabulação", "Barra vertical (|)"]
ENCODING_OPTIONS = ["Automática", "utf-8-sig", "utf-8", "cp1252", "latin1"]
HEADER_OPTIONS = ["Automático", "Sim", "Não"]
FILTER_OPERATORS = ["equals", "contains", "not_empty"]
FREE_MODE_LABEL = "Imagem-base (padrão)"
ADVANCED_MODE_LABEL = "Indicadores por CSV (avançado)"
INDICATOR_COLUMNS = [
    "enabled",
    "id",
    "label",
    "section",
    "column",
    "operation",
    "filter_column",
    "filter_operator",
    "filter_value",
    "match_value",
    "numerator_column",
    "denominator_column",
    "prefix",
    "suffix",
    "decimals",
    "order",
    "icon",
    "color",
]


def separator_value(label: str) -> str | None:
    return {
        "Automático": None,
        "Ponto e vírgula (;)": ";",
        "Vírgula (,)": ",",
        "Tabulação": "\t",
        "Barra vertical (|)": "|",
    }[label]


def header_value(label: str) -> bool | None:
    return {"Automático": None, "Sim": True, "Não": False}[label]


def reset_editor_state() -> None:
    st.session_state["editor_nonce"] = int(st.session_state.get("editor_nonce", 0)) + 1
    st.session_state["appearance_dialog_open"] = False


def init_state() -> None:
    st.session_state.setdefault("workflow_mode", FREE_MODE_LABEL)
    st.session_state.setdefault("csv_bytes", None)
    st.session_state.setdefault("csv_name", "")
    st.session_state.setdefault("csv_digest", "")
    st.session_state.setdefault("demo_mode", False)
    st.session_state.setdefault("current_config", empty_config())
    st.session_state.setdefault("active_schema_signature", "")
    st.session_state.setdefault("separator_label", "Automático")
    st.session_state.setdefault("encoding_label", "Automática")
    st.session_state.setdefault("header_label", "Automático")
    st.session_state.setdefault("editor_nonce", 0)
    st.session_state.setdefault("appearance_dialog_open", False)
    st.session_state.setdefault("appearance_target_id", "")
    st.session_state.setdefault("preview_ratio", DEFAULT_PREVIEW_RATIO)
    st.session_state.setdefault("preview_minimized", False)
    st.session_state.setdefault("preview_fit_width", True)
    st.session_state.setdefault("preview_zoom", 70)
    st.session_state.setdefault("auto_proposal", None)
    st.session_state.setdefault("free_base_image_bytes", None)
    st.session_state.setdefault("free_base_image_name", "")
    st.session_state.setdefault("free_base_image_digest", "")
    st.session_state.setdefault("free_base_image_size", (0, 0))
    st.session_state.setdefault("free_expected_base_image_name", "")
    st.session_state.setdefault("free_project_name", "")
    st.session_state.setdefault("free_screen", "home")
    st.session_state.setdefault("free_fields", [])
    st.session_state.setdefault("free_field_csv_digest", "")
    st.session_state.setdefault("free_field_csv_name", "")
    st.session_state.setdefault("free_field_csv_warnings", [])
    st.session_state.setdefault("free_editor_nonce", 0)
    st.session_state.setdefault("free_project_id", "")
    st.session_state.setdefault("free_data_bytes", None)
    st.session_state.setdefault("free_data_name", "")
    st.session_state.setdefault("free_dirty", False)
    st.session_state.setdefault("free_selected_id", "")
    st.session_state.setdefault("local_selected_element", "")
    st.session_state.setdefault("local_control_field_id", "")
    st.session_state.setdefault("free_update_preview", None)
    st.session_state.setdefault("free_pending_action", "")
    st.session_state.setdefault("free_metadata", {})
    st.session_state.setdefault("local_source_input", "")
    st.session_state.setdefault("free_export_paths", [])
    st.session_state.setdefault("local_batch_preview", [])
    st.session_state.setdefault("local_batch_bytes", None)
    st.session_state.setdefault("local_batch_name", "")
    st.session_state.setdefault("local_delete_project_id", "")
    st.session_state.setdefault("ephemeral_workspace_id", uuid.uuid4().hex)


def set_csv_bytes(data: bytes, name: str, demo_mode: bool = False, config: dict | None = None) -> None:
    digest = hashlib.sha256(data).hexdigest()
    token = f"{name}:{digest}"
    if st.session_state.csv_digest == token and st.session_state.demo_mode == demo_mode:
        return
    st.session_state.csv_bytes = data
    st.session_state.csv_name = name
    st.session_state.csv_digest = token
    st.session_state.demo_mode = demo_mode
    st.session_state.current_config = normalize_config(config or empty_config(source=name), source=name)
    st.session_state.active_schema_signature = ""
    st.session_state.auto_proposal = None
    reset_editor_state()


def load_demo() -> None:
    demo_csv = EXAMPLES_DIR / "dados_exemplo.csv"
    demo_config = EXAMPLES_DIR / "config_exemplo.yaml"
    config = yaml.safe_load(demo_config.read_text(encoding="utf-8")) or {}
    st.session_state.separator_label = "Ponto e vírgula (;)"
    st.session_state.encoding_label = "utf-8-sig"
    st.session_state.header_label = "Não"
    set_csv_bytes(demo_csv.read_bytes(), demo_csv.name, demo_mode=True, config=config)


def load_yaml(uploaded_config, columns: list[str], source: str) -> dict | None:
    if uploaded_config is None:
        return None
    try:
        config = yaml.safe_load(uploaded_config.getvalue().decode("utf-8")) or {}
    except Exception as exc:
        st.sidebar.error(f"Não foi possível ler o YAML: {exc}")
        return None

    compatibility = config_compatibility(config, columns)
    if compatibility.compatible:
        if st.sidebar.button("Aplicar YAML compatível"):
            return update_schema(normalize_config(config, columns, source=source), columns)
    else:
        st.sidebar.warning(
            "YAML incompatível com o CSV atual. "
            f"Colunas ausentes: {', '.join(compatibility.missing_columns) or 'assinatura de colunas diferente'}."
        )
        if st.sidebar.button("Aplicar para corrigir manualmente"):
            return update_schema(normalize_config(config, columns, source=source), columns)
    return None


def accept_auto_proposal(proposal, columns: list[str], source: str, high_only: bool = False) -> None:
    config = deepcopy(proposal.config)
    if high_only:
        allowed = {
            decision.indicator_id
            for decision in proposal.decisions
            if decision.confidence >= 85
        }
        config["indicators"] = [
            indicator
            for indicator in config.get("indicators") or []
            if str(indicator.get("id")) in allowed
        ]
        config["sections"] = sections_from_indicators(config["indicators"], config.get("sections") or [])
        config["indicators"] = apply_sections_to_indicators(config["indicators"], config["sections"])
    st.session_state.current_config = update_schema(normalize_config(config, columns, source=source), columns)
    st.session_state.auto_proposal = None
    reset_editor_state()


def render_auto_review(dataframe: pd.DataFrame, profile, source: str) -> None:
    proposal = st.session_state.get("auto_proposal")
    if proposal is None:
        return
    st.subheader("Revisar configuração automática")
    st.caption(f"Formato detectado: {proposal.data_shape} · confiança geral: {proposal.confidence}/100 · {proposal.reason}")
    if proposal.warnings:
        st.warning("\n".join(proposal.warnings))

    rows = []
    for decision in proposal.decisions:
        rows.append({
            "rótulo": decision.label,
            "valor ou cálculo": decision.value_or_calculation,
            "coluna": decision.column,
            "operação": OPERATION_LABELS.get(decision.operation, decision.operation),
            "filtro": decision.filter_description,
            "seção": decision.section,
            "ícone": decision.icon,
            "cor": decision.color,
            "ordem": decision.order,
            "confiança": decision.confidence,
            "nível": decision.confidence_level,
            "motivo": decision.reason,
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("O motor não encontrou indicadores seguros para aplicar automaticamente.")

    with st.expander("Perfis de colunas analisadas"):
        st.dataframe(pd.DataFrame([profile.__dict__ for profile in proposal.column_profiles]), width="stretch", hide_index=True)

    actions = st.columns(5)
    if actions[0].button("Aceitar tudo", width="stretch"):
        accept_auto_proposal(proposal, profile.columns, source)
        st.rerun()
    if actions[1].button("Aceitar somente alta confiança", width="stretch"):
        accept_auto_proposal(proposal, profile.columns, source, high_only=True)
        st.rerun()
    if actions[2].button("Editar configuração", width="stretch"):
        accept_auto_proposal(proposal, profile.columns, source)
        st.rerun()
    if actions[3].button("Cancelar", width="stretch"):
        st.session_state.auto_proposal = None
        st.rerun()
    if actions[4].button("Gerar novamente", width="stretch"):
        st.session_state.auto_proposal = infer_config(dataframe, profile, source)
        st.rerun()


def render_custom_rules_manager() -> None:
    with st.sidebar.expander("Regras personalizadas"):
        path = CUSTOM_RULES_PATH
        current = path.read_text(encoding="utf-8") if path.exists() else "version: 1\nrules: {}\n"
        edited = st.text_area("Editar regras YAML", value=current, height=180)
        if st.button("Salvar regras personalizadas", width="stretch"):
            try:
                yaml.safe_load(edited) or {}
            except Exception as exc:
                st.error(f"YAML inválido: {exc}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(edited, encoding="utf-8")
                st.success("Regras personalizadas salvas.")
        st.download_button(
            "Exportar regras",
            edited.encode("utf-8"),
            file_name="custom_semantic_rules.yaml",
            mime="application/x-yaml",
            width="stretch",
        )


def save_selected_indicator_as_rule(indicator: dict) -> None:
    label = str(indicator.get("label") or indicator.get("filter_value") or indicator.get("id") or "regra")
    rule_id = "custom_" + normalize_text(label).replace(" ", "_")[:48]
    rule = {
        "enabled": True,
        "terms": [label],
        "section": indicator.get("section") or "Indicadores",
        "icon": normalize_icon_name(indicator.get("icon") or DEFAULT_ICON),
        "color": normalize_hex_color(indicator.get("color") or DEFAULT_COLOR),
        "priority": 200,
        "confidence_minimum": 60,
        "preferred_label": label,
        "compatible_operations": [indicator.get("operation") or "direct_value"],
    }
    save_custom_rule(rule_id, rule)


def column_options(columns: list[str], indicators: list[dict]) -> list[str]:
    values = set(columns)
    for indicator in indicators:
        for key in ["column", "filter_column", "numerator_column", "denominator_column"]:
            value = str(indicator.get(key, "")).strip()
            if value:
                values.add(value)
    return [""] + sorted(values)


def editable_indicator_table(indicators: list[dict], columns: list[str]) -> list[dict]:
    rows = []
    reverse_operations = {label: key for key, label in OPERATION_LABELS.items()}
    for item in indicators:
        row = {column: deepcopy(item.get(column, "")) for column in INDICATOR_COLUMNS}
        row["operation"] = OPERATION_LABELS.get(str(row.get("operation")), row.get("operation") or "")
        row["icon"] = normalize_icon_name(row.get("icon") or DEFAULT_ICON)
        row["color"] = normalize_hex_color(row.get("color") or DEFAULT_COLOR)
        rows.append(row)

    frame = pd.DataFrame(rows, columns=INDICATOR_COLUMNS)
    options = column_options(columns, rows)
    edited = st.data_editor(
        frame,
        key=f"indicator_editor_{st.session_state.editor_nonce}",
        width="stretch",
        num_rows="dynamic",
        column_order=INDICATOR_COLUMNS,
        column_config={
            "enabled": st.column_config.CheckboxColumn("usar"),
            "id": st.column_config.TextColumn("id"),
            "label": st.column_config.TextColumn("rótulo público"),
            "section": st.column_config.TextColumn("seção"),
            "column": st.column_config.SelectboxColumn("coluna de origem", options=options),
            "operation": st.column_config.SelectboxColumn("operação", options=[""] + list(OPERATION_LABELS.values())),
            "filter_column": st.column_config.SelectboxColumn("coluna do filtro", options=options),
            "filter_operator": st.column_config.SelectboxColumn("operador do filtro", options=FILTER_OPERATORS),
            "filter_value": st.column_config.TextColumn("valor do filtro"),
            "match_value": st.column_config.TextColumn("valor para percentual"),
            "numerator_column": st.column_config.SelectboxColumn("numerador", options=options),
            "denominator_column": st.column_config.SelectboxColumn("denominador", options=options),
            "decimals": st.column_config.NumberColumn("casas decimais", min_value=0, max_value=6, step=1),
            "order": st.column_config.NumberColumn("ordem", min_value=0, step=1),
            "icon": st.column_config.TextColumn("ícone atual", disabled=True),
            "color": st.column_config.TextColumn("cor atual", disabled=True),
        },
        disabled=["icon", "color"],
        hide_index=True,
    )

    existing_ids: list[str] = []
    result = []
    for index, row in enumerate(edited.fillna("").to_dict(orient="records"), start=1):
        item = deepcopy(indicators[index - 1]) if index - 1 < len(indicators) else {}
        item.update({key: row.get(key, "") for key in INDICATOR_COLUMNS})
        if not str(item.get("id", "")).strip():
            item["id"] = new_indicator(columns, existing_ids, order=index)["id"]
        existing_ids.append(str(item["id"]))
        item["enabled"] = bool(item.get("enabled", True))
        item["operation"] = reverse_operations.get(str(item.get("operation")), item.get("operation") or "")
        item["decimals"] = int(item.get("decimals") or 0)
        item["order"] = int(item.get("order") or index)
        item["filter_operator"] = item.get("filter_operator") or "equals"
        item["color"] = normalize_hex_color(item.get("color") or DEFAULT_COLOR)
        item["icon"] = normalize_icon_name(item.get("icon") or DEFAULT_ICON)
        result.append(item)
    return result


def editable_sections(indicators: list[dict], sections: list[dict]) -> tuple[list[dict], list[dict]]:
    section_rows = []
    for section in sections_from_indicators(indicators, sections):
        section_rows.append({
            "original_name": section["name"],
            "name": section["name"],
            "order": int(section.get("order") or 1),
            "show_title": bool(section.get("show_title", True)),
        })

    edited = st.data_editor(
        pd.DataFrame(section_rows, columns=["original_name", "name", "order", "show_title"]),
        key=f"section_editor_{st.session_state.editor_nonce}",
        width="stretch",
        num_rows="dynamic",
        column_config={
            "original_name": st.column_config.TextColumn("nome anterior", disabled=True),
            "name": st.column_config.TextColumn("nome da seção"),
            "order": st.column_config.NumberColumn("ordem da seção", min_value=1, step=1),
            "show_title": st.column_config.CheckboxColumn("mostrar título"),
        },
        hide_index=True,
    )

    rename_map = {}
    normalized_sections = []
    for index, row in enumerate(edited.fillna("").to_dict(orient="records"), start=1):
        name = str(row.get("name", "")).strip()
        original = str(row.get("original_name", "")).strip()
        if not name:
            continue
        if original and original != name:
            rename_map[original] = name
        normalized_sections.append({
            "name": name,
            "order": int(row.get("order") or index),
            "show_title": bool(row.get("show_title", True)),
        })

    renamed = []
    for indicator in indicators:
        item = deepcopy(indicator)
        if item.get("section") in rename_map:
            item["section"] = rename_map[item["section"]]
        renamed.append(item)
    return normalized_sections, apply_sections_to_indicators(renamed, normalized_sections)


def png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def asset_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def inject_styles() -> None:
    home_background = asset_data_uri(ROOT / "assets" / "ui" / "fundo-estudio-infograficos.png")
    st.markdown(
        f"""
        <style>
        :root {{
            --observatorio-navy: #182a5c;
            --observatorio-blue: #1768b5;
            --observatorio-cyan: #67a9be;
            --observatorio-ice: #f5f9fd;
            --observatorio-line: #d7e4f0;
            --observatorio-muted: #52647a;
        }}
        .stApp {{
            background: #f8fbfe;
            color: var(--observatorio-navy);
        }}
        .stApp::before {{
            background: #f4c400;
            box-shadow: 25vw 0 0 #16833a, 50vw 0 0 #dc2d21, 75vw 0 0 #1768b5;
            content: "";
            height: 5px;
            left: 0;
            position: fixed;
            width: 25vw;
            top: 0;
            z-index: 999999;
        }}
        [data-testid="stAppViewContainer"]:has(.home-screen-marker) {{
            background-color: #f8fbfe;
            background-image: url("{home_background}");
            background-position: center top;
            background-repeat: no-repeat;
            background-size: cover;
        }}
        [data-testid="stAppViewContainer"]:has(.home-screen-marker) .main .block-container {{
            max-width: 1180px;
            padding-top: 2.8rem;
        }}
        [data-testid="stAppViewContainer"]:has(.editor-screen-marker) .main .block-container {{
            padding-top: 1.8rem;
        }}
        [data-testid="stSidebar"] {{
            background: #f1f7fc;
            border-right: 1px solid var(--observatorio-line);
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            padding-top: 1.25rem;
        }}
        .home-screen-marker, .editor-screen-marker {{
            display: none;
        }}
        .brand-masthead {{
            align-items: center;
            display: flex;
            gap: 28px;
            margin: 0 0 2rem;
            min-height: 128px;
        }}
        .brand-masthead img {{
            height: 68px;
            object-fit: contain;
            width: 280px;
        }}
        .brand-masthead-copy {{
            border-left: 1px solid #abc7dc;
            padding-left: 28px;
        }}
        .brand-masthead h1 {{
            color: var(--observatorio-navy);
            font-size: 2.45rem;
            line-height: 1.08;
            margin: 0 0 0.45rem;
        }}
        .brand-masthead p {{
            color: var(--observatorio-muted);
            font-size: 1rem;
            margin: 0;
            max-width: 560px;
        }}
        .editor-brandline {{
            align-items: center;
            color: var(--observatorio-navy);
            display: flex;
            font-size: 0.85rem;
            font-weight: 700;
            gap: 9px;
            margin-bottom: 0.25rem;
        }}
        .editor-brandline::before {{
            background: #67a9be;
            border-left: 5px solid #182a5c;
            content: "";
            height: 22px;
            width: 4px;
        }}
        .sidebar-step {{
            align-items: center;
            color: var(--observatorio-navy);
            display: flex;
            font-size: 0.95rem;
            font-weight: 700;
            gap: 10px;
            margin: 1.15rem 0 0.45rem;
        }}
        .sidebar-step b {{
            align-items: center;
            background: #dcecf7;
            border-radius: 999px;
            color: #145b9e;
            display: inline-flex;
            font-size: 0.76rem;
            height: 24px;
            justify-content: center;
            width: 24px;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: rgba(255, 255, 255, 0.94);
            border-color: var(--observatorio-line) !important;
            border-radius: 8px !important;
            box-shadow: 0 5px 18px rgba(24, 42, 92, 0.05);
        }}
        div[data-testid="stExpander"] {{
            background: rgba(255, 255, 255, 0.9);
            border-color: var(--observatorio-line);
            border-radius: 8px;
        }}
        .stButton > button, .stDownloadButton > button {{
            border-radius: 6px;
            min-height: 2.55rem;
        }}
        .stButton > button[kind="primary"] {{
            background: #1768b5;
            border-color: #1768b5;
        }}
        [data-testid="stTextInputRootElement"], [data-testid="stSelectbox"] > div > div {{
            border-radius: 6px;
        }}
        .preview-surface {{
            background: #f4f6f8;
            border: 1px solid #d8e0ea;
            border-radius: 8px;
            max-height: 78vh;
            overflow: auto;
            padding: 16px;
            position: sticky;
            top: 0.75rem;
        }}
        .preview-surface img {{
            display: block;
            height: auto;
            margin: 0 auto;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
        }}
        .color-swatch-row {{
            display: flex;
            gap: 12px;
            margin: 0.4rem 0 1rem;
        }}
        .color-swatch {{
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            height: 40px;
            width: 88px;
        }}
        @media (max-width: 900px) {{
            .brand-masthead {{
                align-items: flex-start;
                flex-direction: column;
                gap: 18px;
                margin-bottom: 1.25rem;
            }}
            .brand-masthead img {{
                height: auto;
                max-width: 270px;
                width: 70%;
            }}
            .brand-masthead-copy {{
                border-left: 0;
                border-top: 1px solid #abc7dc;
                padding-left: 0;
                padding-top: 18px;
            }}
            .brand-masthead h1 {{
                font-size: 2rem;
            }}
            .preview-surface {{
                max-height: none;
                overflow-x: hidden;
                position: static;
            }}
            .preview-surface img {{
                max-width: 100%;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def indicator_option_label(indicator: dict, index: int) -> str:
    order = indicator.get("order") or index + 1
    label = str(indicator.get("label") or indicator.get("id") or f"indicador_{index + 1:03d}").strip()
    section = str(indicator.get("section") or "").strip()
    return f"{order} · {label}" + (f" · {section}" if section else "")


def indicator_by_id(indicators: list[dict], indicator_id: str) -> dict | None:
    for indicator in indicators:
        if str(indicator.get("id")) == str(indicator_id):
            return indicator
    return None


def metric_lookup(metrics) -> dict[str, object]:
    return {str(metric.metric_id): metric for metric in metrics}


def open_appearance_editor(indicator: dict) -> None:
    st.session_state.appearance_dialog_open = True
    st.session_state.appearance_original_icon = normalize_icon_name(indicator.get("icon") or DEFAULT_ICON)
    st.session_state.appearance_original_color = normalize_hex_color(indicator.get("color") or DEFAULT_COLOR)
    st.session_state.appearance_draft_icon = st.session_state.appearance_original_icon
    st.session_state.appearance_draft_color = st.session_state.appearance_original_color
    st.session_state.appearance_icon_query = ""
    st.session_state.appearance_icon_category = "todos"


def set_draft_color(color: str) -> None:
    st.session_state.appearance_draft_color = normalize_hex_color(color)


def close_appearance_editor() -> None:
    st.session_state.appearance_dialog_open = False


def update_config_indicators(indicators: list[dict], columns: list[str], source: str) -> None:
    updated = deepcopy(st.session_state.current_config)
    updated["indicators"] = indicators
    updated["sections"] = sections_from_indicators(indicators, updated.get("sections") or [])
    st.session_state.current_config = update_schema(normalize_config(updated, columns, source=source), columns)
    reset_editor_state()


def preview_card_payload(indicator: dict, metric, icon: str, color: str) -> dict:
    payload = dict(getattr(metric, "__dict__", {}) or {})
    payload["metric_id"] = str(indicator.get("id") or payload.get("metric_id") or "preview")
    payload["label"] = str(payload.get("label") or indicator.get("label") or "Indicador").strip()
    payload["display_value"] = str(payload.get("display_value") or "123")
    payload["icon"] = normalize_icon_name(icon)
    payload["color"] = normalize_hex_color(color)
    return payload


def render_color_swatches(current_color: str, draft_color: str) -> None:
    st.markdown(
        f"""
        <div class="color-swatch-row">
            <div>
                <div class="color-swatch" style="background:{current_color};"></div>
                <small>atual {current_color}</small>
            </div>
            <div>
                <div class="color-swatch" style="background:{draft_color};"></div>
                <small>nova {draft_color}</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_icon_gallery(draft_icon: str, draft_color: str) -> None:
    st.text_input("Buscar ícone", key="appearance_icon_query")
    st.selectbox("Categoria", ICON_CATEGORIES, key="appearance_icon_category")
    icons = icons_for_gallery(st.session_state.appearance_icon_category, st.session_state.appearance_icon_query)
    if not icons:
        st.info("Nenhum ícone encontrado para esta busca.")
        return

    cols = st.columns(3)
    for index, icon in enumerate(icons):
        with cols[index % 3]:
            st.image(png_bytes(icon_preview_image(icon.name, draft_color, size=84)), width=60)
            if icon.name == draft_icon:
                st.caption("Selecionado")
            if st.button(icon.label, key=f"appearance_icon_{icon.name}", help=f"{icon.category} · {icon.name}"):
                st.session_state.appearance_draft_icon = icon.name
                st.rerun()


def render_palette() -> None:
    palette_cols = st.columns(5)
    for index, (color, label) in enumerate(INSTITUTIONAL_PALETTE):
        with palette_cols[index % 5]:
            st.markdown(
                f"<div class='color-swatch' style='background:{color}; width:100%;'></div>",
                unsafe_allow_html=True,
            )
            st.button(color, key=f"palette_{index}", help=label, on_click=set_draft_color, args=(color,), width="stretch")


def render_appearance_body(indicators: list[dict], metrics_by_id: dict[str, object], columns: list[str], source: str) -> None:
    target_id = str(st.session_state.get("appearance_target_id") or "")
    indicator = indicator_by_id(indicators, target_id)
    if indicator is None:
        st.warning("O indicador selecionado não está mais disponível.")
        if st.button("Fechar"):
            close_appearance_editor()
            st.rerun()
        return

    current_icon = normalize_icon_name(indicator.get("icon") or DEFAULT_ICON)
    current_color = normalize_hex_color(indicator.get("color") or DEFAULT_COLOR)
    draft_icon = normalize_icon_name(st.session_state.get("appearance_draft_icon") or current_icon)
    draft_color = normalize_hex_color(st.session_state.get("appearance_draft_color") or current_color)
    selected_label = str(indicator.get("label") or indicator.get("id") or "Indicador")

    st.markdown(f"**{selected_label}**")
    left, right = st.columns([1.0, 1.45])
    with left:
        st.caption("Miniatura")
        metric = metrics_by_id.get(target_id)
        preview = render_card_thumbnail(preview_card_payload(indicator, metric, draft_icon, draft_color), width=680, height=330)
        st.image(png_bytes(preview), width="stretch")
        render_color_swatches(current_color, draft_color)
        if "appearance_draft_color" not in st.session_state:
            st.session_state.appearance_draft_color = draft_color
        st.color_picker("Cor", key="appearance_draft_color")
        st.caption(f"Ícone atual: {icon_label(current_icon)} · novo: {icon_label(draft_icon)}")

    with right:
        render_icon_gallery(draft_icon, draft_color)
        st.divider()
        st.caption("Paleta institucional")
        render_palette()

    st.divider()
    actions = st.columns(4)
    if actions[0].button("Aplicar ao indicador", width="stretch"):
        updated = apply_appearance_to_indicator(indicators, target_id, icon=draft_icon, color=draft_color)
        update_config_indicators(updated, columns, source)
        st.rerun()
    if actions[1].button("Aplicar à seção", width="stretch"):
        updated = apply_appearance_to_section(indicators, str(indicator.get("section") or ""), icon=draft_icon, color=draft_color)
        update_config_indicators(updated, columns, source)
        st.rerun()
    if actions[2].button("Aplicar a todos", width="stretch"):
        updated = apply_appearance_to_all(indicators, icon=draft_icon, color=draft_color)
        update_config_indicators(updated, columns, source)
        st.rerun()
    if actions[3].button("Cancelar", width="stretch"):
        close_appearance_editor()
        st.rerun()


def maybe_open_appearance_dialog(indicators: list[dict], metrics_by_id: dict[str, object], columns: list[str], source: str) -> None:
    if not st.session_state.appearance_dialog_open:
        return
    if hasattr(st, "dialog"):
        @st.dialog("Editar aparência", width="large")
        def _dialog() -> None:
            render_appearance_body(indicators, metrics_by_id, columns, source)

        _dialog()
    else:
        with st.expander("Editar aparência", expanded=True):
            render_appearance_body(indicators, metrics_by_id, columns, source)


def render_appearance_launcher(indicators: list[dict], metrics_by_id: dict[str, object], columns: list[str], source: str) -> None:
    st.subheader("Aparência dos indicadores")
    if not indicators:
        st.info("Adicione pelo menos um indicador para editar ícone e cor.")
        return

    options = [str(item.get("id")) for item in indicators]
    labels = {str(item.get("id")): indicator_option_label(item, index) for index, item in enumerate(indicators)}
    if st.session_state.get("appearance_target_id") not in options:
        st.session_state.appearance_target_id = options[0]
    selected_id = st.selectbox(
        "Indicador para editar aparência",
        options=options,
        format_func=lambda value: labels.get(value, value),
        key="appearance_target_id",
    )
    selected = indicator_by_id(indicators, selected_id)
    if selected:
        current_icon = normalize_icon_name(selected.get("icon") or DEFAULT_ICON)
        current_color = normalize_hex_color(selected.get("color") or DEFAULT_COLOR)
        info_cols = st.columns([1, 1, 1.2])
        info_cols[0].metric("Ícone", icon_label(current_icon))
        info_cols[1].metric("Cor", current_color)
        with info_cols[2]:
            if st.button("Editar aparência", width="stretch"):
                open_appearance_editor(selected)
                st.rerun()
        if st.button("Salvar esta correção como regra"):
            save_selected_indicator_as_rule(selected)
            st.success("Correção salva em config/custom_semantic_rules.yaml.")

    maybe_open_appearance_dialog(indicators, metrics_by_id, columns, source)


def preview_controls() -> None:
    st.subheader("Prévia")
    if st.session_state.preview_minimized:
        if st.button("Restaurar prévia", width="stretch"):
            st.session_state.preview_minimized = False
            st.rerun()
        st.caption("Prévia minimizada.")
        return

    controls = st.columns(4)
    if controls[0].button("Prévia menor", width="stretch"):
        st.session_state.preview_ratio = fallback_preview_ratio(st.session_state.preview_ratio, "smaller")
        st.rerun()
    if controls[1].button("Equilibrado", width="stretch"):
        st.session_state.preview_ratio = fallback_preview_ratio(st.session_state.preview_ratio, "balanced")
        st.rerun()
    if controls[2].button("Prévia maior", width="stretch"):
        st.session_state.preview_ratio = fallback_preview_ratio(st.session_state.preview_ratio, "larger")
        st.rerun()
    if controls[3].button("Minimizar", width="stretch"):
        st.session_state.preview_minimized = True
        st.rerun()

    st.session_state.preview_ratio = st.slider(
        "Largura da prévia",
        min_value=0.28,
        max_value=0.62,
        value=clamp_preview_ratio(st.session_state.preview_ratio),
        step=0.01,
        format="%.2f",
    )
    st.session_state.preview_fit_width = st.toggle("Ajustar à largura", value=bool(st.session_state.preview_fit_width))
    if not st.session_state.preview_fit_width:
        st.session_state.preview_zoom = st.slider("Zoom", min_value=25, max_value=100, value=int(st.session_state.preview_zoom), step=5)


def render_preview_image(path: Path) -> None:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    if st.session_state.preview_fit_width:
        style = "width:100%; max-width:100%;"
    else:
        zoom = max(25, min(100, int(st.session_state.preview_zoom)))
        style = f"width:{zoom}%; max-width:100%; min-width:260px;"
    st.markdown(
        f"""
        <div class="preview-surface">
            <img src="data:image/png;base64,{encoded}" style="{style}" alt="Prévia do infográfico" />
        </div>
        """,
        unsafe_allow_html=True,
    )


def reset_free_editor_state() -> None:
    st.session_state["free_editor_nonce"] = int(st.session_state.get("free_editor_nonce", 0)) + 1


def sync_local_field_widget_values(fields: list[dict]) -> None:
    st.session_state.local_control_field_id = ""


def sync_local_selected_control_values(field: dict) -> None:
    field_id = str(field.get("id") or "")
    if not field_id or st.session_state.local_control_field_id == field_id:
        return
    if field.get("type") == "chart":
        chart = field.get("chart") or {}
        st.session_state.local_chart_title = str(chart.get("title") or "")
        st.session_state.local_chart_color = str(chart.get("bar_color") or "#0057B8")
        st.session_state.local_chart_values = bool(chart.get("show_values", True))
        st.session_state.local_chart_labels = bool(chart.get("show_labels", True))
    else:
        st.session_state.local_field_font_size = int(field.get("font_size") or 58)
        st.session_state.local_field_color = str(field.get("color") or "#0057B8")
        st.session_state.local_field_bold = bool(field.get("bold", True))
        st.session_state.local_field_align = str(field.get("align") or "left")
        st.session_state.local_field_label = bool(field.get("render_label", False))
    st.session_state.local_control_field_id = field_id


def update_local_field_from_widget(field_id: str, property_name: str, widget_key: str, chart_property: bool = False) -> None:
    fields = deepcopy(st.session_state.get("free_fields") or [])
    index = next((position for position, item in enumerate(fields) if str(item.get("id") or "") == field_id), None)
    if index is None or widget_key not in st.session_state:
        return
    field = deepcopy(fields[index])
    value = st.session_state[widget_key]
    if chart_property:
        chart = deepcopy(field.get("chart") or {})
        chart[property_name] = value
        field["chart"] = chart
        if property_name == "title":
            field["name"] = str(value or "") or "Gráfico"
            field["value"] = field["name"]
    else:
        if property_name == "font_size":
            value = max(8, min(220, int(value)))
        elif property_name == "color":
            value = normalize_hex_color(str(value or "#0057B8"))
        elif property_name in {"bold", "render_label"}:
            value = bool(value)
        elif property_name == "align":
            value = str(value or "left") if str(value or "left") in ALIGN_OPTIONS else "left"
        field[property_name] = value
    if field != fields[index]:
        fields[index] = field
        st.session_state.free_fields = fields
        st.session_state.free_dirty = True


def image_size_from_bytes(data: bytes) -> tuple[int, int]:
    image = Image.open(BytesIO(data))
    return image.size


def set_free_base_image(data: bytes, name: str) -> None:
    digest = hashlib.sha256(data).hexdigest()
    token = f"{name}:{digest}"
    if st.session_state.free_base_image_digest == token:
        return
    image_size = image_size_from_bytes(data)
    st.session_state.free_base_image_bytes = data
    st.session_state.free_base_image_name = name
    st.session_state.free_base_image_digest = token
    st.session_state.free_base_image_size = image_size
    st.session_state.free_fields = normalize_fields(st.session_state.free_fields, image_size[0], image_size[1])
    st.session_state.free_dirty = True
    reset_free_editor_state()


def clear_free_mode() -> None:
    st.session_state.free_base_image_bytes = None
    st.session_state.free_base_image_name = ""
    st.session_state.free_base_image_digest = ""
    st.session_state.free_base_image_size = (0, 0)
    st.session_state.free_expected_base_image_name = ""
    st.session_state.free_project_name = ""
    st.session_state.free_fields = []
    st.session_state.free_field_csv_digest = ""
    st.session_state.free_field_csv_name = ""
    st.session_state.free_field_csv_warnings = []
    st.session_state.free_project_id = ""
    st.session_state.free_data_bytes = None
    st.session_state.free_data_name = ""
    st.session_state.free_dirty = False
    st.session_state.free_selected_id = ""
    st.session_state.local_selected_element = ""
    st.session_state.local_control_field_id = ""
    st.session_state.free_update_preview = None
    st.session_state.free_metadata = {}
    st.session_state.local_source_input = ""
    st.session_state.free_export_paths = []
    reset_free_editor_state()


def load_reference_base_as_free_mode() -> None:
    base_path = ROOT / "assets" / "templates" / "institucional_claro_v1" / "base_9_indicadores.png"
    if not base_path.exists():
        st.error("Imagem-base de exemplo não encontrada.")
        return
    set_free_base_image(base_path.read_bytes(), base_path.name)


def set_free_fields_from_csv(data: bytes, name: str) -> None:
    digest = hashlib.sha256(data).hexdigest()
    token = f"{name}:{digest}"
    if st.session_state.free_field_csv_digest == token:
        return
    image_width, image_height = st.session_state.free_base_image_size or (1122, 1402)
    workspace = local_workspace()
    project_id = st.session_state.free_project_id or st.session_state.free_project_name or "rascunho"
    fields, warnings = workspace.create_fields(
        data,
        name,
        project_id,
        (image_width or 1122, image_height or 1402),
        existing=st.session_state.free_fields,
    )
    st.session_state.free_field_csv_digest = token
    st.session_state.free_field_csv_name = name
    st.session_state.free_field_csv_warnings = warnings
    st.session_state.free_data_bytes = data
    st.session_state.free_data_name = name
    if fields:
        st.session_state.free_fields = fields
        sync_local_field_widget_values(fields)
        st.session_state.free_dirty = True
        reset_free_editor_state()


def apply_free_yaml(data: bytes) -> bool:
    try:
        config = yaml.safe_load(data.decode("utf-8")) or {}
    except Exception as exc:
        st.sidebar.error(f"Não foi possível ler o YAML: {exc}")
        return False
    if config.get("mode") != "imagem_base":
        st.sidebar.warning("Este YAML não é uma configuração do modo imagem-base.")
        return False
    base_image = config.get("base_image") or {}
    image_width, image_height = st.session_state.free_base_image_size or (
        int(base_image.get("width") or 1122),
        int(base_image.get("height") or 1402),
    )
    st.session_state.free_project_name = str(config.get("name") or "")
    st.session_state.free_expected_base_image_name = str(base_image.get("file") or "")
    st.session_state.free_fields = normalize_fields(config.get("fields") or [], image_width, image_height)
    reset_free_editor_state()
    return True


def free_field_csv_bytes(fields: list[dict], base_image_name: str) -> bytes:
    return fields_to_dataframe(fields, base_image_name).to_csv(index=False).encode("utf-8-sig")


def free_config_bytes(base_image_name: str, fields: list[dict], image_size: tuple[int, int], project_name: str = "") -> bytes:
    config = build_free_mode_config_with_name(base_image_name, fields, image_size, project_name)
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode("utf-8")


def editable_free_fields_table(fields: list[dict], image_size: tuple[int, int]) -> list[dict]:
    image_width, image_height = image_size
    normalized = normalize_fields(fields, image_width or 1122, image_height or 1402)
    frame = pd.DataFrame(normalized, columns=FIELD_COLUMNS)
    edited = st.data_editor(
        frame,
        key=f"free_field_editor_{st.session_state.free_editor_nonce}",
        width="stretch",
        height=360,
        num_rows="dynamic",
        column_order=[
            "enabled",
            "placed",
            "name",
            "value",
            "x",
            "y",
            "width",
            "height",
            "font_size",
            "color",
            "bold",
            "align",
            "render_label",
            "order",
            "id",
        ],
        column_config={
            "enabled": st.column_config.CheckboxColumn("usar"),
            "placed": st.column_config.CheckboxColumn("na arte"),
            "id": st.column_config.TextColumn("id técnico", disabled=True),
            "name": st.column_config.TextColumn("nome do campo"),
            "value": st.column_config.TextColumn("valor/texto"),
            "x": st.column_config.NumberColumn("coord. X", min_value=0, max_value=max(1, image_width), step=1),
            "y": st.column_config.NumberColumn("coord. Y", min_value=0, max_value=max(1, image_height), step=1),
            "width": st.column_config.NumberColumn("largura", min_value=24, max_value=max(24, image_width), step=1),
            "height": st.column_config.NumberColumn("altura", min_value=18, max_value=max(18, image_height), step=1),
            "font_size": st.column_config.NumberColumn("tam. fonte", min_value=8, max_value=220, step=1),
            "color": st.column_config.TextColumn("cor"),
            "bold": st.column_config.CheckboxColumn("negrito"),
            "align": st.column_config.SelectboxColumn("alinhamento", options=ALIGN_OPTIONS),
            "render_label": st.column_config.CheckboxColumn("mostrar nome"),
            "order": st.column_config.NumberColumn("ordem", min_value=1, step=1),
        },
        hide_index=True,
    )
    rows = edited.fillna("").to_dict(orient="records")
    previous_by_index = normalized
    merged = []
    for index, row in enumerate(rows, start=1):
        base = deepcopy(previous_by_index[index - 1]) if index - 1 < len(previous_by_index) else {}
        base.update(row)
        merged.append(base)
    return normalize_fields(merged, image_width or 1122, image_height or 1402)


def write_free_validation_report(report, output_path: Path, field_count: int, base_image_name: str) -> None:
    lines = [
        "Relatorio de validacao do modo imagem-base",
        f"Imagem-base: {base_image_name}",
        f"Dimensoes: {report.width} x {report.height}px",
        f"Campos renderizados: {field_count}",
        f"PNG: {report.output_png}",
        f"PDF: {report.output_pdf or 'nao gerado'}",
    ]
    if report.errors:
        lines.append("Problemas encontrados:")
        lines.extend(f"- {error}" for error in report.errors)
    else:
        lines.append("Validacao visual automatica: sem texto fora dos limites e sem sobreposicao entre campos.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def saved_free_projects() -> list[dict[str, object]]:
    projects = []
    if not OUTPUT_DIR.exists():
        return projects
    for path in sorted(OUTPUT_DIR.glob("*.yaml"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if config.get("mode") != "imagem_base":
            continue
        base_image = config.get("base_image") or {}
        name = str(config.get("name") or "").strip() or path.stem.replace("config_imagem_base_", "").replace("_", " ").strip() or path.stem
        projects.append({
            "path": path,
            "name": name,
            "base_file": str(base_image.get("file") or ""),
            "updated": date.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y"),
            "field_count": len(config.get("fields") or []),
        })
    return projects


def resolve_free_base_path(config_path: Path, base_file: str) -> Path | None:
    candidates = [
        config_path.parent / base_file,
        OUTPUT_DIR / base_file,
        ROOT / base_file,
        ROOT / "assets" / "templates" / "institucional_claro_v1" / base_file,
        ROOT / "assets" / base_file,
    ]
    for candidate in candidates:
        if str(base_file).strip() and candidate.exists() and candidate.is_file():
            return candidate
    return None


def load_free_project(config_path: Path) -> str | None:
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return f"Não foi possível abrir a configuração: {exc}"
    if config.get("mode") != "imagem_base":
        return "A configuração selecionada não pertence ao modo imagem-base."
    base_image = config.get("base_image") or {}
    base_file = str(base_image.get("file") or "")
    base_path = resolve_free_base_path(config_path, base_file)
    if base_path is None:
        st.session_state.free_base_image_bytes = None
        st.session_state.free_base_image_name = ""
        st.session_state.free_base_image_digest = ""
        st.session_state.free_base_image_size = (
            int(base_image.get("width") or 0),
            int(base_image.get("height") or 0),
        )
        st.session_state.free_expected_base_image_name = base_file
    else:
        set_free_base_image(base_path.read_bytes(), base_path.name)
    image_size = st.session_state.free_base_image_size or (
        int(base_image.get("width") or 1122),
        int(base_image.get("height") or 1402),
    )
    st.session_state.free_project_name = str(config.get("name") or "")
    st.session_state.free_fields = normalize_fields(config.get("fields") or [], int(image_size[0] or 1122), int(image_size[1] or 1402))
    st.session_state.free_screen = "editor"
    reset_free_editor_state()
    return None


def save_free_project_files(base_bytes: bytes, base_name: str, project_name: str, fields: list[dict], image_size: tuple[int, int]) -> dict[str, Path]:
    names = free_mode_export_names(project_name or base_name, date.today())
    suffix = Path(base_name).suffix.lower() or ".png"
    slug = Path(names["png"]).stem.replace("infografico_", "")
    base_copy = OUTPUT_DIR / f"base_{slug}{suffix}"
    fields_path = OUTPUT_DIR / names["fields"]
    config_path = OUTPUT_DIR / names["config"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_copy.write_bytes(base_bytes)
    write_fields_csv(fields, fields_path, base_copy.name)
    config_path.write_bytes(free_config_bytes(base_copy.name, fields, image_size, project_name))
    return {"base": base_copy, "fields": fields_path, "config": config_path}


def generate_free_project_from_config(config_path: Path) -> tuple[list[Path], list[str]]:
    messages: list[str] = []
    generated: list[Path] = []
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return generated, [f"{config_path.name}: YAML inválido ({exc})"]
    if config.get("mode") != "imagem_base":
        return generated, [f"{config_path.name}: modo incompatível"]
    base_image = config.get("base_image") or {}
    base_file = str(base_image.get("file") or "")
    base_path = resolve_free_base_path(config_path, base_file)
    if base_path is None:
        return generated, [f"{config_path.name}: imagem-base ausente ({base_file})"]
    fields = normalize_fields(config.get("fields") or [], int(base_image.get("width") or 1122), int(base_image.get("height") or 1402))
    names = free_mode_export_names(str(config.get("name") or base_path.name), date.today())
    output_png = OUTPUT_DIR / names["png"]
    output_pdf = OUTPUT_DIR / names["pdf"]
    validation_path = OUTPUT_DIR / names["validation"]
    report = render_free_infographic(base_path, fields, output_png, output_pdf)
    rendered_count = len([field for field in fields if field.get("enabled", True) and field.get("placed", True)])
    write_free_validation_report(report, validation_path, rendered_count, base_path.name)
    generated.extend([output_png, output_pdf, validation_path])
    if report.errors:
        messages.extend(report.errors)
    return generated, messages


def update_free_project_config(config_path: Path) -> str | None:
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return f"{config_path.name}: YAML inválido ({exc})"
    if config.get("mode") != "imagem_base":
        return f"{config_path.name}: modo incompatível"
    base_image = config.get("base_image") or {}
    base_file = str(base_image.get("file") or "")
    width = int(base_image.get("width") or 1122)
    height = int(base_image.get("height") or 1402)
    base_path = resolve_free_base_path(config_path, base_file)
    if base_path is not None:
        try:
            width, height = Image.open(base_path).size
        except Exception:
            pass
    updated = build_free_mode_config_with_name(
        base_file,
        normalize_fields(config.get("fields") or [], width, height),
        (width, height),
        str(config.get("name") or ""),
    )
    config_path.write_text(yaml.safe_dump(updated, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return None


def positions_changed(before: list[dict], after: list[dict]) -> bool:
    before_by_id = {str(field.get("id")): field for field in before}
    for field in after:
        old = before_by_id.get(str(field.get("id")))
        if old is None:
            return True
        if bool(old.get("placed", True)) != bool(field.get("placed", True)):
            return True
        for key in ["x", "y", "width", "height", "font_size"]:
            if int(old.get(key) or 0) != int(field.get(key) or 0):
                return True
    return False


def preview_refresh_needed(before: list[dict], after: list[dict]) -> bool:
    before_by_id = {str(field.get("id")): field for field in before}
    for field in after:
        old = before_by_id.get(str(field.get("id")))
        if old is None:
            return True
        for key in ["width", "height", "font_size"]:
            if int(old.get(key) or 0) != int(field.get(key) or 0):
                return True
    return False


def active_workspace_dir() -> Path:
    if not is_ephemeral_environment(WORKSPACE_DIR):
        return WORKSPACE_DIR
    session_id = str(st.session_state.get("ephemeral_workspace_id") or uuid.uuid4().hex)
    st.session_state["ephemeral_workspace_id"] = session_id
    return ROOT / "tmp" / "sessions" / session_id


def local_workspace() -> LocalInfographicWorkspace:
    return LocalInfographicWorkspace(active_workspace_dir()).bootstrap()


def load_local_infographic(infographic_id: str) -> str | None:
    workspace = local_workspace()
    try:
        document = workspace.load(infographic_id)
        base_path = workspace.resolve(str((document.get("base_image") or {}).get("path") or ""))
        data_path_value = str((document.get("data_source") or {}).get("path") or "")
        set_free_base_image(base_path.read_bytes(), base_path.name)
        if data_path_value:
            data_path = workspace.resolve(data_path_value)
            st.session_state.free_data_bytes = data_path.read_bytes() if data_path.exists() else None
            st.session_state.free_data_name = str((document.get("data_source") or {}).get("filename") or data_path.name)
        else:
            st.session_state.free_data_bytes = None
            st.session_state.free_data_name = ""
        canvas = document.get("canvas") or {}
        st.session_state.free_base_image_size = (int(canvas.get("width") or 1122), int(canvas.get("height") or 1402))
        st.session_state.free_project_id = document["id"]
        st.session_state.free_project_name = document["name"]
        st.session_state.free_fields = normalize_fields(document.get("elements") or [], *st.session_state.free_base_image_size)
        sync_local_field_widget_values(st.session_state.free_fields)
        st.session_state.free_metadata = deepcopy(document.get("metadata") or {})
        st.session_state.local_source_input = str(st.session_state.free_metadata.get("source") or "")
        st.session_state.free_field_csv_name = st.session_state.free_data_name
        st.session_state.free_field_csv_digest = str((document.get("data_source") or {}).get("checksum") or "")
        st.session_state.free_dirty = False
        st.session_state.free_update_preview = None
        st.session_state.local_selected_element = st.session_state.free_selected_id
        st.session_state.free_screen = "editor"
        reset_free_editor_state()
        return None
    except Exception as exc:
        return str(exc)


def save_local_infographic() -> dict | None:
    workspace = local_workspace()
    base_bytes = st.session_state.free_base_image_bytes
    if base_bytes is None:
        st.error("Carregue uma imagem-base antes de salvar.")
        return None
    try:
        document = workspace.save(
            name=st.session_state.free_project_name,
            infographic_id=st.session_state.free_project_id,
            elements=st.session_state.free_fields,
            canvas=st.session_state.free_base_image_size,
            base_bytes=base_bytes,
            base_filename=st.session_state.free_base_image_name,
            data_bytes=st.session_state.free_data_bytes,
            data_filename=st.session_state.free_data_name,
            metadata=st.session_state.free_metadata,
        )
    except LocalWorkspaceError as exc:
        st.error(str(exc))
        return None
    st.session_state.free_project_id = document["id"]
    st.session_state.free_dirty = False
    st.success(f"Infográfico salvo em {document['id']}.json.")
    return document


def request_local_action(action: str) -> None:
    if st.session_state.free_dirty:
        st.session_state.free_pending_action = action
    elif action == "home":
        st.session_state.free_screen = "home"
        st.rerun()
    elif action == "new":
        clear_free_mode()
        st.session_state.free_screen = "editor"
        st.rerun()


def render_pending_local_action() -> None:
    action = str(st.session_state.get("free_pending_action") or "")
    if not action:
        return
    st.warning("Existem alterações não salvas. Deseja descartá-las?")
    discard, cancel, _space = st.columns([1, 1, 4])
    if discard.button("Descartar", type="primary"):
        st.session_state.free_pending_action = ""
        st.session_state.free_dirty = False
        if action == "home":
            st.session_state.free_screen = "home"
        else:
            clear_free_mode()
            st.session_state.free_screen = "editor"
        st.rerun()
    if cancel.button("Continuar editando"):
        st.session_state.free_pending_action = ""
        st.rerun()


def render_update_preview(preview: UpdatePreview, csv_bytes: bytes) -> None:
    summary = preview.summary()
    st.subheader("Prévia da atualização")
    cols = st.columns(4)
    cols[0].metric("Alterados", summary["alterados"])
    cols[1].metric("Inalterados", summary["inalterados"])
    cols[2].metric("Ausentes", summary["ausentes"])
    cols[3].metric("Incompatíveis", summary["incompativeis"])
    if preview.changed:
        st.dataframe(pd.DataFrame(preview.changed), hide_index=True, width="stretch")
    for issue in preview.missing:
        st.warning(f"{issue['field_id'] or issue['element_id']}: {issue['message']}. O valor anterior será preservado e a exportação ficará bloqueada.")
    for issue in preview.incompatible:
        st.error(f"{issue['field_id'] or issue['element_id']}: {issue['message']}")
    confirm, cancel, _space = st.columns([1, 1, 4])
    if confirm.button("Confirmar atualização", type="primary", disabled=not preview.can_apply):
        try:
            document = local_workspace().apply_update(preview, csv_bytes)
            st.session_state.free_fields = normalize_fields(document["elements"], *st.session_state.free_base_image_size)
            st.session_state.free_data_bytes = csv_bytes
            st.session_state.free_data_name = preview.filename
            st.session_state.free_field_csv_digest = preview.checksum
            st.session_state.free_update_preview = None
            st.session_state.free_dirty = False
            reset_free_editor_state()
            st.success("Dados atualizados sem alterar o layout.")
            st.rerun()
        except LocalWorkspaceError as exc:
            st.error(str(exc))
    if cancel.button("Cancelar atualização"):
        st.session_state.free_update_preview = None
        st.rerun()


def request_local_delete(project_id: str) -> None:
    st.session_state.local_delete_project_id = str(project_id)


def cancel_local_delete() -> None:
    st.session_state.local_delete_project_id = ""


def render_local_home() -> None:
    workspace = local_workspace()
    brand = asset_data_uri(ROOT / "assets" / "logo_observatorio.png")
    st.markdown('<div class="home-screen-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <header class="brand-masthead">
            <img src="{brand}" alt="Observatório">
            <div class="brand-masthead-copy">
                <h1>Estúdio de Infográficos</h1>
                <p>Crie e mantenha peças institucionais a partir de imagens-base e dados em CSV.</p>
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )

    title_col, action_col = st.columns([4.5, 1.5], vertical_alignment="center")
    with title_col:
        st.subheader("Seus infográficos")
        st.caption("Abra um trabalho existente ou comece uma nova composição.")
    with action_col:
        if st.button("Novo infográfico", icon=":material/add:", type="primary", width="stretch", help="Criar um novo infográfico"):
            clear_free_mode()
            st.session_state.free_screen = "editor"
            st.rerun()

    if is_ephemeral_environment(WORKSPACE_DIR):
        st.warning("Esta sessão possui uma área de trabalho temporária e privada. Baixe o pacote do projeto após salvar; os arquivos podem desaparecer quando o aplicativo reiniciar ou a sessão terminar.")
    else:
        st.caption("Os trabalhos são salvos na área de trabalho local deste computador.")

    projects, issues = workspace.discover()
    if issues:
        with st.expander(f"{len(issues)} arquivo(s) precisam de correção"):
            for issue in issues:
                st.error(f"{issue['file']}: {issue['error']}")

    if not projects:
        st.info("Nenhum infográfico salvo ainda. Use Novo infográfico para começar.")
    for project in projects:
        with st.container(border=True):
            thumb_col, info_col, action_col = st.columns([0.8, 3.5, 1.4], vertical_alignment="center")
            thumbnail = workspace.thumbnails_dir / f"{project['id']}.png"
            with thumb_col:
                if thumbnail.exists():
                    st.image(str(thumbnail), width="stretch")
            with info_col:
                st.markdown(f"**{project['name']}**")
                updated = str(project["updated_at"]).replace("T", " ")[:16]
                st.caption(f"Alterado em {updated} · {project['data_file']} · {project['element_count']} elementos")
                if project["status"] == "Atualizado":
                    st.success(project["status"], icon=":material/check_circle:")
                else:
                    st.warning(project["status"], icon=":material/warning:")
            with action_col:
                if st.button("Abrir", key=f"local_open_{project['id']}", icon=":material/edit:", width="stretch"):
                    error = load_local_infographic(project["id"])
                    if error:
                        st.error(error)
                    else:
                        st.rerun()
                if st.button("Exportar", key=f"local_export_{project['id']}", icon=":material/download:", width="stretch"):
                    try:
                        png, pdf, errors = workspace.export(project["id"])
                        st.session_state.free_export_paths = [png, pdf]
                        if errors:
                            st.warning("; ".join(errors))
                        else:
                            st.success("PNG e PDF atualizados.")
                    except LocalWorkspaceError as exc:
                        st.error(str(exc))
                st.button(
                    "Excluir",
                    key=f"local_delete_{project['id']}",
                    icon=":material/delete:",
                    width="stretch",
                    on_click=request_local_delete,
                    args=(str(project["id"]),),
                )
                if st.session_state.local_delete_project_id == str(project["id"]):
                    st.error(f"Excluir permanentemente “{project['name']}”?", icon=":material/warning:")
                    confirm_col, cancel_col = st.columns(2)
                    if confirm_col.button("Confirmar", key=f"local_delete_confirm_{project['id']}", type="primary", width="stretch"):
                        try:
                            workspace.delete(str(project["id"]))
                            st.session_state.local_delete_project_id = ""
                            st.success("Infográfico excluído.")
                            st.rerun()
                        except LocalWorkspaceError as exc:
                            st.error(str(exc))
                    cancel_col.button(
                        "Cancelar",
                        key=f"local_delete_cancel_{project['id']}",
                        width="stretch",
                        on_click=cancel_local_delete,
                    )
                if is_ephemeral_environment(WORKSPACE_DIR):
                    package = workspace.package(project["id"])
                    st.download_button("Pacote", package.read_bytes(), file_name=package.name, mime="application/zip", key=f"local_package_{project['id']}", width="stretch")

    with st.expander("Atualizar vários infográficos"):
        st.caption("Selecione uma nova versão do CSV. Você poderá conferir o que mudou antes de aplicar.")
        batch_upload = st.file_uploader("Nova versão dos dados (CSV)", type=["csv"], key="local_batch_upload")
        if batch_upload is not None and st.button("Conferir atualizações", icon=":material/refresh:"):
            previews = []
            for project in projects:
                try:
                    preview = workspace.update_preview(project["id"], batch_upload.getvalue(), batch_upload.name)
                    if preview.file_changed and (preview.is_compatible or preview.missing or preview.incompatible):
                        previews.append(preview)
                except Exception as exc:
                    st.warning(f"{project['name']}: {exc}")
            st.session_state.local_batch_preview = previews
            st.session_state.local_batch_bytes = batch_upload.getvalue()
            st.session_state.local_batch_name = batch_upload.name

        previews = st.session_state.get("local_batch_preview") or []
        if previews:
            names = {str(project["id"]): str(project["name"]) for project in projects}
            rows = [
                {
                    "infográfico": names.get(item.infographic_id, item.infographic_id),
                    "situação": item.status_label,
                    **item.summary(),
                }
                for item in previews
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            if st.button("Aplicar nos infográficos compatíveis", type="primary"):
                applied = 0
                blocked = 0
                for preview in previews:
                    if preview.can_apply:
                        workspace.apply_update(preview, st.session_state.local_batch_bytes)
                        applied += 1
                    else:
                        blocked += 1
                st.session_state.local_batch_preview = []
                st.success(f"Atualização concluída: {applied} alterado(s), {blocked} bloqueado(s).")
                st.rerun()

    for path in st.session_state.get("free_export_paths") or []:
        path = Path(path)
        if path.exists():
            mime = "image/png" if path.suffix == ".png" else "application/pdf"
            st.download_button(f"Baixar {path.name}", path.read_bytes(), file_name=path.name, mime=mime)

def _selected_local_field() -> tuple[int, dict] | tuple[None, None]:
    fields = st.session_state.free_fields
    if not fields:
        return None, None
    ids = [str(item.get("id")) for item in fields]
    selected = st.session_state.free_selected_id if st.session_state.free_selected_id in ids else ids[0]
    st.session_state.free_selected_id = selected
    index = ids.index(selected)
    return index, fields[index]


def render_local_sidebar() -> None:
    with st.sidebar:
        st.header("Montagem")
        st.markdown('<div class="sidebar-step"><b>1</b><span>Imagem-base</span></div>', unsafe_allow_html=True)
        uploaded_base = st.file_uploader("Arquivo PNG ou JPG", type=["png", "jpg", "jpeg"], key="local_base_upload")
        if uploaded_base is not None:
            token = f"{uploaded_base.name}:{sha256_bytes(uploaded_base.getvalue())}"
            if token != st.session_state.free_base_image_digest:
                try:
                    set_free_base_image(uploaded_base.getvalue(), uploaded_base.name)
                except Exception as exc:
                    st.error(f"Não foi possível abrir a imagem-base: {exc}")

        st.markdown('<div class="sidebar-step"><b>2</b><span>Dados</span></div>', unsafe_allow_html=True)
        data_upload_label = "Nova versão do CSV" if st.session_state.free_project_id else "Arquivo CSV"
        uploaded_data = st.file_uploader(
            data_upload_label,
            type=["csv"],
            key="local_data_upload",
            help="Em um trabalho salvo, selecione aqui o CSV novo e depois clique em Atualizar dados na barra superior.",
        )
        if st.session_state.free_project_id and st.session_state.free_data_name:
            st.caption(f"Em uso: {st.session_state.free_data_name}")
        if uploaded_data is not None and not st.session_state.free_project_id:
            if st.button("Ler campos do CSV", icon=":material/table_view:", width="stretch"):
                try:
                    set_free_fields_from_csv(uploaded_data.getvalue(), uploaded_data.name)
                    st.success("Campos prontos para arrastar até a imagem.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível ler os dados-base: {exc}")

        def update_source() -> None:
            st.session_state.free_metadata = {
                **(st.session_state.free_metadata or {}),
                "source": str(st.session_state.local_source_input or ""),
            }
            st.session_state.free_dirty = True

        st.markdown('<div class="sidebar-step"><b>3</b><span>Fonte</span></div>', unsafe_allow_html=True)
        st.text_input(
            "Fonte dos dados",
            key="local_source_input",
            on_change=update_source,
            help="Origem oficial registrada no JSON e na auditoria dos campos. Não use aqui o nome do arquivo CSV.",
        )
        st.caption("Origem oficial registrada no projeto e na auditoria.")

        if st.session_state.free_fields:
            st.divider()
            st.markdown('<div class="sidebar-step"><b>4</b><span>Elementos</span></div>', unsafe_allow_html=True)
            search = st.text_input("Buscar por nome", placeholder="Ex.: pesquisadores", key="local_field_search")
            categories = sorted({str(item.get("category") or "Outros") for item in st.session_state.free_fields})
            category = st.selectbox("Categoria", ["Todas", *categories], key="local_field_category")
            visible = [item for item in st.session_state.free_fields if (category == "Todas" or str(item.get("category") or "Outros") == category) and (not search or search.casefold() in f"{item.get('name', '')} {item.get('id', '')}".casefold())]
            st.caption(f"{len(visible)} de {len(st.session_state.free_fields)} campos na tabela")

            metric_fields = [item for item in st.session_state.free_fields if item.get("type") != "chart" and (item.get("binding") or {}).get("indicator_id")]
            if len(metric_fields) >= 2 and st.session_state.free_data_bytes:
                st.subheader("Gráfico")
                labels = {str(item["id"]): str(item.get("name") or item["id"]) for item in metric_fields}
                selected = st.multiselect("Campos", list(labels), format_func=lambda value: labels[value], key="local_chart_fields")
                kind = st.segmented_control("Tipo", ["Barras", "Colunas"], default="Barras", key="local_chart_kind")
                title = st.text_input("Título do gráfico", key="local_chart_title")
                if st.button("Criar gráfico", icon=":material/bar_chart:", width="stretch", disabled=len(selected) < 2):
                    dataframe, _profile = load_csv(BytesIO(st.session_state.free_data_bytes), separator=None, encoding=None, has_header=None)
                    indicators = [str((next(item for item in metric_fields if str(item["id"]) == field_id).get("binding") or {}).get("indicator_id")) for field_id in selected]
                    chart = make_chart_element(
                        st.session_state.free_project_id or st.session_state.free_project_name or "rascunho",
                        sha256_bytes(st.session_state.free_data_bytes),
                        dataframe,
                        local_workspace().catalog(),
                        indicators,
                        chart_type="bar_horizontal" if kind == "Barras" else "bar_vertical",
                        title=title,
                        existing_ids=[str(item.get("id")) for item in st.session_state.free_fields],
                        order=len(st.session_state.free_fields) + 1,
                        image_width=st.session_state.free_base_image_size[0],
                        image_height=st.session_state.free_base_image_size[1],
                    )
                    if str((chart.get("binding") or {}).get("status") or "ok") != "ok":
                        st.error(f"Não foi possível criar o gráfico: {(chart.get('binding') or {}).get('error') or 'série inválida'}")
                        return
                    chart["category"] = "Gráficos"
                    st.session_state.free_fields.append(chart)
                    st.session_state.free_fields = normalize_fields(st.session_state.free_fields, *st.session_state.free_base_image_size)
                    st.session_state.free_dirty = True
                    reset_free_editor_state()
                    st.rerun()

            st.divider()
            st.subheader("Ajustar elemento")
            ids = [str(item.get("id")) for item in st.session_state.free_fields]
            if st.session_state.local_selected_element not in ids:
                st.session_state.local_selected_element = st.session_state.free_selected_id if st.session_state.free_selected_id in ids else ids[0]

            def select_local_element() -> None:
                st.session_state.free_selected_id = str(st.session_state.local_selected_element or "")
                st.session_state.local_control_field_id = ""

            selected_id = st.selectbox(
                "Elemento",
                ids,
                key="local_selected_element",
                format_func=lambda value: next(str(item.get("name") or value) for item in st.session_state.free_fields if str(item.get("id")) == value),
                on_change=select_local_element,
            )
            st.session_state.free_selected_id = selected_id
            index = ids.index(selected_id)
            field = deepcopy(st.session_state.free_fields[index])
            sync_local_selected_control_values(field)
            if field.get("type") == "chart":
                st.text_input("Título", key="local_chart_title", on_change=update_local_field_from_widget, args=(selected_id, "title", "local_chart_title", True))
                st.color_picker("Cor", key="local_chart_color", on_change=update_local_field_from_widget, args=(selected_id, "bar_color", "local_chart_color", True))
                st.checkbox("Mostrar valores", key="local_chart_values", on_change=update_local_field_from_widget, args=(selected_id, "show_values", "local_chart_values", True))
                st.checkbox("Mostrar rótulos", key="local_chart_labels", on_change=update_local_field_from_widget, args=(selected_id, "show_labels", "local_chart_labels", True))
            else:
                st.slider("Tamanho do texto", 8, 220, key="local_field_font_size", on_change=update_local_field_from_widget, args=(selected_id, "font_size", "local_field_font_size"))
                st.color_picker("Cor", key="local_field_color", on_change=update_local_field_from_widget, args=(selected_id, "color", "local_field_color"))
                st.checkbox("Negrito", key="local_field_bold", on_change=update_local_field_from_widget, args=(selected_id, "bold", "local_field_bold"))
                st.segmented_control("Alinhamento", ALIGN_OPTIONS, key="local_field_align", on_change=update_local_field_from_widget, args=(selected_id, "align", "local_field_align"))
                st.checkbox("Mostrar rótulo", key="local_field_label", on_change=update_local_field_from_widget, args=(selected_id, "render_label", "local_field_label"))
            if st.button("Remover da imagem", icon=":material/delete:", help="Mantém o campo disponível para ser arrastado novamente", width="stretch"):
                st.session_state.free_fields[index]["placed"] = False
                st.session_state.free_dirty = True
                reset_free_editor_state()
                st.rerun()


def render_local_editor() -> None:
    workspace = local_workspace()
    st.markdown('<div class="editor-screen-marker"></div>', unsafe_allow_html=True)
    st.markdown('<div class="editor-brandline"><span>Estúdio de Infográficos</span></div>', unsafe_allow_html=True)
    name = st.text_input("Nome do infográfico", value=st.session_state.free_project_name, placeholder="Ex.: A ciência baiana em números")
    if name.strip() != st.session_state.free_project_name:
        st.session_state.free_project_name = name.strip()
        st.session_state.free_dirty = True

    home_col, new_col, spacer, save_col, update_col, export_col = st.columns([1.15, 1.05, 1.65, 1.2, 1.55, 1.25])
    if home_col.button("Início", icon=":material/home:", help="Voltar à lista de infográficos", width="stretch"):
        request_local_action("home")
    if new_col.button("Novo", icon=":material/add:", help="Iniciar um novo trabalho", width="stretch"):
        request_local_action("new")
    if save_col.button("Salvar", icon=":material/save:", type="primary", help="Salvar este infográfico em JSON", width="stretch"):
        save_local_infographic()
    uploaded_data = st.session_state.get("local_data_upload")
    can_update = bool(st.session_state.free_project_id)
    update_help = "Comparar o CSV selecionado com os campos vinculados" if can_update else "Salve o infográfico antes da primeira atualização"
    if update_col.button("Atualizar dados", icon=":material/refresh:", help=update_help, width="stretch", disabled=not can_update):
        if not st.session_state.free_project_id:
            st.info("Salve o infográfico antes da primeira atualização.")
        elif uploaded_data is None:
            st.info("Selecione o novo arquivo na etapa 2, Dados.")
        else:
            try:
                st.session_state.free_update_preview = workspace.update_preview(st.session_state.free_project_id, uploaded_data.getvalue(), uploaded_data.name)
            except Exception as exc:
                st.error(f"Não foi possível comparar os dados: {exc}")
    can_export = bool(st.session_state.free_project_id) and not st.session_state.free_dirty
    export_help = "Gerar PNG e PDF" if can_export else "Salve as alterações antes de exportar"
    if export_col.button("Exportar", icon=":material/download:", help=export_help, width="stretch", disabled=not can_export):
        if not st.session_state.free_project_id or st.session_state.free_dirty:
            st.warning("Salve as alterações antes de exportar.")
        else:
            try:
                png, pdf, errors = workspace.export(st.session_state.free_project_id)
                st.session_state.free_export_paths = [png, pdf]
                if errors:
                    st.warning("; ".join(errors))
                else:
                    st.success("PNG e PDF gerados.")
            except LocalWorkspaceError as exc:
                st.error(str(exc))

    render_pending_local_action()
    sidebar_rendered = False
    if st.session_state.free_base_image_bytes is None:
        render_local_sidebar()
        sidebar_rendered = True
    if st.session_state.free_base_image_bytes is None:
        st.info("Comece pela etapa 1 na lateral: selecione a imagem-base do infográfico.")
        return

    image_size = st.session_state.free_base_image_size
    try:
        field_previews = render_free_field_preview_map(st.session_state.free_fields, *image_size)
    except Exception:
        field_previews = {}
    result = drag_canvas(
        st.session_state.free_base_image_bytes,
        st.session_state.free_fields,
        image_size,
        key=f"local_canvas_{st.session_state.free_editor_nonce}",
        field_preview_bytes=field_previews,
    )
    if result:
        selected_id = str(result.get("selected_id") or "")
        if selected_id:
            if selected_id != st.session_state.free_selected_id:
                st.session_state.local_control_field_id = ""
            st.session_state.free_selected_id = selected_id
            st.session_state.local_selected_element = selected_id
        if result.get("changed"):
            before = normalize_fields(st.session_state.free_fields, *image_size)
            changed_fields = changed_dragged_fields(result)
            merged = merge_dragged_fields(before, changed_fields, *image_size)
            if positions_changed(before, merged):
                st.session_state.free_fields = merged
                st.session_state.free_dirty = True
                st.session_state.local_control_field_id = ""

    if not sidebar_rendered:
        render_local_sidebar()

    for warning in st.session_state.get("free_field_csv_warnings") or []:
        st.warning(warning)
    preview = st.session_state.get("free_update_preview")
    if isinstance(preview, UpdatePreview) and uploaded_data is not None:
        render_update_preview(preview, uploaded_data.getvalue())

    if not str((st.session_state.free_metadata or {}).get("source") or "").strip():
        st.info("Informe a fonte dos dados para manter a origem registrada no projeto. O nome do CSV continuará apenas na auditoria técnica.")
    for path in st.session_state.get("free_export_paths") or []:
        path = Path(path)
        if path.exists():
            mime = "image/png" if path.suffix == ".png" else "application/pdf"
            st.download_button(f"Baixar {path.name}", path.read_bytes(), file_name=path.name, mime=mime)
    if st.session_state.free_project_id and is_ephemeral_environment(WORKSPACE_DIR):
        package = workspace.package(st.session_state.free_project_id)
        st.download_button("Baixar pacote do projeto", package.read_bytes(), file_name=package.name, mime="application/zip", icon=":material/archive:")


def render_free_mode_app() -> None:
    if st.session_state.free_screen == "editor":
        render_local_editor()
    else:
        render_local_home()


def selected_template_capacity(template_config: dict, fallback: int = 9) -> int:
    try:
        template = get_template_registry().get(template_config.get("id"))
        return int(template.metadata.capacity_per_page or fallback)
    except Exception:
        return fallback


def render_template_selector(template_config: dict) -> dict:
    registry = get_template_registry()
    templates = registry.public_templates()
    selected = normalize_template_config(template_config)

    st.subheader("Selecionar design")
    count_label = "1 design disponível" if len(templates) == 1 else f"{len(templates)} designs disponíveis"
    st.caption(count_label)

    if not templates:
        st.warning("Nenhum design público pôde ser carregado. O renderer de compatibilidade será utilizado.")
        return selected

    for item in templates:
        metadata = item.metadata
        is_selected = selected.get("id") == metadata.id
        with st.container(border=True):
            image_col, text_col = st.columns([0.9, 1.4], vertical_alignment="center")
            with image_col:
                if metadata.thumbnail.exists():
                    st.image(str(metadata.thumbnail), width="stretch")
                    st.caption("Referência visual — dados fictícios")
            with text_col:
                st.markdown(f"**{metadata.name}**")
                st.write(metadata.description)
                st.caption(f"Versão {metadata.version} · capacidade {metadata.capacity_per_page} indicadores por página · {metadata.status}")
                if is_selected:
                    st.success(f"Design selecionado: {metadata.name}")
                elif st.button("Selecionar design", key=f"select_template_{metadata.id}", width="stretch"):
                    selected = {"id": metadata.id, "version": metadata.version}
                    st.session_state.current_config["template"] = selected
                    st.rerun()
    return selected


def _render_template_failure(exc: Exception) -> None:
    st.warning(
        "Não foi possível aplicar o design selecionado. "
        f"O renderer de compatibilidade será utilizado. Detalhe técnico: {exc}"
    )


def render_selected_infographic(
    metrics,
    metadata: dict,
    assets: dict,
    config: dict,
    output_png: Path,
    output_pdf: Path | None = None,
):
    template_config = normalize_template_config(config.get("template"))
    try:
        template = get_template_registry().get(template_config.get("id"))
        context = TemplateContext(metrics, metadata, assets, config, demo_mode=bool(st.session_state.demo_mode))
        if not template.supports(context):
            raise ValueError(f"template incompatível com {len(metrics)} indicador(es)")
        return template.render(context, output_png, output_pdf)
    except Exception as exc:
        _render_template_failure(exc)
        report = render_compat_infographic(metrics, metadata, assets, output_png, output_pdf)
        report.template_id = LEGACY_TEMPLATE_ID
        report.template_version = ""
        report.fallback_used = True
        return report


def render_selected_infographic_pages(
    metrics,
    metadata: dict,
    assets: dict,
    config: dict,
    output_dir: Path,
    basename: str,
    output_pdf: Path | None = None,
    max_per_page: int = 9,
):
    template_config = normalize_template_config(config.get("template"))
    try:
        template = get_template_registry().get(template_config.get("id"))
        context = TemplateContext(metrics, metadata, assets, config, demo_mode=bool(st.session_state.demo_mode))
        if not template.supports(context):
            raise ValueError(f"template incompatível com {len(metrics)} indicador(es)")
        return template.render_pages(context, output_dir, basename, output_pdf)
    except Exception as exc:
        _render_template_failure(exc)
        report = render_compat_infographic_pages(metrics, metadata, assets, output_dir, basename, output_pdf, max_per_page=max_per_page)
        report.template_id = LEGACY_TEMPLATE_ID
        report.template_version = ""
        report.fallback_used = True
        return report


def build_current_config(metadata: dict, sections: list[dict], indicators: list[dict], columns: list[str], source: str, export: dict, template: dict) -> dict:
    config = empty_config(columns, source)
    config["metadata"] = metadata
    config["template"] = normalize_template_config(template)
    config["sections"] = sections
    config["indicators"] = apply_sections_to_indicators(indicators, sections)
    config["export"].update(export)
    return update_schema(config, columns)


def maybe_render_preview(valid_metrics, metadata, assets, max_per_page: int, config: dict):
    preview_controls()
    if st.session_state.preview_minimized:
        return None, False

    if not valid_metrics:
        st.info("Configure pelo menos um indicador válido para gerar a prévia.")
        return None, False
    if len(valid_metrics) > max_per_page:
        st.warning(
            f"Foram configurados {len(valid_metrics)} indicadores. "
            f"O limite legível por página é {max_per_page}."
        )
        multipage = st.checkbox("Gerar mais de uma página", value=True, key="preview_multipage")
        if not multipage:
            return None, False
        preview_metrics = valid_metrics[:max_per_page]
        preview_png = OUTPUT_DIR / "preview_p01.png"
        preview_config = deepcopy(config)
        preview_config["template"] = normalize_template_config(config.get("template"))
        report = render_selected_infographic(preview_metrics, metadata, assets, preview_config, preview_png, None)
        st.caption("Prévia da primeira página.")
        render_preview_image(preview_png)
        return report, True

    preview_png = OUTPUT_DIR / "preview.png"
    report = render_selected_infographic(valid_metrics, metadata, assets, config, preview_png, None)
    render_preview_image(preview_png)
    return report, False


st.set_page_config(page_title="Estúdio de Infográficos | Observatório", page_icon=":material/insert_chart:", layout="wide")
init_state()
inject_styles()
st.session_state.workflow_mode = FREE_MODE_LABEL
render_free_mode_app()
st.stop()

st.title("Estúdio de Infográficos")
st.caption("Modo avançado: o conteúdo vem do CSV, dos cálculos e do design institucional selecionado.")

with st.sidebar:
    st.header("Dados")
    render_custom_rules_manager()
    if st.button("Nova configuração / limpar indicadores", width="stretch"):
        st.session_state.current_config = clear_indicators(
            st.session_state.current_config,
            source=st.session_state.csv_name,
        )
        st.session_state.auto_proposal = None
        reset_editor_state()
        st.success("Configuração da interface limpa. Nenhum arquivo foi apagado.")

    if st.button("Carregar exemplo de demonstração", width="stretch"):
        load_demo()
        st.success("Exemplo de demonstração carregado.")

    uploaded_csv = st.file_uploader("Carregar CSV", type=["csv"])
    st.selectbox("Separador", SEPARATOR_OPTIONS, key="separator_label")
    st.selectbox("Codificação", ENCODING_OPTIONS, key="encoding_label")
    st.selectbox("Primeira linha é cabeçalho?", HEADER_OPTIONS, key="header_label")

if uploaded_csv is not None:
    set_csv_bytes(uploaded_csv.getvalue(), uploaded_csv.name, demo_mode=False)

if st.session_state.csv_bytes is None:
    st.info("Carregue um arquivo CSV para começar.")
    st.stop()

try:
    dataframe, profile = load_csv(
        BytesIO(st.session_state.csv_bytes),
        separator=separator_value(st.session_state.separator_label),
        encoding=None if st.session_state.encoding_label == "Automática" else st.session_state.encoding_label,
        has_header=header_value(st.session_state.header_label),
    )
except Exception as exc:
    st.error(f"Não foi possível ler o CSV: {exc}")
    st.stop()

current_signature = csv_schema_signature(profile.columns)
if st.session_state.active_schema_signature and st.session_state.active_schema_signature != current_signature:
    st.session_state.current_config = empty_config(profile.columns, st.session_state.csv_name)
    reset_editor_state()
    st.warning("O esquema do CSV mudou; os indicadores atuais foram limpos para evitar reaproveitamento indevido.")
else:
    st.session_state.current_config = update_schema(
        normalize_config(st.session_state.current_config, profile.columns, source=st.session_state.csv_name),
        profile.columns,
    )
st.session_state.active_schema_signature = current_signature

with st.sidebar:
    uploaded_config = st.file_uploader("Carregar configuração YAML", type=["yaml", "yml"])
    applied_config = load_yaml(uploaded_config, profile.columns, st.session_state.csv_name)
    if applied_config is not None:
        st.session_state.current_config = applied_config
        reset_editor_state()
        st.success("Configuração aplicada.")

if st.session_state.demo_mode:
    st.warning("Modo de demonstração — os dados exibidos são fictícios.")

st.subheader("CSV carregado")
summary_cols = st.columns(5)
summary_cols[0].metric("Arquivo", st.session_state.csv_name)
summary_cols[1].metric("Linhas", profile.row_count)
summary_cols[2].metric("Colunas", len(profile.columns))
summary_cols[3].metric("Separador", repr(profile.separator))
summary_cols[4].metric("Formato", profile.data_shape)

with st.expander("Colunas, tipos, ausências e prévia", expanded=True):
    st.dataframe(pd.DataFrame({
        "coluna": profile.columns,
        "tipo inferido": [profile.dtypes[column] for column in profile.columns],
        "valores ausentes": [profile.missing_values[column] for column in profile.columns],
    }), width="stretch", hide_index=True)
    st.dataframe(dataframe.head(20), width="stretch")

config = st.session_state.current_config
if not config.get("indicators"):
    st.subheader("Como deseja iniciar a configuração?")
    options = ["Gerar infográfico automaticamente", "Configurar manualmente", "Carregar um YAML compatível"]
    if profile.data_shape == "agregado" and aggregate_indicators_from_dataframe(dataframe):
        options.insert(2, "Criar cards automaticamente do CSV agregado")
    choice = st.radio("Escolha o ponto de partida", options, horizontal=True)
    if st.button("Aplicar escolha inicial"):
        if choice == "Gerar infográfico automaticamente":
            st.session_state.auto_proposal = infer_config(dataframe, profile, st.session_state.csv_name)
            st.success("Proposta automática gerada para revisão.")
        elif choice == "Criar cards automaticamente do CSV agregado":
            config["indicators"] = aggregate_indicators_from_dataframe(dataframe)
            config["sections"] = sections_from_indicators(config["indicators"], [])
            st.session_state.current_config = update_schema(normalize_config(config, profile.columns, st.session_state.csv_name), profile.columns)
            reset_editor_state()
            st.success("Cards criados a partir das linhas do CSV agregado.")
        elif choice == "Configurar manualmente":
            st.session_state.current_config = empty_config(profile.columns, st.session_state.csv_name)
            reset_editor_state()
            st.success("Configuração vazia iniciada.")
        else:
            st.info("Use o carregador de YAML na barra lateral.")
        config = st.session_state.current_config

render_auto_review(dataframe, profile, st.session_state.csv_name)
if st.session_state.get("auto_proposal") is not None and not config.get("indicators"):
    st.stop()

width_state = panel_widths(st.session_state.preview_ratio, st.session_state.preview_minimized)
editor_col, preview_col = st.columns([width_state.editor, width_state.preview], gap="large")

with editor_col:
    st.subheader("Textos institucionais")
    metadata_config = config.get("metadata") or {}
    left, right = st.columns(2)
    with left:
        header = st.text_input("Cabeçalho institucional", metadata_config.get("header") or DEFAULT_HEADER)
        title = st.text_input("Título", metadata_config.get("title", ""))
        subtitle = st.text_area("Subtítulo", metadata_config.get("subtitle", ""), height=92)
        period = st.text_input("Período dos dados", metadata_config.get("period", ""))
    with right:
        source = st.text_input("Fonte", metadata_config.get("source", ""))
        updated_at = st.text_input("Data de atualização", metadata_config.get("updated_at", ""))
        cta = st.text_input("Chamada final", metadata_config.get("cta", ""))
        website = st.text_input("Endereço eletrônico opcional", metadata_config.get("website", ""))

    metadata = {
        "header": header,
        "title": title,
        "subtitle": subtitle,
        "period": period,
        "source": source,
        "updated_at": updated_at,
        "cta": cta,
        "website": website,
    }

    st.subheader("Indicadores")
    toolbar = st.columns([1, 1, 1, 3])
    indicators = [deepcopy(item) for item in config.get("indicators") or []]
    with toolbar[0]:
        if st.button("Adicionar indicador", width="stretch"):
            indicators.append(new_indicator(profile.columns, [str(item.get("id")) for item in indicators], order=len(indicators) + 1))
            reset_editor_state()
    with toolbar[1]:
        indicator_labels = [f"{item.get('order', index + 1)} · {item.get('label') or item.get('id')}" for index, item in enumerate(indicators)]
        selected_duplicate = st.selectbox("Duplicar", [""] + indicator_labels, label_visibility="collapsed")
    with toolbar[2]:
        if st.button("Duplicar indicador", width="stretch") and selected_duplicate:
            selected_index = indicator_labels.index(selected_duplicate)
            indicators = duplicate_indicator(indicators, indicators[selected_index]["id"])
            reset_editor_state()
    with toolbar[3]:
        selected_remove = st.selectbox("Excluir indicador", [""] + indicator_labels)
        if st.button("Excluir selecionado") and selected_remove:
            selected_index = indicator_labels.index(selected_remove)
            indicators = remove_indicator(indicators, indicators[selected_index]["id"])
            reset_editor_state()

    edited_indicators = editable_indicator_table(indicators, profile.columns)

    st.subheader("Seções")
    edited_sections, edited_indicators = editable_sections(edited_indicators, config.get("sections") or [])
    edited_indicators = reorder_indicators(apply_sections_to_indicators(edited_indicators, edited_sections))

    config_errors = validate_required_metadata(metadata) + validate_metric_configs(edited_indicators, profile.columns)
    valid_metrics, metric_errors = calculate_metrics(dataframe, edited_indicators, metadata)
    metrics_by_id = metric_lookup(valid_metrics)

    render_appearance_launcher(edited_indicators, metrics_by_id, profile.columns, st.session_state.csv_name)

    if config_errors:
        st.warning("\n".join(config_errors))
    if metric_errors:
        st.warning("\n".join(f"{error.label}: {error.error}" for error in metric_errors))

    with st.expander("Como cada indicador foi calculado", expanded=bool(valid_metrics)):
        if valid_metrics:
            st.dataframe(pd.DataFrame([{
                "indicador": metric.label,
                "seção": metric.section,
                "operação": OPERATION_LABELS.get(metric.operation, metric.operation),
                "coluna": metric.column,
                "filtro": metric.filter_applied,
                "cálculo": metric.calculation,
                "valor exibido": metric.display_value,
            } for metric in valid_metrics]), width="stretch", hide_index=True)
        else:
            st.info("Ainda não há indicadores válidos.")

    template_config = render_template_selector(config.get("template") or {})

    assets = {
        "observatorio_logo": ROOT / "assets" / "logo_observatorio.png",
        "bahia_logo": ROOT / "assets" / "logo_estado_bahia.jpeg",
    }

    st.subheader("Salvar configuração")
    export_config = config.get("export") or {}
    export_config["max_indicators_per_page"] = selected_template_capacity(template_config, int(export_config.get("max_indicators_per_page") or 9))
    current_config = build_current_config(
        metadata,
        edited_sections,
        edited_indicators,
        profile.columns,
        st.session_state.csv_name,
        export_config,
        template_config,
    )
    st.session_state.current_config = current_config

    yaml_bytes = yaml.safe_dump(current_config, allow_unicode=True, sort_keys=False).encode("utf-8")
    st.download_button("Baixar configuração YAML", yaml_bytes, file_name="config_infografico.yaml", mime="application/x-yaml")
    if st.button("Salvar configuração em output/"):
        names = export_names(st.session_state.csv_name, date.today())
        path = OUTPUT_DIR / names["png"].replace("infografico_", "config_").replace(".png", ".yaml")
        path.write_bytes(yaml_bytes)
        st.success(f"Configuração salva em {path}")

    st.subheader("Exportação")
    max_per_page = int((current_config.get("export") or {}).get("max_indicators_per_page") or 9)
    if not str(metadata.get("source") or "").strip():
        st.warning("Fonte institucional vazia. A linha de fonte será omitida no infográfico; o nome do CSV ficará somente na auditoria.")
    if valid_metrics and st.button("Gerar arquivos finais"):
        names = export_names(st.session_state.csv_name, date.today())
        output_png = OUTPUT_DIR / names["png"]
        output_pdf = OUTPUT_DIR / names["pdf"]
        audit_path = OUTPUT_DIR / names["audit"]
        auto_audit_path = OUTPUT_DIR / names["audit"].replace("auditoria_", "auditoria_inferencia_")
        data_path = OUTPUT_DIR / names["data"]
        validation_path = OUTPUT_DIR / names["validation"]
        basename = output_png.stem

        if len(valid_metrics) > max_per_page:
            final_report = render_selected_infographic_pages(valid_metrics, metadata, assets, current_config, OUTPUT_DIR, basename, output_pdf, max_per_page=max_per_page)
        else:
            final_report = render_selected_infographic(valid_metrics, metadata, assets, current_config, output_png, output_pdf)

        audit_mode = "automatica" if any(bool(item.get("auto_applied")) for item in current_config.get("indicators") or []) else "manual"
        write_audit(
            valid_metrics,
            audit_path,
            template=current_config.get("template") or {},
            slot_map=getattr(final_report, "slot_map", {}),
            mode=audit_mode,
            fallback_used=bool(getattr(final_report, "fallback_used", False)),
            csv_name=st.session_state.csv_name,
        )
        write_automatic_audit(current_config, auto_audit_path)
        save_used_data(dataframe, data_path)
        write_validation_report(final_report, validation_path, len(valid_metrics))
        st.success("Arquivos gerados em output/.")

        download_targets = []
        if len(valid_metrics) > max_per_page and hasattr(final_report, "png_pages"):
            download_targets.extend(Path(path) for path in final_report.png_pages)
        else:
            download_targets.append(output_png)
        download_targets.extend([output_pdf, audit_path, auto_audit_path, data_path, validation_path])
        for path in download_targets:
            if path.exists():
                mime = "image/png" if path.suffix == ".png" else "application/pdf" if path.suffix == ".pdf" else "text/csv" if path.suffix == ".csv" else "text/plain"
                st.download_button(f"Baixar {path.name}", path.read_bytes(), file_name=path.name, mime=mime)

with preview_col:
    assets = {
        "observatorio_logo": ROOT / "assets" / "logo_observatorio.png",
        "bahia_logo": ROOT / "assets" / "logo_estado_bahia.jpeg",
    }
    report, multipage = maybe_render_preview(valid_metrics, metadata, assets, max_per_page, current_config)
    if report and report.errors:
        st.error("\n".join(report.errors))
