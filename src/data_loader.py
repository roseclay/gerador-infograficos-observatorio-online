from __future__ import annotations

from dataclasses import dataclass
import csv
import io
from pathlib import Path
from typing import Any

import pandas as pd

from .formatting import is_missing, parse_brazilian_number


ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")
SEPARATORS = (";", ",", "\t", "|")


@dataclass(frozen=True)
class CsvProfile:
    encoding: str
    separator: str
    columns: list[str]
    dtypes: dict[str, str]
    row_count: int
    missing_values: dict[str, int]
    data_shape: str
    has_header: bool


def read_source_bytes(source: Any) -> bytes:
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if hasattr(source, "getvalue"):
        data = source.getvalue()
        return data if isinstance(data, bytes) else str(data).encode("utf-8")
    if hasattr(source, "read"):
        position = None
        try:
            position = source.tell()
        except Exception:
            position = None
        data = source.read()
        if position is not None:
            source.seek(position)
        return data if isinstance(data, bytes) else str(data).encode("utf-8")
    raise TypeError("fonte de CSV nao suportada")


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ENCODINGS:
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin1"


def decode_bytes(raw: bytes, encoding: str | None = None) -> tuple[str, str]:
    selected = encoding or detect_encoding(raw)
    return raw.decode(selected), selected


def detect_separator(text: str) -> str:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(SEPARATORS))
        return dialect.delimiter
    except csv.Error:
        counts = {sep: sample.count(sep) for sep in SEPARATORS}
        return max(counts, key=counts.get) if any(counts.values()) else ";"


def _looks_numeric(value: Any) -> bool:
    try:
        parse_brazilian_number(value)
        return True
    except Exception:
        return False


def _normalized_header_cell(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("í", "i").replace("é", "e").replace("ç", "c").replace("ã", "a")
    return "".join(char if char.isalnum() else "_" for char in text).strip("_")


def detect_has_header(text: str, separator: str) -> bool:
    rows = list(csv.reader(io.StringIO(text), delimiter=separator))
    rows = [row for row in rows if any(str(cell).strip() for cell in row)]
    if not rows:
        return True
    first = rows[0]
    known_headers = {
        "indicador_id",
        "id_indicador",
        "indicador",
        "periodo",
        "recorte_id",
        "recorte",
        "valor",
        "value",
        "unidade",
        "ano",
        "categoria",
    }
    normalized = {_normalized_header_cell(cell) for cell in first}
    if len(first) > 2 and len(normalized.intersection(known_headers)) >= 2:
        return True
    if len(first) == 2 and _looks_numeric(first[1]):
        return False
    try:
        return csv.Sniffer().has_header(text[:4096])
    except csv.Error:
        if len(rows) < 2:
            return True
        first_numeric = sum(_looks_numeric(cell) for cell in rows[0])
        later_numeric = sum(_looks_numeric(cell) for row in rows[1:4] for cell in row)
        return first_numeric == 0 and later_numeric > 0


def _default_columns(column_count: int) -> list[str]:
    if column_count == 2:
        return ["indicador", "valor"]
    return [f"coluna_{index + 1}" for index in range(column_count)]


def load_csv(source: Any, separator: str | None = None, encoding: str | None = None, has_header: bool | None = None) -> tuple[pd.DataFrame, CsvProfile]:
    raw = read_source_bytes(source)
    text, selected_encoding = decode_bytes(raw, encoding)
    selected_separator = separator or detect_separator(text)
    selected_has_header = detect_has_header(text, selected_separator) if has_header is None else bool(has_header)

    header = 0 if selected_has_header else None
    dataframe = pd.read_csv(
        io.StringIO(text),
        sep=selected_separator,
        header=header,
        dtype=str,
        keep_default_na=False,
    )
    dataframe = dataframe.dropna(how="all")
    dataframe = dataframe.loc[:, ~dataframe.columns.astype(str).str.startswith("Unnamed:")]

    if not selected_has_header:
        dataframe.columns = _default_columns(dataframe.shape[1])
    else:
        dataframe.columns = [str(column).strip() for column in dataframe.columns]

    for column in dataframe.columns:
        dataframe[column] = dataframe[column].map(lambda value: "" if value is None else str(value).strip())

    profile = profile_dataframe(dataframe, selected_encoding, selected_separator, selected_has_header)
    return dataframe, profile


def infer_column_type(series: pd.Series) -> str:
    values = [value for value in series.tolist() if not is_missing(value)]
    if not values:
        return "vazio"
    numeric_count = sum(_looks_numeric(value) for value in values)
    if numeric_count == len(values):
        return "numerico"
    if numeric_count:
        return "misto"
    return "texto"


def infer_data_shape(dataframe: pd.DataFrame) -> str:
    if dataframe.shape[1] == 2:
        first = dataframe.iloc[:, 0]
        second = dataframe.iloc[:, 1]
        first_text = first.map(lambda value: not _looks_numeric(value) and not is_missing(value)).mean() if len(first) else 0
        second_values = second.map(lambda value: not is_missing(value)).mean() if len(second) else 0
        if first_text >= 0.8 and second_values >= 0.8 and first.nunique(dropna=True) >= max(1, len(first) * 0.7):
            return "agregado"
    return "detalhado"


def profile_dataframe(dataframe: pd.DataFrame, encoding: str, separator: str, has_header: bool) -> CsvProfile:
    missing = {
        column: int(dataframe[column].map(is_missing).sum())
        for column in dataframe.columns
    }
    dtypes = {column: infer_column_type(dataframe[column]) for column in dataframe.columns}
    return CsvProfile(
        encoding=encoding,
        separator=separator,
        columns=[str(column) for column in dataframe.columns],
        dtypes=dtypes,
        row_count=int(len(dataframe)),
        missing_values=missing,
        data_shape=infer_data_shape(dataframe),
        has_header=has_header,
    )


def save_used_data(dataframe: pd.DataFrame, output_path: str | Path) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
