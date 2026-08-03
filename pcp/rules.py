"""Motor de regras do PCP.

Camada de domínio: funções puras sobre DataFrames já tipados. Não lê arquivo,
não escreve cache, não sabe que existe Streamlit. É o que permite travar os
indicadores em teste e trocar ingestão ou interface sem tocar em regra.

Toda regra aqui foi obtida por engenharia reversa das fórmulas da aba ANALISE
GERENCIAL e validada contra os valores da planilha (diferença zero nos 8 KPIs).
Ver PLANO_APP_PCP.md §2 e CORRECAO_FLUXO_PRODUTIVO.md.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import pandas as pd

from . import schema
from .schema import A_RECEBER, CORPO, EM_CASA, NAO, SIM
from .transform import normalizar_flag

# Dimensões de quebra e o nome da coluna em cada base.
# Existem porque BASE CPG e BASE MP usam nomes diferentes para o mesmo conceito.
DIMENSOES: dict[str, str] = {
    "familia": "Família",
    "departamento": "Grupo",
    "tipo_produto": "Produto",
    "toc": "TOC",
    "quinzena": "Quinzena",
}


@dataclass(frozen=True)
class Filtros:
    """Recorte da análise. `None` = sem filtro naquela dimensão."""

    mes: int | None = None
    ano: int | None = None
    familia: str | None = None
    departamento: str | None = None
    tipo_produto: str | None = None
    toc: str | None = None
    quinzena: str | None = None

    def dimensoes_ativas(self) -> dict[str, str]:
        return {
            k: v
            for k, v in asdict(self).items()
            if k in DIMENSOES and v not in (None, "", "Todos", "Todas")
        }


@dataclass(frozen=True)
class KPIs:
    """Os 8 indicadores do painel principal."""

    carteira_total: float
    programado: float
    a_programar: float
    sem_avi: float
    sem_mp: float
    sem_prototipo: float
    mp_prot_sem_avi: float
    disponivel_para_programar: float

    @property
    def pct_programado(self) -> float:
        return self.programado / self.carteira_total if self.carteira_total else 0.0

    def pct_do_saldo(self, valor: float) -> float:
        """Peso de um detrator sobre o saldo pendente (base dos painéis)."""
        return valor / self.a_programar if self.a_programar else 0.0

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _mascara(df: pd.DataFrame, filtros: Filtros, *, com_ano: bool) -> pd.Series:
    """Máscara booleana do recorte, tolerante a coluna ausente."""
    mask = pd.Series(True, index=df.index)
    if filtros.mes is not None and "mes" in df.columns:
        mask &= df["mes"] == filtros.mes
    if com_ano and filtros.ano is not None and "ano" in df.columns:
        mask &= df["ano"] == filtros.ano
    for dim, valor in filtros.dimensoes_ativas().items():
        if dim in df.columns:
            mask &= df[dim].astype(str).str.strip() == str(valor).strip()
    return mask


# --------------------------------------------------------------------------
# Volumes — origem BASE CPG
# --------------------------------------------------------------------------


def carteira(cpg: pd.DataFrame, filtros: Filtros) -> tuple[float, float, float]:
    """(carteira_total, programado, a_programar).

    `Programado` é derivado (`carteira - a_programar`) e não lido da coluna
    'Programado' da base — é assim que a planilha calcula, e as duas divergem:
    a coluna traz 528.179 contra 494.563 do derivado, porque inclui produção
    de outras competências.
    """
    m = _mascara(cpg, filtros, com_ano=True)
    total = float(cpg.loc[m, "carteira_total"].sum())
    pendente = float(cpg.loc[m, "a_programar"].sum())
    return total, total - pendente, pendente


# --------------------------------------------------------------------------
# Detratores — origem BASE MP
# --------------------------------------------------------------------------


def _base_mp(mp: pd.DataFrame, filtros: Filtros) -> pd.Series:
    """Recorte comum a todos os detratores.

    O corte `PARTE_PECA = CORPO` é obrigatório: sem ele há dupla contagem,
    porque a base tem uma linha por componente (CORPO, COMPLEMENTO,
    COMPLEMENTO II, AVIAMENTO) do mesmo pedido.
    """
    return _mascara(mp, filtros, com_ano=False) & (mp["parte_peca"] == CORPO)


def detratores(mp: pd.DataFrame, filtros: Filtros) -> dict[str, float]:
    base = _base_mp(mp, filtros)
    saldo = mp["saldo_a_programar"]

    def soma(cond: pd.Series) -> float:
        return float(saldo[base & cond].sum())

    prototipo_ok = mp["prototipo"] == SIM
    return {
        "sem_avi": soma(mp["status_avi"] == NAO),
        "sem_mp": soma(mp["situacao_mp"] == A_RECEBER),
        "sem_prototipo": soma(mp["prototipo"] == NAO),
        "mp_prot_sem_avi": soma(
            prototipo_ok & (mp["full_kit_tecido"] == SIM) & (mp["status_avi"] == NAO)
        ),
        "disponivel_para_programar": soma(
            prototipo_ok & (mp["situacao_mp"] == EM_CASA) & (mp["programar"] == SIM)
        ),
    }




def kpis(cpg: pd.DataFrame, mp: pd.DataFrame, filtros: Filtros) -> KPIs:
    total, programado, pendente = carteira(cpg, filtros)
    return KPIs(
        carteira_total=total,
        programado=programado,
        a_programar=pendente,
        **detratores(mp, filtros),
    )


def kpis_por_dimensao(
    cpg: pd.DataFrame, mp: pd.DataFrame, filtros: Filtros, dimensao: str
) -> pd.DataFrame:
    """Uma linha de KPIs por valor da dimensão (Família, TOC, Grupo, Produto).

    Os valores vêm dos dados, nunca de lista fixa no código — Tear, Malha e Polo
    têm catálogo de família próprio.
    """
    if dimensao not in DIMENSOES:
        raise ValueError(
            f"Dimensão '{dimensao}' inválida. Use uma de: {', '.join(DIMENSOES)}."
        )

    valores = sorted(
        {
            str(v).strip()
            for df in (cpg, mp)
            if dimensao in df.columns
            for v in df.loc[_mascara(df, filtros, com_ano=df is cpg), dimensao].unique()
            if str(v).strip()
        }
    )

    linhas = []
    for valor in valores:
        recorte = Filtros(**{**asdict(filtros), dimensao: valor})
        k = kpis(cpg, mp, recorte)
        linhas.append({DIMENSOES[dimensao]: valor, **k.as_dict(), "pct_programado": k.pct_programado})
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------
# Fluxo produtivo — bloco corrigido (ver CORRECAO_FLUXO_PRODUTIVO.md)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FluxoProdutivo:
    """WIP por etapa e saídas do fluxo.

    Substitui o bloco AH:AY da planilha, que retorna zero em 100% das células
    por ler colunas erradas da BASE CPG.
    """

    etapas: dict[str, float]
    aguardando_entrada: float
    em_processo: float
    embalado: float
    faturado: float
    recebido_cd: float
    carteira_total: float
    tempo_total: float
    programado: float

    @property
    def wip_total(self) -> float:
        return sum(self.etapas.values())

    @property
    def gargalo(self) -> tuple[str, float] | None:
        """Etapa com maior WIP — a informação que a planilha nunca mostrou."""
        if not self.etapas:
            return None
        nome, valor = max(self.etapas.items(), key=lambda kv: kv[1])
        return schema.ROTULO_ETAPA.get(nome, nome), valor

    @property
    def evolucao(self) -> float:
        return self.faturado / self.carteira_total if self.carteira_total else 0.0

    @property
    def conferencia_programado(self) -> float:
        """`Programado − (Processo + Embalado)`.

        É a identidade que expôs o defeito da coluna 'Programado' duplicada
        (ver CORRECAO_FLUXO_PRODUTIVO.md §5b) e que fecha com zero na
        competência corrente. Em competência já encerrada ela **não** fecha, e
        isso não é erro: o resíduo é a peça que saiu do fluxo (tipicamente o
        Faturado, que ali já deixou o Embalado). Quem interpreta o resíduo é a
        tela — aqui ele é só o número.
        """
        return self.programado - (self.em_processo + self.embalado)

    def funil(self) -> list[tuple[str, float, int]]:
        """Estágios do fluxo com o nível hierárquico de cada um.

        Não é uma cascata linear: `Programado` se divide em **dois ramos**
        paralelos — o que está em processo e o que já foi embalado. Desenhar
        tudo numa coluna só produzia a leitura errada de que 'Embalado' sai de
        'Em Processo', e em competência encerrada o Embalado aparecia maior que
        o estágio anterior.
        """
        return [
            ("Carteira Ajustada", self.carteira_total, 0),
            ("Programado", self.programado, 1),
            ("Em Processo", self.em_processo, 2),
            ("Nas etapas (WIP)", self.wip_total, 3),
            ("Aguardando entrada", self.aguardando_entrada, 3),
            ("Embalado", self.embalado, 2),
            ("Faturado", self.faturado, 3),
            ("Recebido CD", self.recebido_cd, 4),
        ]

    def como_tabela(self) -> pd.DataFrame:
        wip = self.wip_total
        return pd.DataFrame(
            [
                {
                    "Etapa": schema.ROTULO_ETAPA.get(k, k),
                    "Peças": v,
                    "% do WIP": v / wip if wip else 0.0,
                }
                for k, v in self.etapas.items()
            ]
        )


def fluxo_produtivo(cpg: pd.DataFrame, filtros: Filtros) -> FluxoProdutivo:
    m = _mascara(cpg, filtros, com_ano=True)
    recorte = cpg.loc[m]

    etapas = {
        c.canonical: float(recorte[c.canonical].sum())
        for c in schema.ETAPAS_CPG
        if c.canonical in recorte.columns
    }
    etapas = {k: v for k, v in etapas.items() if v}

    def total(coluna: str) -> float:
        return float(recorte[coluna].sum()) if coluna in recorte.columns else 0.0

    em_processo = total("processo")
    return FluxoProdutivo(
        etapas=etapas,
        # Peças programadas que ainda não entraram em nenhuma etapa.
        # Indicador novo: não existia na planilha.
        aguardando_entrada=em_processo - sum(etapas.values()),
        em_processo=em_processo,
        embalado=total("embalado"),
        faturado=total("faturado"),
        recebido_cd=total("recebido_cd"),
        carteira_total=total("carteira_total"),
        tempo_total=total("tempo_total"),
        programado=total("programado"),
    )


# --------------------------------------------------------------------------
# M5 · Full Kit & Matéria-Prima — origem BASE MP
# --------------------------------------------------------------------------

# Aderência da previsão de MP, como o SAP devolve (já sem acento pela
# normalização de flag). Qualquer outro valor cai em "sem previsão".
ADERENTE = "ADERENTE"
NAO_ADERENTE = "NAO ADERENTE"

# 'numero - quantidade - dd/mm/aaaa' — formato de 'FULL KIT SAP..Pedidos Compras'.
# A data pode vir vazia (pedido sem previsão confirmada), por isso é opcional.
_PEDIDO_COMPRA = re.compile(
    r"^\s*(?P<numero>\d+)\s*-\s*(?P<qtd>[\d.,]+)\s*-\s*(?P<data>[\d/]*)\s*$"
)


@dataclass(frozen=True)
class FullKit:
    """Situação de matéria-prima do saldo pendente, por componente.

    O corte é o mesmo dos detratores (linhas CORPO): é o que a planilha usa e
    o que evita contar a mesma peça uma vez por componente do pedido.
    """

    itens: pd.DataFrame
    saldo_pendente: float
    bloqueado: float          # saldo com MP 'A Receber'
    liberado: float           # saldo com MP 'Em Casa'
    com_pedido: float         # do bloqueado, o que já tem pedido de compra
    aderente: float           # do bloqueado, o que o SAP marca como aderente
    nao_aderente: float

    @property
    def sem_pedido(self) -> float:
        """Bloqueado sem pedido de compra — o pior caso: não há nada a caminho."""
        return self.bloqueado - self.com_pedido

    @property
    def pct_bloqueado(self) -> float:
        return self.bloqueado / self.saldo_pendente if self.saldo_pendente else 0.0


def _texto(df: pd.DataFrame, coluna: str) -> pd.Series:
    """Coluna de texto tolerante a ausência — multiunidade pode não exportar."""
    if coluna in df.columns:
        return df[coluna].fillna("").astype(str).str.strip()
    return pd.Series("", index=df.index, dtype="object")


def _numerica(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna in df.columns:
        return df[coluna].fillna(0.0)
    return pd.Series(0.0, index=df.index, dtype="float64")


def pedido_de_compra(texto: str) -> dict[str, object] | None:
    """'4700033544 - 10000 - 10/08/2026' -> numero, quantidade e previsão.

    Devolve `None` quando a célula está vazia ou fora do padrão — nunca inventa
    pedido. Uma linha da base real traz '4700034062 - 26,5 -' (sem data): o
    pedido existe, a previsão não, e é assim que aparece na tela.
    """
    casou = _PEDIDO_COMPRA.match(str(texto or ""))
    if not casou:
        return None
    quantidade = pd.to_numeric(casou["qtd"].replace(".", "").replace(",", "."), errors="coerce")
    data = pd.to_datetime(casou["data"], dayfirst=True, errors="coerce") if casou["data"] else pd.NaT
    return {
        "numero": casou["numero"],
        "quantidade": float(quantidade) if pd.notna(quantidade) else 0.0,
        "previsao": data,
    }


def full_kit(mp: pd.DataFrame, filtros: Filtros) -> FullKit:
    """Ranking de componentes que travam a programação por falta de MP."""
    base = _base_mp(mp, filtros)
    recorte = mp.loc[base].copy()

    saldo = recorte["saldo_a_programar"]
    bloqueio = recorte["situacao_mp"] == A_RECEBER
    status = normalizar_flag(_texto(recorte, "status_prev_mp"))
    pedidos = _texto(recorte, "pedidos_compras")
    tem_pedido = pedidos != ""

    recorte = recorte.assign(
        _saldo_bloqueado=saldo.where(bloqueio, 0.0),
        _componente=_texto(recorte, "componente").replace("", "(sem componente)"),
        _descricao=_texto(recorte, "descricao_material"),
        _tipo=_texto(recorte, "tipo_mp"),
        _status=status,
        # Texto que o PCP escreve à mão explicando a trava ('SEM MP AGENDADO
        # 31/07', 'AVI OFCT'). Vale mais na tela que qualquer classificação
        # nossa: é a leitura de quem acompanha o fornecedor.
        _analise=_texto(recorte, "analise_mp"),
        _pedidos=pedidos,
        _estoque=_numerica(recorte, "estoque_disponivel"),
        _reserva=_numerica(recorte, "reserva"),
        _disponibilidade=_numerica(recorte, "disponibilidade_mp"),
    )

    return FullKit(
        itens=_itens_full_kit(recorte),
        saldo_pendente=float(saldo.sum()),
        bloqueado=float(saldo[bloqueio].sum()),
        liberado=float(saldo[recorte["situacao_mp"] == EM_CASA].sum()),
        com_pedido=float(saldo[bloqueio & tem_pedido].sum()),
        aderente=float(saldo[bloqueio & (status == ADERENTE)].sum()),
        nao_aderente=float(saldo[bloqueio & (status == NAO_ADERENTE)].sum()),
    )


def _itens_full_kit(recorte: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por componente, ordenada pelo saldo que ele trava.

    `Estoque Geral Disponível` é atributo do componente e se repete em todas as
    linhas dele — por isso `max`, não `sum`, que multiplicaria o estoque pelo
    número de referências que o usam. `Reserva` é por linha e soma.
    """
    if recorte.empty:
        return pd.DataFrame(
            columns=["componente", "descricao", "tipo", "saldo_bloqueado", "saldo_total",
                     "estoque", "reserva", "disponibilidade", "status", "analise",
                     "pedidos", "previsao"]
        )

    agrupado = recorte.groupby("_componente", dropna=False)
    itens = pd.DataFrame(
        {
            "descricao": agrupado["_descricao"].agg(_primeiro_preenchido),
            "tipo": agrupado["_tipo"].agg(_primeiro_preenchido),
            "saldo_bloqueado": agrupado["_saldo_bloqueado"].sum(),
            "saldo_total": agrupado["saldo_a_programar"].sum(),
            "estoque": agrupado["_estoque"].max(),
            "reserva": agrupado["_reserva"].sum(),
            "disponibilidade": agrupado["_disponibilidade"].max(),
            "status": agrupado["_status"].agg(_primeiro_preenchido),
            "analise": agrupado["_analise"].agg(_primeiro_preenchido),
            "pedidos": agrupado["_pedidos"].agg(
                lambda s: sorted({v for v in s if v})
            ),
        }
    ).reset_index(names="componente")

    itens["previsao"] = itens["pedidos"].map(_previsao_mais_proxima)
    return itens.sort_values(
        ["saldo_bloqueado", "saldo_total"], ascending=False
    ).reset_index(drop=True)


