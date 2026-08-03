"""Tipagem e normalização dos dados brutos.

Camada pura: recebe DataFrame de texto cru vindo de `ingest` e devolve DataFrame
tipado. Não faz I/O e não conhece planilha nem cache.

Duas responsabilidades que evitam bugs históricos da planilha:

1. **Normalizar texto de flag.** 'NÃO', 'Não', 'nao' e 'NAO ' precisam ser o
   mesmo valor, senão um `== "NÃO"` subconta silenciosamente.
2. **Barrar coluna numérica que chega como texto.** Foi assim que 'Corte' passou
   a somar a coluna 'Bimatéria' (SIM/NÃO) e devolver zero sem ninguém perceber.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

import pandas as pd

from . import schema
from .errors import TipoInvalidoError

# Excel conta dias a partir de 1899-12-30 (o "bug" do ano bissexto de 1900).
_EPOCA_EXCEL = pd.Timestamp("1899-12-30")

# Tolerância de sujeira antes de considerar que a coluna não é numérica.
_LIMITE_NAO_NUMERICO = 0.10


@dataclass
class Diagnostico:
    """O que a carga encontrou de anormal, sem ter sido fatal."""

    avisos: list[str] = field(default_factory=list)
    fora_de_dominio: dict[str, list[str]] = field(default_factory=dict)

    def avisar(self, msg: str) -> None:
        self.avisos.append(msg)

    @property
    def ok(self) -> bool:
        return not self.avisos and not self.fora_de_dominio


def normalizar_flag(serie: pd.Series) -> pd.Series:
    """'À Receber' -> 'A RECEBER'; 'Não ' -> 'NAO'."""
    texto = serie.fillna("").astype(str)
    sem_acento = texto.map(
        lambda s: "".join(
            c
            for c in unicodedata.normalize("NFKD", s)
            if not unicodedata.combining(c)
        )
    )
    return sem_acento.str.upper().str.strip().str.replace(r"\s+", " ", regex=True)


def _para_numero(serie: pd.Series) -> pd.Series:
    """Converte texto em número aceitando formato brasileiro (1.234,56)."""
    bruto = serie.fillna("").astype(str).str.strip()
    direto = pd.to_numeric(bruto, errors="coerce")
    faltando = direto.isna() & (bruto != "")
    if faltando.any():
        br = (
            bruto[faltando]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        direto.loc[faltando] = pd.to_numeric(br, errors="coerce")
    return direto


def _validar_numerica(aba: str, nome: str, bruto: pd.Series, convertido: pd.Series) -> None:
    preenchidas = bruto.fillna("").astype(str).str.strip() != ""
    total = int(preenchidas.sum())
    if total == 0:
        return
    invalidas = preenchidas & convertido.isna()
    if int(invalidas.sum()) / total > _LIMITE_NAO_NUMERICO:
        amostra = bruto[invalidas].astype(str).unique()[:5].tolist()
        raise TipoInvalidoError(aba, nome, amostra)


def _para_data(serie: pd.Series) -> pd.Series:
    """Aceita serial do Excel (46139) e texto ISO ('2026-07-31 04:37:04')."""
    bruto = serie.fillna("").astype(str).str.strip()
    saida = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    numerico = pd.to_numeric(bruto, errors="coerce")
    serial = numerico.notna() & (numerico > 0)
    if serial.any():
        saida.loc[serial] = _EPOCA_EXCEL + pd.to_timedelta(
            numerico[serial].astype(float), unit="D"
        )

    resto = (~serial) & (bruto != "")
    if resto.any():
        texto = bruto[resto]
        # ISO primeiro ('2026-07-31 04:37:04', formato da coluna Data Arquivo);
        # o que sobrar tenta dd/mm/aaaa, que é como o time digita.
        convertido = pd.to_datetime(texto, errors="coerce")
        pendente = convertido.isna()
        if pendente.any():
            convertido.loc[pendente] = pd.to_datetime(
                texto[pendente], errors="coerce", dayfirst=True
            )
        saida.loc[resto] = convertido
    return saida


def tipar(aba: str, df: pd.DataFrame, diag: Diagnostico | None = None) -> pd.DataFrame:
    """Aplica o contrato de tipos do schema sobre o DataFrame cru."""
    diag = diag if diag is not None else Diagnostico()
    out = pd.DataFrame(index=df.index)

    for col in schema.colunas(aba):
        if col.canonical not in df.columns:
            continue
        bruto = df[col.canonical]

        if col.kind == "num":
            convertido = _para_numero(bruto)
            _validar_numerica(aba, col.header, bruto, convertido)
            out[col.canonical] = convertido.fillna(0.0).astype("float64")

        elif col.kind == "int":
            convertido = _para_numero(bruto)
            _validar_numerica(aba, col.header, bruto, convertido)
            out[col.canonical] = convertido.astype("Int64")

        elif col.kind == "flag":
            out[col.canonical] = normalizar_flag(bruto)

        elif col.kind == "date":
            out[col.canonical] = _para_data(bruto)

        else:
            out[col.canonical] = bruto.fillna("").astype(str).str.strip()

    _checar_dominios(out, diag)
    return out


def _checar_dominios(df: pd.DataFrame, diag: Diagnostico) -> None:
    """Valor de flag fora do domínio é aviso, não erro.

    Não bloqueia porque um valor novo legítimo na base não pode travar a rotina
    do time — mas fica registrado e visível na tela de carga.
    """
    for canonical, permitidos in schema.DOMINIOS.items():
        if canonical not in df.columns:
            continue
        vistos = set(df[canonical].unique())
        estranhos = sorted(v for v in vistos - permitidos if v)
        if estranhos:
            diag.fora_de_dominio[canonical] = estranhos
            diag.avisar(
                f"A coluna '{canonical}' tem valores fora do esperado: "
                f"{', '.join(estranhos[:5])}. Foram tratados como não pertencentes "
                f"a nenhum detrator."
            )
