"""Contrato de ingestão — quais colunas ler e como tratá-las.

Princípio inegociável: **mapeamento por NOME DE CABEÇALHO, nunca por letra de
coluna**. Foi a referência posicional que quebrou o bloco de fluxo produtivo da
planilha (ver CORRECAO_FLUXO_PRODUTIVO.md): a BASE CPG ganhou 17 colunas antes
do bloco de etapas e mais 6 no meio dele, e as fórmulas `SUMIFS` continuaram
lendo o intervalo antigo — passando a somar 'Bimatéria', 'Carteira Original' e
até campos de texto sob os rótulos 'Corte', 'Customização' e 'Embalado'.

Com mapeamento por nome, inserir coluna na base não quebra nada; e remover ou
renomear uma coluna obrigatória derruba a carga com erro explícito em vez de
devolver zero.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

BASE_CPG = "BASE CPG"
BASE_MP = "BASE MP"


def normalizar_cabecalho(texto: object) -> str:
    """Chave de comparação de cabeçalho: sem acento, minúsculo, sem espaço extra.

    'Situação Full Kit Tecido' e 'SITUACAO  FULL KIT TECIDO' viram a mesma chave.
    """
    s = "" if texto is None else str(texto)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("\n", " ").replace("\r", " ").replace("\xa0", " ")
    return " ".join(s.split()).lower()


@dataclass(frozen=True)
class Coluna:
    """Uma coluna do contrato.

    canonical: nome usado no DataFrame (snake_case, estável para o código).
    header:    cabeçalho esperado na planilha (o que o usuário vê).
    kind:      num | int | text | flag | date
    required:  se False, a ausência é aceita e a coluna nasce vazia.
    aliases:   outros cabeçalhos aceitos para a mesma coluna.
    """

    canonical: str
    header: str
    kind: str = "text"
    required: bool = True
    aliases: tuple[str, ...] = ()
    # Qual ocorrência usar quando o cabeçalho aparece repetido na aba (1 = a
    # primeira). `None` exige que seja único: se houver repetição, a carga falha
    # em vez de escolher sozinha. Ver CabecalhoAmbiguoError.
    ocorrencia: int | None = None

    @property
    def chaves(self) -> list[str]:
        return [normalizar_cabecalho(h) for h in (self.header, *self.aliases)]


# --------------------------------------------------------------------------
# BASE CPG — carteira, volumes e etapas produtivas
# --------------------------------------------------------------------------

# As 16 etapas do fluxo, na ordem real de produção.
#
# required=False de propósito: Tear, Malha e Polo usam a mesma estrutura de
# planilha, mas não necessariamente as mesmas etapas (Malha provavelmente não
# tem Lavanderia nos mesmos moldes). A aplicação exibe as que existirem no
# arquivo e ignora as ausentes — sem quebrar e sem inventar zero.
ETAPAS_CPG: tuple[Coluna, ...] = (
    Coluna("etapa_corte", "Corte", "num", required=False),
    Coluna("etapa_customizacao", "Customização", "num", required=False),
    Coluna("etapa_alfandega", "Alfândega", "num", required=False),
    Coluna("etapa_costura", "Costura", "num", required=False),
    Coluna("etapa_oficina", "Oficina", "num", required=False),
    Coluna("etapa_customizacao_alfandega", "Customização Alfândega", "num", required=False),
    Coluna("etapa_customizacao_pos", "Customização Pós", "num", required=False),
    Coluna("etapa_logistica", "Logística", "num", required=False),
    Coluna("etapa_recebimento", "Recebimento", "num", required=False),
    Coluna("etapa_lavanderia", "Lavanderia", "num", required=False),
    Coluna("etapa_acabamento", "Acabamento", "num", required=False),
    Coluna("etapa_transfer_pos", "Transfer Pós", "num", required=False),
    Coluna("etapa_qualidade", "Qualidade", "num", required=False),
    Coluna("etapa_intertek", "Intertek", "num", required=False),
    Coluna("etapa_alfandega_embalagem", "Alfândega Embalagem", "num", required=False),
    Coluna("etapa_embalagem", "Embalagem", "num", required=False),
)

# Rótulo de exibição de cada etapa, na ordem do fluxo.
ROTULO_ETAPA: dict[str, str] = {c.canonical: c.header for c in ETAPAS_CPG}

COLUNAS_CPG: tuple[Coluna, ...] = (
    # identificação
    Coluna("pedido", "Pedido"),
    Coluna("material", "Material"),
    Coluna("projeto", "Projeto"),
    Coluna("fabrica", "Fábrica"),  # <- unidade produtiva vem daqui, não de menu
    # dimensões de quebra
    Coluna("familia", "FAM"),
    Coluna("familia_tecnica", "Família Técnica", required=False),
    Coluna("desc_familia", "Desc Família", required=False),
    Coluna("produto_detalhado", "Produto Detalhado", required=False),
    Coluna("departamento", "Departamento"),
    Coluna("tipo_produto", "Tipo de Produto"),
    Coluna("toc", "Classe"),
    Coluna("quinzena", "Quinzena"),
    Coluna("status_programacao", "Status Programação", required=False),
    Coluna("cor", "Cor", required=False),
    # tempo
    Coluna("mes", "Mês", "int"),
    Coluna("ano", "Ano", "int"),
    Coluna("data_criacao", "Data de Criação", "date", required=False),
    Coluna("data_lib_recomendada", "Data Lib Recomendada", "date", required=False),
    Coluna("entrega_cd", "Entrega CD", "date", required=False),
    Coluna("data_arquivo", "Data Arquivo", "date", required=False),
    # volumes
    Coluna("carteira_total", "Carteira Ajustada", "num"),
    Coluna("carteira_original", "Carteira Original", "num", required=False),
    Coluna("real_cortado", "Real Cortado", "num", required=False),
    Coluna("a_programar", "A Programar", "num"),
    # A BASE CPG tem DUAS colunas 'Programado': a coluna A é auxiliar
    # (=Carteira Original - Carteira Ajustada) e a do bloco de métricas é a
    # segunda — que é a produção efetivamente programada. Pegar a primeira
    # quebra a identidade `Programado = Processo + Embalado`.
    Coluna("programado", "Programado", "num", ocorrencia=2),
    Coluna("processo", "Processo", "num"),
    Coluna("refugo", "Refugo", "num", required=False),
    Coluna("segunda_qualidade", "2ª Qualidade", "num", required=False),
    Coluna("embalado", "Embalado", "num"),
    Coluna("faturado", "Faturado", "num"),
    Coluna("recebido_cd", "Recebido CD", "num", required=False),
    # carga
    Coluna("tempo_total", "Tempo Total", "num"),
    Coluna("tempo_medio", "Tempo Médio", "num", required=False),
    *ETAPAS_CPG,
)

# --------------------------------------------------------------------------
# BASE MP — matéria-prima, AVI, protótipo e full kit
# --------------------------------------------------------------------------

COLUNAS_MP: tuple[Coluna, ...] = (
    # identificação
    # 'Referência' aparece duas vezes na BASE MP: a coluna A é o dado e a
    # segunda é resultado de PROCV (traz #N/A). Aqui a primeira é a correta.
    Coluna("referencia", "Referência", ocorrencia=1),
    Coluna("material", "Material"),
    Coluna("projeto_plm", "Projeto PLM", required=False),
    Coluna("descricao_material", "Descrição de material", required=False),
    Coluna("cor", "Cor", required=False),
    Coluna("componente", "COMPONENTE", required=False),
    Coluna("mp_sap", "MP Sap", required=False),
    # dimensões de quebra
    Coluna("familia", "FAMILIA"),
    Coluna("departamento", "Departamento"),
    Coluna("tipo_produto", "Produto"),
    Coluna("toc", "TOC"),
    Coluna("quinzena", "Quinzena Entrega", required=False),
    Coluna("parte_peca", "PARTE_PECA", "flag"),
    # tempo
    Coluna("mes", "Mês", "int"),
    Coluna("data_pedido", "Data do Pedido", "date", required=False),
    Coluna("data_recomendacao", "Data de Recomendação", "date", required=False),
    Coluna("criacao_pedido", "Criação do Pedido", "date", required=False),
    # métrica dos detratores
    Coluna("saldo_a_programar", "Saldo a Programar", "num"),
    Coluna("pedido_total", "Pedido Total", "num", required=False),
    Coluna("qtd_programada", "Qtd.Programada", "num", required=False),
    Coluna("saldo_real", "Saldo Real", "num", required=False),
    Coluna("sit_programacao", "Sit. Programação", required=False),
    # flags que definem os detratores
    Coluna("programar", "PROGRAMAR", "flag"),
    Coluna("status_avi", "Status Pedido_AVI", "flag"),
    Coluna("prototipo", "Protótipo", "flag"),
    Coluna("situacao_mp", "Situação em MP", "flag"),
    Coluna("full_kit_tecido", "Situação Full Kit Tecido", "flag"),
    # full kit / estoque
    Coluna("disponibilidade_mp", "Disponibilidade MP x Consumo", "num", required=False),
    Coluna("estoque_disponivel", "Estoque Geral Disponível", "num", required=False),
    Coluna("reserva", "Reserva", "num", required=False),
    Coluna("consumo", "CONSUMO", "num", required=False),
    Coluna("un_medida", "Un. Médida", required=False),
    Coluna("minutos_costura", "Minutos_Costura", "num", required=False),
    Coluna("minutos_total", "Minutos Total", "num", required=False),
    # Compras (M5). Os cabeçalhos vêm do bloco 'FULL KIT SAP' e chegam com
    # ponto duplo no arquivo real ('FULL KIT SAP..Pedidos Compras'); o alias com
    # ponto simples cobre a versão sem o defeito de digitação, que outra unidade
    # pode ter. Todas opcionais: sem elas o painel de Full Kit degrada, o resto
    # da aplicação não sente.
    Coluna("tipo_mp", "Tp. MP", required=False),
    Coluna("analise_mp", "ANALISE MP", required=False),
    Coluna("status_prev_mp", "FULL KIT SAP.Status Prev MP", required=False,
           aliases=("Status Prev MP",)),
    Coluna("pedidos_compras", "FULL KIT SAP..Pedidos Compras", required=False,
           aliases=("FULL KIT SAP.Pedidos Compras", "Pedidos Compras")),
    Coluna("quant_pedidos", "FULL KIT SAP.QUANT. PEDIDOS", "num", required=False,
           aliases=("QUANT. PEDIDOS",)),
)

CONTRATO: dict[str, tuple[Coluna, ...]] = {
    BASE_CPG: COLUNAS_CPG,
    BASE_MP: COLUNAS_MP,
}

# --------------------------------------------------------------------------
# Domínios — valores aceitos nas colunas de flag, já normalizados
# --------------------------------------------------------------------------

SIM = "SIM"
NAO = "NAO"
CORPO = "CORPO"
A_RECEBER = "A RECEBER"
EM_CASA = "EM CASA"

DOMINIOS: dict[str, set[str]] = {
    "programar": {SIM, NAO, ""},
    "status_avi": {SIM, NAO, ""},
    "prototipo": {SIM, NAO, ""},
    "full_kit_tecido": {SIM, NAO, ""},
    "situacao_mp": {A_RECEBER, EM_CASA, ""},
}


def colunas(aba: str) -> tuple[Coluna, ...]:
    return CONTRATO[aba]


def por_canonical(aba: str) -> dict[str, Coluna]:
    return {c.canonical: c for c in CONTRATO[aba]}