def _primeiro_preenchido(serie: pd.Series) -> str:
    for valor in serie:
        if str(valor).strip():
            return str(valor).strip()
    return ""


def _previsao_mais_proxima(pedidos: list[str]) -> pd.Timestamp:
    """Data em que o primeiro pedido do componente chega — o que destrava antes."""
    datas = [
        p["previsao"]
        for p in (pedido_de_compra(t) for t in pedidos)
        if p and pd.notna(p["previsao"])
    ]
    return min(datas) if datas else pd.NaT


@dataclass(frozen=True)
class Simulacao:
    """Resultado de 'e se a MP destes componentes chegasse hoje?'."""

    componentes: list[str]
    disponivel_hoje: float
    disponivel_depois: float
    saldo_alvo: float
    motivos: dict[str, float]

    @property
    def ganho(self) -> float:
        return self.disponivel_depois - self.disponivel_hoje

    @property
    def travado_por_outros(self) -> float:
        """Saldo do componente que a chegada da MP **não** libera."""
        return self.saldo_alvo - self.ganho


def simular_chegada(
    mp: pd.DataFrame, filtros: Filtros, componentes: list[str]
) -> Simulacao:
    """Responde: *se o full kit do componente X chegar, libera quantas peças?*

    A simulação troca apenas `Situação em MP` para 'Em Casa' e reaplica a regra
    real de disponibilidade — protótipo e liberação para programar continuam
    valendo. Por isso o ganho é quase sempre menor que o saldo bloqueado do
    componente, e às vezes zero: MP não é a única trava. Os `motivos` dizem
    qual é a outra, para a resposta não parecer defeito de conta.
    """
    atual = detratores(mp, filtros)["disponivel_para_programar"]
    if not componentes:
        return Simulacao(componentes, atual, atual, 0.0, {})

    alvo = (
        _base_mp(mp, filtros)
        & _texto(mp, "componente").isin(componentes)
        & (mp["situacao_mp"] == A_RECEBER)
    )
    simulado = mp.copy()
    simulado.loc[alvo, "situacao_mp"] = EM_CASA
    depois = detratores(simulado, filtros)["disponivel_para_programar"]

    saldo = mp["saldo_a_programar"]
    motivos = {
        "Sem protótipo aprovado": float(saldo[alvo & (mp["prototipo"] != SIM)].sum()),
        "Não liberado para programar": float(saldo[alvo & (mp["programar"] != SIM)].sum()),
    }
    return Simulacao(
        componentes=componentes,
        disponivel_hoje=atual,
        disponivel_depois=depois,
        saldo_alvo=float(saldo[alvo].sum()),
        motivos={k: v for k, v in motivos.items() if v},
    )


