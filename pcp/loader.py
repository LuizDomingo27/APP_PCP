"""Orquestração da carga: ingestão -> tratamento -> cache.

Camada de aplicação. É o único ponto que conhece as três camadas de baixo ao
mesmo tempo; a interface fala só com daqui, nunca com `ingest` direto.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import ingest, rules, schema, transform
from .cache import CacheParquet, hash_arquivo
from .errors import PCPError
from .transform import Diagnostico


@dataclass
class Carga:
    """Resultado de uma carga bem-sucedida."""

    cpg: pd.DataFrame
    mp: pd.DataFrame
    unidade: str
    data_snapshot: pd.Timestamp | None
    competencias: list[tuple[int, int]]
    diagnostico: Diagnostico
    veio_do_cache: bool
    segundos: float
    arquivo: str = ""

    @property
    def rotulo_snapshot(self) -> str:
        """Texto do carimbo exibido em todo painel e exportação."""
        if self.data_snapshot is None:
            return "data não informada"
        return self.data_snapshot.strftime("%d/%m/%Y")


def carregar(
    caminho: str | Path,
    *,
    cache: CacheParquet | None = None,
    usar_cache: bool = True,
) -> Carga:
    """Carrega uma planilha de Follow Up, usando cache quando possível.

    Erros de contrato (aba/coluna ausente, coluna numérica que virou texto)
    sobem como `PCPError` com mensagem pronta para a tela — nunca viram
    resultado vazio ou zero.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise PCPError(f"Arquivo não encontrado: {caminho}")

    inicio = time.perf_counter()
    cache = cache or CacheParquet()
    chave = hash_arquivo(caminho)

    if usar_cache and (guardado := cache.ler(chave)):
        bases, entrada = guardado
        return _montar(
            bases,
            Diagnostico(avisos=list(entrada.metadados.get("avisos", []))),
            origem=str(caminho),
            veio_do_cache=True,
            segundos=time.perf_counter() - inicio,
        )

    diag = Diagnostico()
    brutas = ingest.ler_planilha(str(caminho))
    bases = {aba: transform.tipar(aba, df, diag) for aba, df in brutas.items()}

    carga = _montar(
        bases,
        diag,
        origem=str(caminho),
        veio_do_cache=False,
        segundos=time.perf_counter() - inicio,
    )
    if usar_cache:
        try:
            cache.gravar(
                chave,
                bases,
                {
                    "arquivo": caminho.name,
                    "unidade": carga.unidade,
                    "data_snapshot": carga.data_snapshot,
                    "avisos": diag.avisos,
                },
            )
        except OSError as exc:
            # Falha ao gravar cache degrada performance, não corretude.
            diag.avisar(f"Não consegui gravar o cache local: {exc}")
    return carga


def _montar(
    bases: dict[str, pd.DataFrame],
    diag: Diagnostico,
    *,
    origem: str,
    veio_do_cache: bool,
    segundos: float,
) -> Carga:
    """`origem` é o caminho de onde a carga veio — vira o nome exibido."""
    cpg = bases[schema.BASE_CPG]
    mp = bases[schema.BASE_MP]
    return Carga(
        cpg=cpg,
        mp=mp,
        unidade=rules.unidade(cpg),
        data_snapshot=rules.data_snapshot(cpg),
        competencias=rules.competencias(cpg),
        diagnostico=diag,
        veio_do_cache=veio_do_cache,
        segundos=segundos,
        arquivo=Path(origem).name,
    )


def comparar(anterior: Carga, atual: Carga, filtros: rules.Filtros) -> pd.DataFrame:
    """Diff de KPIs entre duas cargas — base do M1 (validação) e do M7."""
    antes = rules.kpis(anterior.cpg, anterior.mp, filtros).as_dict()
    depois = rules.kpis(atual.cpg, atual.mp, filtros).as_dict()
    return pd.DataFrame(
        [
            {
                "Indicador": nome,
                anterior.rotulo_snapshot: antes[nome],
                atual.rotulo_snapshot: depois[nome],
                "Variação": depois[nome] - antes[nome],
            }
            for nome in depois
        ]
    )


# --------------------------------------------------------------------------
# M7 · Evolução histórica — sem banco, a série vem do que já foi carregado
# --------------------------------------------------------------------------


def historico_local(cache: CacheParquet | None = None) -> list[Carga]:
    """Reconstrói as cargas guardadas no cache local, sem o .xlsx original.

    É o histórico pessoal do M7 dentro da decisão "sem banco de dados": cada
    planilha aberta uma vez nesta máquina vira um ponto da série, para sempre —
    sem o usuário precisar guardar arquivos de 139 MB.

    Entrada corrompida ou de contrato antigo é ignorada em silêncio: histórico
    incompleto degrada o gráfico, mas não pode impedir o app de abrir.
    """
    cache = cache or CacheParquet()
    cargas: list[Carga] = []
    for entrada in cache.listar():
        guardado = cache.ler(entrada.chave)
        if guardado is None:
            continue
        bases, _ = guardado
        if not {schema.BASE_CPG, schema.BASE_MP}.issubset(bases):
            continue
        try:
            carga = _montar(
                bases,
                Diagnostico(avisos=list(entrada.metadados.get("avisos", []))),
                origem=str(entrada.metadados.get("arquivo", entrada.chave)),
                veio_do_cache=True,
                segundos=0.0,
            )
        except (KeyError, ValueError):
            continue
        cargas.append(carga)
    return _ordenar_por_snapshot(cargas)


