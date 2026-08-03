"""Estado da sessão e ponte com a camada de domínio.

A UI nunca fala com `pcp.ingest` direto — só com `pcp.loader` através daqui.
Todo erro de domínio é capturado e convertido em mensagem exibível.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from pcp import Carga, carregar, loader
from pcp.cache import CacheParquet
from pcp.errors import PCPError
from pcp.rules import Filtros

CHAVE_CARGAS = "pcp_cargas"
CHAVE_ATIVA = "pcp_carga_ativa"


@dataclass
class ResultadoCarga:
    """Sucesso ou falha de uma tentativa de carga, pronto para a tela."""

    carga: Carga | None = None
    erro: str | None = None
    titulo_erro: str = "Não consegui ler esta planilha"

    @property
    def ok(self) -> bool:
        return self.carga is not None


def _cache() -> CacheParquet:
    return CacheParquet()


def carregar_upload(arquivo) -> ResultadoCarga:
    """Processa um arquivo enviado pelo usuário.

    Grava em disco temporário porque o leitor precisa de acesso randômico ao
    zip; o cache Parquet é chaveado pelo conteúdo, então reenviar o mesmo
    arquivo não reprocessa.
    """
    destino: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".xlsx", prefix="pcp_"
        ) as tmp:
            tmp.write(arquivo.getbuffer())
            destino = Path(tmp.name)
        carga = carregar(destino, cache=_cache())
        carga.arquivo = arquivo.name
        return ResultadoCarga(carga=carga)
    except PCPError as exc:
        return ResultadoCarga(erro=str(exc))
    except MemoryError:
        return ResultadoCarga(
            erro="A planilha é grande demais para a memória disponível. "
            "Feche outros programas e tente de novo.",
            titulo_erro="Memória insuficiente",
        )
    except Exception as exc:  # rede de segurança: nada derruba a tela
        return ResultadoCarga(
            erro=f"Erro inesperado ao processar o arquivo: {exc}",
            titulo_erro="Falha inesperada",
        )
    finally:
        if destino is not None:
            destino.unlink(missing_ok=True)


def carregar_caminho(caminho: Path) -> ResultadoCarga:
    """Carrega um .xlsx já presente no disco.

    Existe porque o arquivo de Follow Up tem centenas de MB: reenviá-lo a cada
    sessão é desperdício quando ele já está na pasta do aplicativo.
    """
    try:
        carga = carregar(caminho, cache=_cache())
        carga.arquivo = caminho.name
        return ResultadoCarga(carga=carga)
    except PCPError as exc:
        return ResultadoCarga(erro=str(exc))
    except Exception as exc:
        return ResultadoCarga(
            erro=f"Erro inesperado ao processar o arquivo: {exc}",
            titulo_erro="Falha inesperada",
        )


def planilhas_locais(pasta: Path | None = None) -> list[Path]:
    """.xlsx na pasta do aplicativo, ignorando temporários do Excel (~$)."""
    raiz = pasta or Path.cwd()
    try:
        return sorted(
            p for p in raiz.glob("*.xlsx") if not p.name.startswith("~$")
        )
    except OSError:
        return []


def registrar(carga: Carga) -> None:
    """Guarda a carga na sessão, mantendo o histórico para comparação."""
    cargas: list[Carga] = st.session_state.setdefault(CHAVE_CARGAS, [])
    cargas = [c for c in cargas if c.arquivo != carga.arquivo]
    cargas.append(carga)
    cargas.sort(key=lambda c: (c.data_snapshot is None, c.data_snapshot))
    st.session_state[CHAVE_CARGAS] = cargas
    st.session_state[CHAVE_ATIVA] = carga.arquivo
    # A carga acabou de entrar no cache: a série do M7 precisa enxergá-la.
    esquecer_historico_local()


def cargas() -> list[Carga]:
    return st.session_state.get(CHAVE_CARGAS, [])


def carga_ativa() -> Carga | None:
    disponiveis = cargas()
    if not disponiveis:
        return None
    nome = st.session_state.get(CHAVE_ATIVA)
    return next((c for c in disponiveis if c.arquivo == nome), disponiveis[-1])


def carga_anterior() -> Carga | None:
    """Carga imediatamente anterior à ativa, para o diff do M1."""
    disponiveis = cargas()
    atual = carga_ativa()
    if atual is None or len(disponiveis) < 2:
        return None
    indice = disponiveis.index(atual)
    return disponiveis[indice - 1] if indice > 0 else None


CHAVE_HISTORICO = "pcp_historico_local"
CHAVE_ERRO_HISTORICO = "pcp_historico_local_erro"


def historico_local() -> list[Carga]:
    """Cargas guardadas no cache desta máquina — a série do M7.

    Lida uma vez por sessão: são leituras de Parquet, baratas, mas não a ponto
    de repetir a cada clique de filtro. Falha de leitura devolve lista vazia —
    histórico é um extra, não pode impedir o painel de abrir — mas o motivo
    fica guardado em `erro_historico_local()`: engolir a exceção fazia a tela
    do M7 pedir "carregue a planilha de outro dia" quando o problema era o
    cache, e o usuário recarregava sem nada mudar.
    """
    if CHAVE_HISTORICO not in st.session_state:
        try:
            st.session_state[CHAVE_HISTORICO] = loader.historico_local(_cache())
            st.session_state[CHAVE_ERRO_HISTORICO] = None
        except Exception as exc:
            st.session_state[CHAVE_HISTORICO] = []
            st.session_state[CHAVE_ERRO_HISTORICO] = str(exc)
    return st.session_state[CHAVE_HISTORICO]


def erro_historico_local() -> str | None:
    """Por que o cache local não pôde ser lido, se foi o caso."""
    return st.session_state.get(CHAVE_ERRO_HISTORICO)


def esquecer_historico_local() -> None:
    """Força reler o cache — usado depois de carregar uma planilha nova."""
    st.session_state.pop(CHAVE_HISTORICO, None)
    st.session_state.pop(CHAVE_ERRO_HISTORICO, None)


def esquecer_tudo() -> None:
    st.session_state[CHAVE_CARGAS] = []
    st.session_state.pop(CHAVE_ATIVA, None)


# --------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------

TODOS = "Todos"


def montar_filtros(valores: dict[str, str], competencia: tuple[int, int] | None) -> Filtros:
    ano, mes = competencia if competencia else (None, None)
    def limpar(chave: str) -> str | None:
        valor = valores.get(chave, TODOS)
        return None if valor in (TODOS, "", None) else valor

    return Filtros(
        mes=mes,
        ano=ano,
        familia=limpar("familia"),
        departamento=limpar("departamento"),
        tipo_produto=limpar("tipo_produto"),
        toc=limpar("toc"),
        quinzena=limpar("quinzena"),
    )