# --------------------------------------------------------------------------
# M6 · Prazos & Deadline — origem BASE CPG
# --------------------------------------------------------------------------

# Faixas de urgência sobre a data recomendada de liberação, em dias corridos a
# partir do snapshot da base. O limite superior é inclusivo.
FAIXAS_PRAZO: tuple[tuple[str, int | None], ...] = (
    ("Estourado", -1),
    ("Crítico · até 7 dias", 7),
    ("Atenção · 8 a 15 dias", 15),
    ("Programável · 16 a 30 dias", 30),
    ("Folga · acima de 30 dias", None),
)

SEM_DATA = "Sem data de liberação"


@dataclass(frozen=True)
class Prazos:
    """Saldo pendente distribuído por urgência de liberação.

    A régua é `Data Lib Recomendada` contra a **data do snapshot**, não contra
    `Data de Recomendação` da BASE MP como sugeria o plano: conferindo o dado,
    as duas colunas carregam a mesma data para o mesmo material (534 de 1.029
    linhas idênticas, o resto explicado por material com mais de um pedido).
    Comparar uma com a outra não mede prazo nenhum — o que decide é quanto falta
    de hoje até a data recomendada.
    """

    referencia: pd.Timestamp
    faixas: dict[str, float]
    itens: pd.DataFrame
    estourado: float
    dias_atraso_max: float

    @property
    def total(self) -> float:
        return sum(self.faixas.values())

    @property
    def no_prazo(self) -> float:
        return self.total - self.estourado - self.faixas.get(SEM_DATA, 0.0)

    @property
    def pct_estourado(self) -> float:
        return self.estourado / self.total if self.total else 0.0


