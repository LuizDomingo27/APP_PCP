"""Leitura da planilha de Follow Up em streaming.

Por que não `pandas.read_excel` / `openpyxl` direto: o arquivo de referência tem
139 MB porque as abas BASE MP têm fórmulas arrastadas até a linha 1.048.362 para
~1.034 registros reais — cerca de 990 MB de XML de células vazias. Abrir isso
pelo caminho convencional custa minutos e vários GB de RAM.

Aqui o XML é consumido com SAX (`iterparse`), lendo só as abas e colunas do
contrato e parando quando encontra uma faixa longa de linhas vazias.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import pandas as pd

from . import schema
from .errors import (
    AbaAusenteError,
    ArquivoInvalidoError,
    CabecalhoAmbiguoError,
    ColunaAusenteError,
    DadoVazioError,
)

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_ROW, _C, _V, _IS, _T = f"{_NS}row", f"{_NS}c", f"{_NS}v", f"{_NS}is", f"{_NS}t"
_RE_COL = re.compile(r"[A-Z]+")

# Linhas vazias consecutivas toleradas antes de assumir fim de dados.
# As abas BASE MP têm ~1M linhas-fantasma no fim; sem isso a leitura levaria
# minutos. Folga generosa: nenhuma tabela real tem 5.000 linhas em branco no meio.
_MAX_VAZIAS = 5_000


def _indice_coluna(ref: str) -> int:
    """'AB12' -> 27 (índice 0-based da coluna); -1 se a referência não é válida.

    Referência sem letra ('12', '') aparece em .xlsx gerado por ferramenta que
    não é o Excel. Antes isso estourava um `AttributeError` no meio da leitura;
    a célula é descartada, porque sem letra não há posição — e adivinhar posição
    de coluna é exatamente como o bug do fluxo produtivo começou.
    """
    casado = _RE_COL.match(ref)
    if casado is None:
        return -1
    n = 0
    for ch in casado.group():
        n = n * 26 + ord(ch) - 64
    return n - 1


@dataclass
class Planilha:
    """Acesso de baixo nível ao .xlsx aberto."""

    caminho: str
    _zip: zipfile.ZipFile
    _abas: dict[str, str]
    _shared: list[str]

    @classmethod
    def abrir(cls, caminho: str) -> "Planilha":
        try:
            z = zipfile.ZipFile(caminho)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ArquivoInvalidoError(
                f"Não consegui abrir '{caminho}' como .xlsx: {exc}"
            ) from exc
        # Um .zip qualquer passa no `ZipFile` e só falha aqui, ao procurar as
        # partes do Excel. Sem este try o erro subia como `KeyError` cru e a
        # tela dizia "erro inesperado" — sem dizer o que fazer.
        try:
            return cls(caminho, z, _mapear_abas(z), _ler_shared_strings(z))
        except Exception as exc:
            z.close()
            raise ArquivoInvalidoError(
                f"'{caminho}' é um arquivo compactado válido, mas não tem a "
                f"estrutura interna de uma planilha do Excel ({exc}).\n"
                f"Confirme que é o .xlsx do Follow Up e não um .zip renomeado "
                f"ou um arquivo baixado pela metade."
            ) from exc

    @property
    def abas(self) -> list[str]:
        return list(self._abas)

    def fechar(self) -> None:
        self._zip.close()

    def __enter__(self) -> "Planilha":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fechar()

    def caminho_aba(self, nome: str) -> str:
        if nome not in self._abas:
            raise AbaAusenteError(nome, self.abas)
        return self._abas[nome]


def _mapear_abas(z: zipfile.ZipFile) -> dict[str, str]:
    """Nome visível da aba -> caminho do XML dentro do zip."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    alvo = {
        m.group(1): m.group(2)
        for m in re.finditer(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels)
    }
    abas: dict[str, str] = {}
    for m in re.finditer(r"<sheet\b([^>]*)/>", wb):
        attrs = m.group(1)
        nome = re.search(r'name="([^"]*)"', attrs)
        rid = re.search(r'r:id="([^"]*)"', attrs)
        if not (nome and rid) or rid.group(1) not in alvo:
            continue
        destino = alvo[rid.group(1)].lstrip("/")
        if not destino.startswith("xl/"):
            destino = "xl/" + destino
        abas[_desescapar(nome.group(1))] = destino
    return abas


