from pathlib import Path

from src.data_loader import load_csv


def test_reads_semicolon_utf8_without_header(tmp_path: Path):
    path = tmp_path / "dados.csv"
    path.write_text("Indicador Alfa;12345\nIndicador Beta;678\n", encoding="utf-8-sig")

    df, profile = load_csv(path, has_header=False)

    assert profile.encoding == "utf-8-sig"
    assert profile.separator == ";"
    assert profile.columns == ["indicador", "valor"]
    assert profile.row_count == 2
    assert profile.data_shape == "agregado"
    assert df.iloc[0]["indicador"] == "Indicador Alfa"


def test_reads_comma_utf8_with_header(tmp_path: Path):
    path = tmp_path / "dados.csv"
    path.write_text("nome,valor\nA,1\nB,2\n", encoding="utf-8")

    df, profile = load_csv(path)

    assert profile.separator == ","
    assert profile.has_header is True
    assert profile.columns == ["nome", "valor"]
    assert df["valor"].tolist() == ["1", "2"]


def test_reads_windows_1252(tmp_path: Path):
    path = tmp_path / "dados.csv"
    path.write_bytes("nome;valor\nPós;1\n".encode("cp1252"))

    df, profile = load_csv(path, separator=";", encoding="cp1252", has_header=True)

    assert profile.encoding == "cp1252"
    assert df.iloc[0]["nome"] == "Pós"


def test_detects_standard_long_csv_header(tmp_path: Path):
    path = tmp_path / "longo.csv"
    path.write_text(
        "indicador_id,periodo,recorte_id,valor\n"
        "pesquisadores_ativos,2021-2026,total,100\n",
        encoding="utf-8",
    )

    df, profile = load_csv(path)

    assert profile.has_header is True
    assert profile.columns == ["indicador_id", "periodo", "recorte_id", "valor"]
    assert df.iloc[0]["valor"] == "100"