def _faixa_de(dias: float) -> str:
    if pd.isna(dias):
        return SEM_DATA
    for rotulo, limite in FAIXAS_PRAZO:
        if limite is None or dias <= limite:
            return rotulo
    return FAIXAS_PRAZO[-1][0]


def prazos(
    cpg: pd.DataFrame, filtros: Filtros, referencia: pd.Timestamp | None
) -> Prazos:
    """Semáforo de deadline do saldo **ainda não programado**.

    O que já foi programado sai da conta de propósito: prazo estourado só é
    acionável enquanto existe peça a programar.
    """
    referencia = pd.Timestamp(referencia).normalize() if referencia is not None else pd.Timestamp.today().normalize()

    m = _mascara(cpg, filtros, com_ano=True) & (cpg["a_programar"] > 0)
    recorte = cpg.loc[m].copy()

    # Recorte vazio traz a coluna de data como float64 (não há valor para
    # inferir dtype) e `.dt` explode. Converter antes cobre os dois casos sem
    # ramificar por tamanho.
    datas = pd.to_datetime(
        recorte.get("data_lib_recomendada", pd.Series(pd.NaT, index=recorte.index)),
        errors="coerce",
    )
    recorte["dias"] = (datas.dt.normalize() - referencia).dt.days
    recorte["faixa"] = recorte["dias"].map(_faixa_de)

    faixas = {rotulo: 0.0 for rotulo, _ in FAIXAS_PRAZO}
    faixas[SEM_DATA] = 0.0
    for rotulo, valor in recorte.groupby("faixa")["a_programar"].sum().items():
        faixas[rotulo] = float(valor)

    atrasadas = recorte[recorte["dias"] < 0]
    return Prazos(
        referencia=referencia,
        faixas=faixas,
        itens=_itens_prazo(recorte),
        estourado=float(atrasadas["a_programar"].sum()),
        dias_atraso_max=float(-atrasadas["dias"].min()) if not atrasadas.empty else 0.0,
    )