def _desescapar(s: str) -> str:
    return (
        s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def _ler_shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    out: list[str] = []
    with z.open("xl/sharedStrings.xml") as fh:
        for _, el in ET.iterparse(fh):
            if el.tag == f"{_NS}si":
                out.append("".join(t.text or "" for t in el.iter(_T)))
                el.clear()
    return out


def _valor(c: ET.Element, shared: list[str]) -> str:
    """Valor textual de uma célula, já resolvendo sharedString e inlineStr."""
    tipo = c.get("t")
    if tipo == "inlineStr":
        node = c.find(_IS)
        return "".join(t.text or "" for t in node.iter(_T)) if node is not None else ""
    v = c.find(_V)
    if v is None or v.text is None:
        return ""
    if tipo == "s":
        try:
            return shared[int(v.text)]
        except (ValueError, IndexError):
            return ""
    if tipo == "e":
        # #N/A, #REF!, #VALUE! -> tratados como vazio, nunca como zero.
        return ""
    return v.text


def _linhas(pl: Planilha, aba: str):
    """Gera listas de células por linha, parando na faixa longa de vazias."""
    caminho = pl.caminho_aba(aba)
    vazias = 0
    viu_dado = False
    with pl._zip.open(caminho) as fh:
        ctx = ET.iterparse(fh, events=("start", "end"))
        _, raiz = next(ctx)
        for evento, el in ctx:
            if evento != "end" or el.tag != _ROW:
                continue
            celulas = [
                (indice, _valor(c, pl._shared))
                for c in el.findall(_C)
                if (indice := _indice_coluna(c.get("r") or "")) >= 0
            ]
            preenchidas = [(i, v) for i, v in celulas if v != ""]
            el.clear()
            raiz.clear()

            if not preenchidas:
                vazias += 1
                if viu_dado and vazias >= _MAX_VAZIAS:
                    return
                continue
            vazias = 0
            viu_dado = True
            yield preenchidas


def _resolver_cabecalho(
    aba: str, cabecalho: list[tuple[int, str]]
) -> tuple[dict[str, int], list[str]]:
    """Casa o cabeçalho do arquivo com o contrato, por nome normalizado.

    Cabeçalho repetido nunca é resolvido por convenção implícita: ou o contrato
    declara `ocorrencia`, ou a carga falha. Ambas as bases têm um caso real e
    eles se resolvem de formas opostas — na BASE MP vale a 1ª 'Referência', na
    BASE CPG vale a 2ª 'Programado'.
    """
    presentes: dict[str, list[int]] = {}
    rotulos: list[str] = []
    for idx, texto in sorted(cabecalho):
        chave = schema.normalizar_cabecalho(texto)
        rotulos.append(str(texto))
        if chave:
            presentes.setdefault(chave, []).append(idx)

    mapa: dict[str, int] = {}
    faltando: list[str] = []
    for col in schema.colunas(aba):
        chave = next((k for k in col.chaves if k in presentes), None)
        if chave is None:
            if col.required:
                faltando.append(col.header)
            continue

        ocorrencias = presentes[chave]
        # `ocorrencia` só entra em jogo quando há de fato ambiguidade. Se a
        # unidade não exportar a coluna auxiliar homônima, a única existente é
        # a certa — exigir a "segunda" aí seria rigidez sem ganho.
        if len(ocorrencias) == 1:
            mapa[col.canonical] = ocorrencias[0]
            continue
        if col.ocorrencia is None:
            raise CabecalhoAmbiguoError(aba, col.header, len(ocorrencias))
        if col.ocorrencia > len(ocorrencias):
            raise ColunaAusenteError(
                aba,
                [
                    f"{col.header} (contrato pede a ocorrência {col.ocorrencia}, "
                    f"mas o arquivo tem {len(ocorrencias)})"
                ],
                rotulos,
            )
        mapa[col.canonical] = ocorrencias[col.ocorrencia - 1]

    if faltando:
        raise ColunaAusenteError(aba, faltando, rotulos)
    return mapa, rotulos


def ler_aba(pl: Planilha, aba: str) -> pd.DataFrame:
    """Lê uma aba do contrato e devolve DataFrame com nomes canônicos."""
    gerador = _linhas(pl, aba)
    try:
        cabecalho = next(gerador)
    except StopIteration:
        raise DadoVazioError(aba) from None

    mapa, _ = _resolver_cabecalho(aba, cabecalho)
    canonicos = list(mapa)
    indices = [mapa[c] for c in canonicos]
    largura = max(indices) + 1

    registros: list[list[str]] = []
    for celulas in gerador:
        linha = [""] * largura
        for i, v in celulas:
            if i < largura:
                linha[i] = v
        registros.append([linha[i] for i in indices])

    if not registros:
        raise DadoVazioError(aba)

    df = pd.DataFrame(registros, columns=canonicos)
    # Colunas opcionais ausentes nascem vazias para o resto do código não
    # precisar checar existência a toda hora.
    for col in schema.colunas(aba):
        if col.canonical not in df.columns:
            df[col.canonical] = ""
    return df


def ler_planilha(caminho: str) -> dict[str, pd.DataFrame]:
    """Lê BASE CPG e BASE MP de um arquivo de Follow Up."""
    with Planilha.abrir(caminho) as pl:
        return {aba: ler_aba(pl, aba) for aba in (schema.BASE_CPG, schema.BASE_MP)}