def _ordenar_por_snapshot(cargas: list[Carga]) -> list[Carga]:
    return sorted(cargas, key=lambda c: (c.data_snapshot is None, c.data_snapshot))


# Indicadores que compõem a curva. São os mesmos do painel principal: a série
# histórica não pode inventar métrica que o time não reconhece.
INDICADORES_SERIE: tuple[str, ...] = (
    "carteira_total",
    "programado",
    "a_programar",
    "sem_avi",
    "sem_mp",
    "sem_prototipo",
    "mp_prot_sem_avi",
    "disponivel_para_programar",
)


def serie_historica(cargas: list[Carga], filtros: rules.Filtros) -> pd.DataFrame:
    """Um ponto por snapshot, com o mesmo recorte aplicado a todos.

    Snapshot repetido (o mesmo arquivo carregado duas vezes com nomes
    diferentes) entra uma vez só: dois pontos na mesma data achatariam a
    velocidade de programação para infinito.
    """
    linhas = []
    vistos: set[pd.Timestamp] = set()
    for carga in _ordenar_por_snapshot(cargas):
        if carga.data_snapshot is None or carga.data_snapshot.normalize() in vistos:
            continue
        vistos.add(carga.data_snapshot.normalize())
        k = rules.kpis(carga.cpg, carga.mp, filtros)
        linhas.append(
            {
                "snapshot": carga.data_snapshot.normalize(),
                "arquivo": carga.arquivo,
                **{nome: k.as_dict()[nome] for nome in INDICADORES_SERIE},
                "pct_programado": k.pct_programado,
            }
        )
    return pd.DataFrame(linhas, columns=["snapshot", "arquivo", *INDICADORES_SERIE, "pct_programado"])


@dataclass(frozen=True)
class Evolucao:
    """Curva dos indicadores e projeção de fechamento da competência."""

    serie: pd.DataFrame
    velocidade: float | None          # peças programadas por dia
    dias_uteis_restantes: float | None
    data_projetada: pd.Timestamp | None
    fim_competencia: pd.Timestamp | None

    @property
    def pontos(self) -> int:
        return len(self.serie)

    @property
    def suficiente(self) -> bool:
        """Dois snapshots é o mínimo para existir variação medível."""
        return self.pontos >= 2

    @property
    def dias_de_atraso(self) -> float | None:
        """Quanto a projeção passa do fim da competência. Negativo = folga."""
        if self.data_projetada is None or self.fim_competencia is None:
            return None
        return float((self.data_projetada - self.fim_competencia).days)

    def variacao(self, indicador: str) -> float | None:
        """Diferença entre o primeiro e o último snapshot da série."""
        if not self.suficiente or indicador not in self.serie.columns:
            return None
        return float(self.serie[indicador].iloc[-1] - self.serie[indicador].iloc[0])


def evolucao(cargas: list[Carga], filtros: rules.Filtros) -> Evolucao:
    """Velocidade de programação e projeção de fechamento a partir da série.

    A velocidade usa a janela inteira (primeiro contra último snapshot), não o
    último par: com carga diária, um feriado no meio derrubaria a projeção a
    zero e o painel anunciaria que o mês nunca fecha.
    """
    serie = serie_historica(cargas, filtros)
    fim = _fim_da_competencia(filtros)

    if len(serie) < 2:
        return Evolucao(serie, None, None, None, fim)

    dias = float((serie["snapshot"].iloc[-1] - serie["snapshot"].iloc[0]).days)
    avanco = float(serie["programado"].iloc[-1] - serie["programado"].iloc[0])
    velocidade = avanco / dias if dias > 0 else None

    restante = float(serie["a_programar"].iloc[-1])
    if not velocidade or velocidade <= 0:
        # Programação parada ou andando para trás: projetar data seria inventar
        # um número. A tela diz que não dá para projetar.
        return Evolucao(serie, velocidade, None, None, fim)

    dias_restantes = restante / velocidade
    projetada = serie["snapshot"].iloc[-1] + pd.Timedelta(days=dias_restantes)
    return Evolucao(serie, velocidade, dias_restantes, projetada.normalize(), fim)


def _fim_da_competencia(filtros: rules.Filtros) -> pd.Timestamp | None:
    """Último dia do mês da competência — o prazo que a projeção precisa bater."""
    if filtros.ano is None or filtros.mes is None:
        return None
    inicio = pd.Timestamp(year=filtros.ano, month=filtros.mes, day=1)
    return (inicio + pd.offsets.MonthEnd(1)).normalize()