_COLUNAS_PRAZO = ("pedido", "familia", "departamento", "toc", "data_lib_recomendada", "entrega_cd")


def _itens_prazo(recorte: pd.DataFrame) -> pd.DataFrame:
    """Pedidos pendentes ordenados do mais atrasado para o mais folgado."""
    colunas = [c for c in _COLUNAS_PRAZO if c in recorte.columns]
    itens = recorte[[*colunas, "a_programar", "carteira_total", "dias", "faixa"]].copy()
    return itens.sort_values(["dias", "a_programar"], ascending=[True, False]).reset_index(drop=True)


# --------------------------------------------------------------------------
# M10 · Programação semanal — origem BASE MP
# --------------------------------------------------------------------------

# A régua é `Data de Recomendação` da BASE MP, e não `Data Lib Recomendada` da
# BASE CPG como no M6: quem responde "isto pode entrar na programação" é a linha
# de MP (protótipo + full kit + liberação), e é nela que está a data. Usar a
# coluna da CPG obrigaria a cruzar as duas bases por material só para reencontrar
# a mesma data (ver `Prazos`, que já mostrou que as duas coincidem).
#
# A semana é de segunda a domingo — a semana da fábrica, não a ISO com virada
# em quinta.
VENCIDA = "Vencida"
ESTA_SEMANA = "Esta semana"
PROXIMA_SEMANA = "Próxima semana"
FUTURA = "Futura"
SEM_SEMANA = "Sem data recomendada"

_METRICAS_SEMANA = ("saldo", "disponivel", "sem_mp", "sem_prototipo", "sem_avi")

_COLUNAS_SEMANA = (
    "inicio", "fim", "semana", "periodo", "situacao",
    *_METRICAS_SEMANA, "travado", "pct_disponivel",
)

_COLUNAS_ITEM = (
    "referencia", "material", "descricao_material", "familia", "departamento",
    "toc", "quinzena", "componente", "recomendado", "semana", "periodo",
    "situacao", "saldo_a_programar",
)


@dataclass(frozen=True)
class ProgramacaoSemanal:
    """O saldo pendente distribuído pela semana em que deveria ser programado.

    Responde a pergunta que o painel de detratores não responde: *o disponível
    para programar é de hoje ou é de daqui a três semanas?* Os 16.674 do KPI
    não são um lote único — parte já venceu a janela e parte só abre em agosto,
    e programar tudo junto é o que estoura a capacidade de uma semana e deixa a
    seguinte vazia.

    `semanas` traz uma linha por semana (disponível e travas); `itens` traz o
    detalhe do que está **disponível**, que é o que se leva para a reunião.
    """

    referencia: pd.Timestamp
    semanas: pd.DataFrame
    itens: pd.DataFrame

    @property
    def saldo(self) -> float:
        return float(self.semanas["saldo"].sum()) if not self.semanas.empty else 0.0

    @property
    def disponivel(self) -> float:
        return float(self.semanas["disponivel"].sum()) if not self.semanas.empty else 0.0

    @property
    def travado(self) -> float:
        return self.saldo - self.disponivel

    @property
    def pct_disponivel(self) -> float:
        return self.disponivel / self.saldo if self.saldo else 0.0

    def disponivel_em(self, situacao: str) -> float:
        if self.semanas.empty:
            return 0.0
        return float(
            self.semanas.loc[self.semanas["situacao"] == situacao, "disponivel"].sum()
        )

    @property
    def vencido(self) -> float:
        """Disponível cuja semana de programação já passou.

        Não é atraso de entrega (isso é o M6): é peça liberada, sem trava
        nenhuma, que ficou fora do programa — capacidade perdida.
        """
        return self.disponivel_em(VENCIDA)

    @property
    def nesta_semana(self) -> float:
        return self.disponivel_em(ESTA_SEMANA)

    @property
    def proxima_semana(self) -> float:
        return self.disponivel_em(PROXIMA_SEMANA)

    @property
    def sem_data(self) -> float:
        return self.disponivel_em(SEM_SEMANA)

    @property
    def semanas_com_disponivel(self) -> int:
        if self.semanas.empty:
            return 0
        return int((self.semanas["disponivel"] > 0).sum())

    @property
    def pico(self) -> tuple[str, float] | None:
        """Semana que concentra mais peças liberadas — onde a capacidade aperta."""
        com_data = self.semanas[
            (self.semanas["situacao"] != SEM_SEMANA) & (self.semanas["disponivel"] > 0)
        ]
        if com_data.empty:
            return None
        linha = com_data.loc[com_data["disponivel"].idxmax()]
        return str(linha["periodo"]), float(linha["disponivel"])


def _inicio_da_semana(dia: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(dia).normalize() - pd.Timedelta(days=int(pd.Timestamp(dia).weekday()))


def _situacao_da_semana(inicio: pd.Timestamp, semana_ref: pd.Timestamp) -> str:
    if pd.isna(inicio):
        return SEM_SEMANA
    if inicio < semana_ref:
        return VENCIDA
    if inicio == semana_ref:
        return ESTA_SEMANA
    if inicio == semana_ref + pd.Timedelta(days=7):
        return PROXIMA_SEMANA
    return FUTURA


def programacao_semanal(
    mp: pd.DataFrame, filtros: Filtros, referencia: pd.Timestamp | None
) -> ProgramacaoSemanal:
    """Agenda de programação por semana, com o disponível separado das travas.

    O corte é o mesmo dos detratores (linhas CORPO) e a regra de disponibilidade
    é a mesma de `detratores`: sem isso, a soma das semanas não fecharia com o
    KPI 'Disponível para Programar' do painel principal e a tela viraria um
    terceiro número para a mesma pergunta.
    """
    referencia = (
        pd.Timestamp(referencia).normalize()
        if referencia is not None
        else pd.Timestamp.today().normalize()
    )
    semana_ref = _inicio_da_semana(referencia)

    recorte = mp.loc[_base_mp(mp, filtros)].copy()

    # Mesma precaução do M6: recorte vazio traz a coluna de data como float64 e
    # `.dt` explodiria. `to_datetime` normaliza os dois casos sem ramificar.
    datas = pd.to_datetime(
        recorte.get("data_recomendacao", pd.Series(pd.NaT, index=recorte.index)),
        errors="coerce",
    )
    saldo = recorte["saldo_a_programar"]
    liberado = (
        (recorte["prototipo"] == SIM)
        & (recorte["situacao_mp"] == EM_CASA)
        & (recorte["programar"] == SIM)
    )

    recorte = recorte.assign(
        _inicio=datas.dt.normalize() - pd.to_timedelta(datas.dt.weekday, unit="D"),
        _recomendado=datas,
        _saldo=saldo,
        _disponivel=saldo.where(liberado, 0.0),
        # Travas somadas em separado, não particionadas: a mesma peça pode estar
        # sem MP **e** sem AVI, e forçar uma trava única esconderia a segunda.
        _sem_mp=saldo.where(recorte["situacao_mp"] == A_RECEBER, 0.0),
        _sem_prototipo=saldo.where(recorte["prototipo"] == NAO, 0.0),
        _sem_avi=saldo.where(recorte["status_avi"] == NAO, 0.0),
    )

    return ProgramacaoSemanal(
        referencia=referencia,
        semanas=_semanas(recorte, semana_ref),
        itens=_itens_disponiveis(recorte[liberado], semana_ref),
    )


def _semanas(recorte: pd.DataFrame, semana_ref: pd.Timestamp) -> pd.DataFrame:
    """Uma linha por semana, da mais antiga para a mais distante.

    `dropna=False` no agrupamento é o que mantém a linha 'Sem data recomendada':
    descartá-la faria a soma das semanas ficar menor que o KPI, sem dizer onde
    foi parar a diferença.
    """
    if recorte.empty:
        return pd.DataFrame(columns=list(_COLUNAS_SEMANA))

    metricas = ["_saldo", "_disponivel", "_sem_mp", "_sem_prototipo", "_sem_avi"]
    tabela = (
        recorte.groupby("_inicio", dropna=False)[metricas]
        .sum()
        .reset_index()
        .rename(columns={f"_{nome}": nome for nome in ("inicio", *_METRICAS_SEMANA)})
    )

    tabela["fim"] = tabela["inicio"] + pd.Timedelta(days=6)
    tabela["situacao"] = tabela["inicio"].map(
        lambda inicio: _situacao_da_semana(inicio, semana_ref)
    )
    tabela["semana"] = tabela["inicio"].map(_rotulo_semana)
    tabela["periodo"] = [
        _rotulo_periodo(inicio, fim)
        for inicio, fim in zip(tabela["inicio"], tabela["fim"], strict=True)
    ]
    tabela["travado"] = tabela["saldo"] - tabela["disponivel"]
    tabela["pct_disponivel"] = (tabela["disponivel"] / tabela["saldo"]).where(
        tabela["saldo"] > 0, 0.0
    )
    return (
        tabela.sort_values("inicio", na_position="last")
        .reset_index(drop=True)[list(_COLUNAS_SEMANA)]
    )


def _rotulo_semana(inicio: pd.Timestamp) -> str:
    """'S31' — a semana do calendário, do jeito que a fábrica chama."""
    if pd.isna(inicio):
        return "—"
    return f"S{pd.Timestamp(inicio).isocalendar().week:02d}"


def _rotulo_periodo(inicio: pd.Timestamp, fim: pd.Timestamp) -> str:
    if pd.isna(inicio):
        return SEM_SEMANA
    return f"{pd.Timestamp(inicio):%d/%m} a {pd.Timestamp(fim):%d/%m}"


def _itens_disponiveis(recorte: pd.DataFrame, semana_ref: pd.Timestamp) -> pd.DataFrame:
    """O que está liberado, da semana mais atrasada para a mais folgada.

    Só o disponível entra: o que está travado tem painel próprio (Full Kit) e
    misturar os dois devolveria de novo a lista que o PCP hoje filtra na mão.
    """
    if recorte.empty:
        return pd.DataFrame(columns=list(_COLUNAS_ITEM))

    itens = pd.DataFrame(
        {
            coluna: _texto(recorte, coluna)
            for coluna in (
                "referencia", "material", "descricao_material", "familia",
                "departamento", "toc", "quinzena", "componente",
            )
        },
        index=recorte.index,
    )
    itens["recomendado"] = recorte["_recomendado"]
    itens["semana"] = recorte["_inicio"].map(_rotulo_semana)
    itens["periodo"] = [
        _rotulo_periodo(inicio, inicio + pd.Timedelta(days=6))
        for inicio in recorte["_inicio"]
    ]
    itens["situacao"] = recorte["_inicio"].map(
        lambda inicio: _situacao_da_semana(inicio, semana_ref)
    )
    itens["saldo_a_programar"] = recorte["_disponivel"]

    return (
        itens.sort_values(
            ["recomendado", "saldo_a_programar"],
            ascending=[True, False],
            na_position="last",
        )
        .reset_index(drop=True)[list(_COLUNAS_ITEM)]
    )


# --------------------------------------------------------------------------
# Contexto do arquivo carregado
# --------------------------------------------------------------------------


def unidade(cpg: pd.DataFrame) -> str:
    """Unidade produtiva lida do dado, não escolhida em menu.

    Evita o erro de analisar a planilha do Tear com 'Oficina Jeans' selecionado.
    """
    if "fabrica" not in cpg.columns:
        return "Não identificada"
    valores = sorted({v for v in cpg["fabrica"].astype(str).str.strip() if v})
    if not valores:
        return "Não identificada"
    return valores[0] if len(valores) == 1 else " + ".join(valores)


def data_snapshot(cpg: pd.DataFrame) -> pd.Timestamp | None:
    """Data de extração da base — carimbada em todo painel e exportação."""
    if "data_arquivo" not in cpg.columns:
        return None
    validas = cpg["data_arquivo"].dropna()
    return validas.max() if not validas.empty else None


def competencias(cpg: pd.DataFrame) -> list[tuple[int, int]]:
    """(ano, mês) presentes na base, em ordem."""
    if not {"ano", "mes"}.issubset(cpg.columns):
        return []
    pares = cpg[["ano", "mes"]].dropna().drop_duplicates()
    return sorted((int(a), int(m)) for a, m in pares.itertuples(index=False))


def valores_de(df: pd.DataFrame, dimensao: str) -> list[str]:
    """Valores distintos de uma dimensão — derivados do dado, nunca fixos."""
    if dimensao not in df.columns:
        return []
    return sorted({v for v in df[dimensao].astype(str).str.strip() if v})
