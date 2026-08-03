"""Testes das camadas puras (schema, transform, rules) com dados sintéticos.

Rodam em milissegundos e não dependem da planilha real.
"""

from __future__ import annotations

import zipfile

import pandas as pd
import pytest

from pcp import Carga, ingest, loader, rules, schema, transform
from pcp.cache import CacheParquet
from pcp.errors import (
    ArquivoInvalidoError,
    CabecalhoAmbiguoError,
    ColunaAusenteError,
    TipoInvalidoError,
)
from pcp.transform import Diagnostico
from pcp.ingest import _resolver_cabecalho
from pcp.rules import Filtros
from pcp.schema import normalizar_cabecalho

# --------------------------------------------------------------------------
# schema — casamento de cabeçalho
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Situação Full Kit Tecido", "situacao full kit tecido"),
        ("SITUACAO  FULL  KIT TECIDO", "situacao full kit tecido"),
        ("2ª Qualidade", "2a qualidade"),
        ("A PROGRAMAR\nSEM AVI", "a programar sem avi"),
        ("  Mês  ", "mes"),
    ],
)
def test_normalizacao_de_cabecalho_ignora_acento_caixa_e_espaco(entrada, esperado):
    assert normalizar_cabecalho(entrada) == esperado


def test_cabecalho_e_casado_por_nome_e_nao_por_posicao():
    """Inserir coluna nova antes do bloco não pode deslocar a leitura.

    É exatamente o que quebrou o fluxo produtivo da planilha.
    """
    cabecalho = [(0, "COLUNA NOVA"), (1, "Corte"), (2, "Costura")]
    mapa, _ = _resolver_cabecalho(schema.BASE_CPG, cabecalho + _cpg_minimo(offset=3))
    assert mapa["etapa_corte"] == 1
    assert mapa["etapa_costura"] == 2


def test_coluna_obrigatoria_ausente_derruba_a_carga():
    """Sem isso, o erro voltaria a ser zero silencioso."""
    cabecalho = [(i, h) for i, h in enumerate(["FAM", "Mês", "Ano"])]
    with pytest.raises(ColunaAusenteError) as exc:
        _resolver_cabecalho(schema.BASE_CPG, cabecalho)
    assert "Carteira Ajustada" in str(exc.value)


def test_etapa_ausente_e_aceita_porque_outras_unidades_podem_nao_ter():
    """Malha/Tear/Polo podem não ter todas as etapas do Jeans."""
    mapa, _ = _resolver_cabecalho(schema.BASE_CPG, _cpg_minimo())
    assert "etapa_lavanderia" not in mapa


def test_cabecalho_repetido_sem_regra_no_contrato_derruba_a_carga():
    """Escolher sozinho entre duas colunas de mesmo nome é o bug original."""
    duplicado = _cpg_minimo() + [(99, "Carteira Ajustada")]
    with pytest.raises(CabecalhoAmbiguoError, match="Carteira Ajustada"):
        _resolver_cabecalho(schema.BASE_CPG, duplicado)


def test_contrato_escolhe_a_ocorrencia_declarada():
    """BASE CPG tem 'PROGRAMADO' (auxiliar, col. A) e 'Programado' (métrica)."""
    cabecalho = [(0, "PROGRAMADO")] + _cpg_minimo(offset=1)
    mapa, _ = _resolver_cabecalho(schema.BASE_CPG, cabecalho)
    posicao_metrica = next(
        i for i, h in cabecalho if h == "Programado"
    )
    assert mapa["programado"] == posicao_metrica
    assert mapa["programado"] != 0


def _cpg_minimo(offset: int = 0) -> list[tuple[int, str]]:
    obrigatorias = [c.header for c in schema.COLUNAS_CPG if c.required]
    return [(i + offset, h) for i, h in enumerate(obrigatorias)]


# --------------------------------------------------------------------------
# transform — normalização e tipagem
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("NÃO", "NAO"), ("Não ", "NAO"), ("nao", "NAO"), ("À Receber", "A RECEBER"), ("Em Casa", "EM CASA")],
)
def test_flags_com_acento_e_caixa_diferentes_viram_o_mesmo_valor(entrada, esperado):
    assert transform.normalizar_flag(pd.Series([entrada])).iloc[0] == esperado


def test_numero_em_formato_brasileiro_e_convertido():
    serie = transform._para_numero(pd.Series(["1.234,56", "89", ""]))
    assert serie.iloc[0] == pytest.approx(1234.56)
    assert serie.iloc[1] == 89


def test_coluna_numerica_que_chega_como_texto_derruba_a_carga():
    """Sintoma de referência apontando para a coluna errada."""
    df = pd.DataFrame({"carteira_total": ["SIM", "NÃO", "SIM", "NÃO"]})
    with pytest.raises(TipoInvalidoError) as exc:
        transform.tipar(schema.BASE_CPG, df)
    assert "Carteira Ajustada" in str(exc.value)


def test_erro_de_excel_nao_vira_zero():
    """#N/A e #REF! precisam virar vazio, nunca zero somável."""
    df = pd.DataFrame({"situacao_mp": ["", "Em Casa"]})
    saida = transform.tipar(schema.BASE_MP, df)
    assert saida["situacao_mp"].tolist() == ["", "EM CASA"]


def test_data_aceita_serial_do_excel_e_texto():
    serie = transform._para_data(pd.Series(["46139", "2026-07-31 04:37:04", ""]))
    assert serie.iloc[0] == pd.Timestamp("2026-04-27")  # serial contado de 1899-12-30
    assert serie.iloc[1] == pd.Timestamp("2026-07-31 04:37:04")
    assert pd.isna(serie.iloc[2])


def test_valor_fora_do_dominio_vira_aviso_e_nao_erro():
    diag = transform.Diagnostico()
    transform.tipar(schema.BASE_MP, pd.DataFrame({"prototipo": ["SIM", "TALVEZ"]}), diag)
    assert "prototipo" in diag.fora_de_dominio
    assert not diag.ok


# --------------------------------------------------------------------------
# rules — motor de regras
# --------------------------------------------------------------------------


@pytest.fixture
def cpg() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mes": pd.array([9, 9, 8], dtype="Int64"),
            "ano": pd.array([2026, 2026, 2026], dtype="Int64"),
            "familia": ["101", "103", "101"],
            "departamento": ["INFANTIL", "FEMININO", "INFANTIL"],
            "tipo_produto": ["NOS", "PROGRAMA", "NOS"],
            "toc": ["MTA", "MTO", "MTA"],
            "quinzena": ["1ª Quinzena", "2ª Quinzena", "1ª Quinzena"],
            "carteira_total": [1000.0, 500.0, 999.0],
            "a_programar": [200.0, 100.0, 50.0],
            "processo": [700.0, 300.0, 0.0],
            "embalado": [50.0, 20.0, 0.0],
            "faturado": [10.0, 5.0, 0.0],
            "recebido_cd": [10.0, 5.0, 0.0],
            "tempo_total": [100.0, 50.0, 0.0],
            "programado": [750.0, 320.0, 0.0],
            "etapa_corte": [400.0, 100.0, 0.0],
            "etapa_oficina": [200.0, 150.0, 0.0],
            "fabrica": ["Oficinas Jeans"] * 3,
        }
    )


@pytest.fixture
def mp() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mes": pd.array([9, 9, 9, 9], dtype="Int64"),
            "familia": ["101", "101", "103", "101"],
            "departamento": ["INFANTIL", "INFANTIL", "FEMININO", "INFANTIL"],
            "tipo_produto": ["NOS", "NOS", "PROGRAMA", "NOS"],
            "toc": ["MTA", "MTA", "MTO", "MTA"],
            "quinzena": ["1ª Quinzena"] * 4,
            # a 4ª linha é COMPLEMENTO do mesmo pedido da 1ª: precisa ser excluída
            "parte_peca": ["CORPO", "CORPO", "CORPO", "COMPLEMENTO"],
            "saldo_a_programar": [100.0, 60.0, 40.0, 999.0],
            "status_avi": ["NAO", "SIM", "NAO", "NAO"],
            "situacao_mp": ["A RECEBER", "EM CASA", "EM CASA", "A RECEBER"],
            "prototipo": ["SIM", "SIM", "NAO", "SIM"],
            "full_kit_tecido": ["SIM", "SIM", "NAO", "SIM"],
            "programar": ["NAO", "SIM", "SIM", "SIM"],
        }
    )


def test_carteira_programado_e_derivado_e_nao_lido_da_coluna(cpg):
    total, programado, pendente = rules.carteira(cpg, Filtros(mes=9, ano=2026))
    assert (total, pendente) == (1500.0, 300.0)
    # a coluna 'programado' soma 1070; o KPI correto é carteira - a_programar
    assert programado == 1200.0


def test_filtro_de_ano_separa_competencias(cpg):
    total, _, _ = rules.carteira(cpg, Filtros(mes=9, ano=2025))
    assert total == 0.0


def test_detrator_ignora_componente_para_nao_contar_em_dobro(mp):
    """Sem o corte PARTE_PECA=CORPO, 'sem_avi' viraria 1.139 em vez de 140."""
    d = rules.detratores(mp, Filtros(mes=9))
    assert d["sem_avi"] == 140.0


def test_cada_detrator_usa_sua_propria_regra(mp):
    d = rules.detratores(mp, Filtros(mes=9))
    assert d["sem_mp"] == 100.0
    assert d["sem_prototipo"] == 40.0
    assert d["mp_prot_sem_avi"] == 100.0
    assert d["disponivel_para_programar"] == 60.0


def test_pct_programado_nao_estoura_com_carteira_zero():
    vazio = rules.KPIs(0, 0, 0, 0, 0, 0, 0, 0)
    assert vazio.pct_programado == 0.0
    assert vazio.pct_do_saldo(10) == 0.0


def test_kpis_respeitam_filtro_de_dimensao(cpg, mp):
    k = rules.kpis(cpg, mp, Filtros(mes=9, ano=2026, toc="MTO"))
    assert k.carteira_total == 500.0
    assert k.sem_avi == 40.0


def test_quebra_por_dimensao_deriva_valores_do_dado(cpg, mp):
    tabela = rules.kpis_por_dimensao(cpg, mp, Filtros(mes=9, ano=2026), "toc")
    assert set(tabela["TOC"]) == {"MTA", "MTO"}
    assert tabela["carteira_total"].sum() == 1500.0


def test_dimensao_invalida_falha_explicitamente(cpg, mp):
    with pytest.raises(ValueError, match="inválida"):
        rules.kpis_por_dimensao(cpg, mp, Filtros(), "coluna_que_nao_existe")


def test_fluxo_calcula_aguardando_entrada_e_gargalo(cpg):
    f = rules.fluxo_produtivo(cpg, Filtros(mes=9, ano=2026))
    assert f.wip_total == 850.0
    assert f.aguardando_entrada == 150.0  # processo 1000 - etapas 850
    assert f.gargalo == ("Corte", 500.0)


def test_fluxo_so_lista_etapas_com_volume(cpg):
    """Unidade sem determinada etapa não deve exibir linha zerada."""
    f = rules.fluxo_produtivo(cpg, Filtros(mes=9, ano=2026))
    assert "etapa_lavanderia" not in f.etapas


def test_unidade_vem_do_dado(cpg):
    assert rules.unidade(cpg) == "Oficinas Jeans"


def test_unidade_sinaliza_arquivo_com_mais_de_uma_fabrica(cpg):
    misturado = cpg.copy()
    misturado.loc[0, "fabrica"] = "Tear"
    assert rules.unidade(misturado) == "Oficinas Jeans + Tear"


# --------------------------------------------------------------------------
# M5 · Full Kit
# --------------------------------------------------------------------------


def test_full_kit_funciona_sem_as_colunas_opcionais(mp):
    """Multiunidade: Tear/Malha/Polo podem não exportar o bloco FULL KIT SAP.

    Sem essas colunas o painel perde detalhe, mas o saldo bloqueado — que vem
    de 'Situação em MP' — continua correto. Degradar é aceitável; errar não.
    """
    fk = rules.full_kit(mp, Filtros(mes=9))
    assert fk.bloqueado == 100.0          # só a linha CORPO 'A RECEBER'
    assert fk.liberado == 100.0           # 60 + 40 'EM CASA'
    assert fk.saldo_pendente == 200.0
    assert fk.com_pedido == 0.0
    assert fk.aderente == 0.0
    assert list(fk.itens["componente"]) == ["(sem componente)"]


def test_full_kit_agrupa_por_componente_e_ordena_pelo_bloqueio(mp):
    com_componente = mp.assign(
        componente=["TECIDO-A", "TECIDO-B", "TECIDO-A", "TECIDO-A"],
        situacao_mp=["A RECEBER", "A RECEBER", "A RECEBER", "A RECEBER"],
    )
    fk = rules.full_kit(com_componente, Filtros(mes=9))
    assert list(fk.itens["componente"]) == ["TECIDO-A", "TECIDO-B"]
    assert fk.itens.iloc[0]["saldo_bloqueado"] == 140.0  # 100 + 40, sem o COMPLEMENTO


def test_full_kit_sem_saldo_devolve_tabela_vazia_com_colunas(mp):
    """Recorte vazio não pode quebrar a tela que itera as colunas."""
    fk = rules.full_kit(mp, Filtros(mes=12))
    assert fk.saldo_pendente == 0.0
    assert list(fk.itens.columns)[:3] == ["componente", "descricao", "tipo"]


@pytest.mark.parametrize(
    ("texto", "numero", "quantidade"),
    [
        ("4700033544 - 10000 - 10/08/2026", "4700033544", 10000.0),
        ("4700034062 - 26,5 -", "4700034062", 26.5),
        ("  4700034062 - 1.250 - 01/09/2026 ", "4700034062", 1250.0),
    ],
)
def test_pedido_de_compra_le_o_formato_do_sap(texto, numero, quantidade):
    pedido = rules.pedido_de_compra(texto)
    assert pedido["numero"] == numero
    assert pedido["quantidade"] == quantidade


def test_pedido_de_compra_sem_data_nao_inventa_previsao():
    assert pd.isna(rules.pedido_de_compra("4700034062 - 26,5 -")["previsao"])


@pytest.mark.parametrize("texto", ["", "   ", "sem pedido", None, "4700033544"])
def test_texto_fora_do_padrao_nao_vira_pedido(texto):
    assert rules.pedido_de_compra(texto) is None


def test_simulador_ignora_componente_inexistente(mp):
    com_componente = mp.assign(componente=["TECIDO-A"] * 4)
    s = rules.simular_chegada(com_componente, Filtros(mes=9), ["NAO-EXISTE"])
    assert s.ganho == 0.0
    assert s.saldo_alvo == 0.0


def test_simulador_so_libera_o_que_a_regra_permite(mp):
    """A linha bloqueada tem PROGRAMAR=NÃO: MP chegando, ela continua parada."""
    com_componente = mp.assign(componente=["TECIDO-A"] * 4)
    s = rules.simular_chegada(com_componente, Filtros(mes=9), ["TECIDO-A"])
    assert s.saldo_alvo == 100.0
    assert s.ganho == 0.0
    assert s.motivos == {"Não liberado para programar": 100.0}


# --------------------------------------------------------------------------
# M6 · Prazos
# --------------------------------------------------------------------------


HOJE = pd.Timestamp("2026-07-31")


def _cpg_prazo(dias: list[int | None]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mes": pd.array([9] * len(dias), dtype="Int64"),
            "ano": pd.array([2026] * len(dias), dtype="Int64"),
            "pedido": [f"P{i}" for i in range(len(dias))],
            "a_programar": [10.0] * len(dias),
            "carteira_total": [10.0] * len(dias),
            "data_lib_recomendada": [
                pd.NaT if d is None else HOJE + pd.Timedelta(days=d) for d in dias
            ],
        }
    )


@pytest.mark.parametrize(
    ("dias", "faixa"),
    [
        (-1, "Estourado"),
        (0, "Crítico · até 7 dias"),
        (7, "Crítico · até 7 dias"),
        (8, "Atenção · 8 a 15 dias"),
        (15, "Atenção · 8 a 15 dias"),
        (16, "Programável · 16 a 30 dias"),
        (31, "Folga · acima de 30 dias"),
        (None, rules.SEM_DATA),
    ],
)
def test_faixa_de_prazo_nos_limites(dias, faixa):
    """Os limites são inclusivos: 7 ainda é crítico, 8 já é atenção."""
    p = rules.prazos(_cpg_prazo([dias]), Filtros(mes=9, ano=2026), HOJE)
    assert p.faixas[faixa] == 10.0


def test_prazo_conta_dias_a_partir_do_snapshot_e_nao_de_hoje():
    """A régua é a data da base. Rodar o app amanhã não pode mover o passado."""
    p = rules.prazos(_cpg_prazo([-30]), Filtros(mes=9, ano=2026), HOJE)
    assert p.dias_atraso_max == 30.0
    assert p.referencia == HOJE


def test_prazo_sem_a_coluna_de_data_joga_tudo_em_sem_data(cpg):
    p = rules.prazos(cpg, Filtros(mes=9, ano=2026), HOJE)
    assert p.faixas[rules.SEM_DATA] == 300.0
    assert p.estourado == 0.0
    assert p.no_prazo == 0.0


def test_prazo_ignora_linha_ja_totalmente_programada():
    base = _cpg_prazo([-5, 10])
    base.loc[0, "a_programar"] = 0.0
    p = rules.prazos(base, Filtros(mes=9, ano=2026), HOJE)
    assert p.total == 10.0
    assert p.estourado == 0.0


# --------------------------------------------------------------------------
# M10 · Programação semanal
# --------------------------------------------------------------------------


def _mp_semanal(dias: list[int | None], liberado: list[bool] | None = None) -> pd.DataFrame:
    """BASE MP mínima: uma linha CORPO por data recomendada.

    Sem as colunas opcionais de propósito — outra unidade pode não exportar
    descrição ou componente, e a agenda não pode depender delas.
    """
    quantas = len(dias)
    liberado = [True] * quantas if liberado is None else liberado
    return pd.DataFrame(
        {
            "mes": pd.array([9] * quantas, dtype="Int64"),
            "parte_peca": ["CORPO"] * quantas,
            "referencia": [f"R{i}" for i in range(quantas)],
            "material": [f"M{i}" for i in range(quantas)],
            "saldo_a_programar": [10.0] * quantas,
            "prototipo": ["SIM"] * quantas,
            "programar": ["SIM"] * quantas,
            "status_avi": ["SIM"] * quantas,
            "situacao_mp": ["EM CASA" if ok else "A RECEBER" for ok in liberado],
            "data_recomendacao": [
                pd.NaT if d is None else HOJE + pd.Timedelta(days=d) for d in dias
            ],
        }
    )


@pytest.mark.parametrize(
    ("dias", "situacao"),
    [
        (-11, rules.VENCIDA),        # domingo da semana retrasada
        (-5, rules.VENCIDA),         # domingo anterior — ainda semana passada
        (-4, rules.ESTA_SEMANA),     # segunda da semana do snapshot
        (0, rules.ESTA_SEMANA),
        (2, rules.ESTA_SEMANA),      # domingo — o fim da semana da fábrica
        (3, rules.PROXIMA_SEMANA),   # segunda seguinte
        (10, rules.FUTURA),
        (None, rules.SEM_SEMANA),
    ],
)
def test_semana_vai_de_segunda_a_domingo_e_e_lida_do_snapshot(dias, situacao):
    """A virada é na segunda, não na quinta da ISO nem no dia do snapshot."""
    ps = rules.programacao_semanal(_mp_semanal([dias]), Filtros(mes=9), HOJE)
    assert ps.semanas["situacao"].tolist() == [situacao]
    assert ps.referencia == HOJE


def test_segunda_e_domingo_da_mesma_semana_caem_na_mesma_linha():
    ps = rules.programacao_semanal(_mp_semanal([-4, 2]), Filtros(mes=9), HOJE)
    assert len(ps.semanas) == 1
    assert ps.semanas["disponivel"].iloc[0] == 20.0
    assert ps.semanas["periodo"].iloc[0] == "27/07 a 02/08"


def test_soma_das_semanas_fecha_com_o_kpi_de_disponivel(mp):
    """Duas contas diferentes para a mesma pergunta seria o defeito original."""
    ps = rules.programacao_semanal(mp, Filtros(mes=9), HOJE)
    esperado = rules.detratores(mp, Filtros(mes=9))["disponivel_para_programar"]
    assert ps.disponivel == pytest.approx(esperado)


def test_linha_sem_data_recomendada_continua_na_agenda():
    """Descartá-la faria a soma ficar menor que o KPI, sem dizer onde foi parar."""
    ps = rules.programacao_semanal(_mp_semanal([0, None]), Filtros(mes=9), HOJE)
    assert ps.sem_data == 10.0
    assert ps.disponivel == 20.0
    assert ps.semanas["situacao"].iloc[-1] == rules.SEM_SEMANA


def test_travas_sao_somadas_em_separado_e_nao_particionam_o_saldo():
    """A mesma peça sem MP e sem AVI precisa aparecer nas duas colunas."""
    base = _mp_semanal([0], liberado=[False])
    base.loc[0, "status_avi"] = "NAO"
    ps = rules.programacao_semanal(base, Filtros(mes=9), HOJE)
    linha = ps.semanas.iloc[0]
    assert (linha["sem_mp"], linha["sem_avi"]) == (10.0, 10.0)
    assert linha["saldo"] == 10.0 and linha["disponivel"] == 0.0
    assert ps.travado == 10.0


def test_agenda_ordena_da_semana_mais_antiga_para_a_mais_distante():
    ps = rules.programacao_semanal(_mp_semanal([10, None, -11, 0]), Filtros(mes=9), HOJE)
    assert ps.semanas["situacao"].tolist() == [
        rules.VENCIDA, rules.ESTA_SEMANA, rules.FUTURA, rules.SEM_SEMANA
    ]


def test_itens_trazem_so_o_que_esta_liberado():
    """O travado tem painel próprio; misturar devolve a lista que se filtra na mão."""
    ps = rules.programacao_semanal(
        _mp_semanal([0, 3], liberado=[True, False]), Filtros(mes=9), HOJE
    )
    assert ps.itens["referencia"].tolist() == ["R0"]
    assert ps.itens["saldo_a_programar"].sum() == 10.0


def test_itens_vem_da_semana_mais_atrasada_para_a_mais_folgada():
    ps = rules.programacao_semanal(_mp_semanal([10, -11, 0]), Filtros(mes=9), HOJE)
    assert ps.itens["referencia"].tolist() == ["R1", "R2", "R0"]


def test_pico_aponta_a_semana_que_concentra_o_disponivel():
    base = _mp_semanal([0, 3, 3])
    ps = rules.programacao_semanal(base, Filtros(mes=9), HOJE)
    assert ps.pico == ("03/08 a 09/08", 20.0)


def test_semana_sem_data_nunca_e_apontada_como_pico():
    """'Sem data' não é uma semana — anunciar capacidade nela seria inventar agenda."""
    ps = rules.programacao_semanal(_mp_semanal([None, None, 0]), Filtros(mes=9), HOJE)
    assert ps.pico == ("27/07 a 02/08", 10.0)


def test_recorte_sem_linha_devolve_agenda_vazia_com_colunas():
    ps = rules.programacao_semanal(_mp_semanal([0]), Filtros(mes=1), HOJE)
    assert ps.semanas.empty and ps.itens.empty
    assert "disponivel" in ps.semanas.columns and "recomendado" in ps.itens.columns
    assert (ps.disponivel, ps.saldo, ps.pct_disponivel) == (0.0, 0.0, 0.0)
    assert ps.pico is None


def test_agenda_sem_saldo_nao_divide_por_zero():
    base = _mp_semanal([0])
    base.loc[0, "saldo_a_programar"] = 0.0
    ps = rules.programacao_semanal(base, Filtros(mes=9), HOJE)
    assert ps.pct_disponivel == 0.0
    assert ps.semanas["pct_disponivel"].iloc[0] == 0.0


# --------------------------------------------------------------------------
# M7 · Evolução histórica
#
# A planilha de referência tem um snapshot só; a matemática de velocidade e
# projeção só existe com dois ou mais. Aqui a série é sintética de propósito.
# --------------------------------------------------------------------------

COMPETENCIA_SET = Filtros(mes=9, ano=2026)


def _carga(cpg, mp, snapshot: str, a_programar: float) -> Carga:
    """Uma fotografia da base num dia, com o saldo pendente informado.

    `carteira_total` fica fixa: o que anda entre snapshots é a programação.
    """
    base = cpg.copy()
    base.loc[base["mes"] == 9, "a_programar"] = [a_programar, 0.0]
    return Carga(
        cpg=base,
        mp=mp,
        unidade="Oficinas Jeans",
        data_snapshot=pd.Timestamp(snapshot),
        competencias=[(2026, 9)],
        diagnostico=Diagnostico(),
        veio_do_cache=False,
        segundos=0.0,
        arquivo=f"{snapshot}.xlsx",
    )


@pytest.fixture
def serie(cpg, mp) -> list[Carga]:
    """10 dias, 100 peças programadas: 10 peças/dia, 200 ainda pendentes."""
    return [
        _carga(cpg, mp, "2026-09-01", 300.0),
        _carga(cpg, mp, "2026-09-06", 250.0),
        _carga(cpg, mp, "2026-09-11", 200.0),
    ]


def test_velocidade_usa_a_janela_inteira(serie):
    """Último par sozinho deixaria um dia sem carga derrubar a projeção."""
    e = loader.evolucao(serie, COMPETENCIA_SET)
    assert e.pontos == 3
    assert e.suficiente
    assert e.velocidade == pytest.approx(10.0)


def test_projecao_de_fechamento_e_o_saldo_dividido_pelo_ritmo(serie):
    e = loader.evolucao(serie, COMPETENCIA_SET)
    assert e.dias_uteis_restantes == pytest.approx(20.0)
    assert e.data_projetada == pd.Timestamp("2026-10-01")
    assert e.fim_competencia == pd.Timestamp("2026-09-30")
    assert e.dias_de_atraso == pytest.approx(1.0)


def test_serie_fora_de_ordem_e_reordenada_por_snapshot(cpg, mp, serie):
    bagunçada = [serie[2], serie[0], serie[1]]
    e = loader.evolucao(bagunçada, COMPETENCIA_SET)
    assert list(e.serie["snapshot"]) == sorted(e.serie["snapshot"])
    assert e.velocidade == pytest.approx(10.0)


def test_variacao_compara_primeiro_e_ultimo_snapshot(serie):
    e = loader.evolucao(serie, COMPETENCIA_SET)
    assert e.variacao("a_programar") == pytest.approx(-100.0)
    assert e.variacao("programado") == pytest.approx(100.0)


def test_programacao_parada_nao_projeta_data(cpg, mp):
    """Velocidade zero: dividir por ela daria data no infinito."""
    parada = [
        _carga(cpg, mp, "2026-09-01", 300.0),
        _carga(cpg, mp, "2026-09-06", 300.0),
    ]
    e = loader.evolucao(parada, COMPETENCIA_SET)
    assert e.velocidade == 0.0
    assert e.data_projetada is None
    assert e.dias_de_atraso is None


def test_saldo_crescendo_nao_projeta_fechamento(cpg, mp):
    """Carteira entrando mais rápido que a programação: não há data de fim."""
    piorando = [
        _carga(cpg, mp, "2026-09-01", 200.0),
        _carga(cpg, mp, "2026-09-06", 300.0),
    ]
    e = loader.evolucao(piorando, COMPETENCIA_SET)
    assert e.velocidade < 0
    assert e.data_projetada is None


def test_sem_competencia_nao_ha_fim_de_mes_para_comparar(serie):
    e = loader.evolucao(serie, Filtros())
    assert e.fim_competencia is None
    assert e.dias_de_atraso is None


def test_snapshot_ausente_fica_fora_da_serie(cpg, mp, serie):
    sem_data = _carga(cpg, mp, "2026-09-01", 300.0)
    object.__setattr__(sem_data, "data_snapshot", None)
    e = loader.evolucao([*serie, sem_data], COMPETENCIA_SET)
    assert e.pontos == 3


def test_prazo_sem_saldo_nao_divide_por_zero():
    p = rules.prazos(_cpg_prazo([]), Filtros(mes=9, ano=2026), HOJE)
    assert p.total == 0.0
    assert p.pct_estourado == 0.0
    assert p.dias_atraso_max == 0.0


# --------------------------------------------------------------------------
# Falhas de arquivo e de cache — o que acontece quando o caminho feliz quebra
# --------------------------------------------------------------------------


def test_zip_que_nao_e_xlsx_falha_com_mensagem_acionavel(tmp_path):
    """Um .zip renomeado passa no `ZipFile` e só quebra ao procurar as partes.

    Antes subia um `KeyError` cru sobre 'xl/workbook.xml' e a tela dizia apenas
    'erro inesperado' — sem dizer o que o usuário deveria fazer.
    """
    falso = tmp_path / "follow_up.xlsx"
    with zipfile.ZipFile(falso, "w") as z:
        z.writestr("leiame.txt", "não sou uma planilha")

    with pytest.raises(ArquivoInvalidoError, match="estrutura interna"):
        ingest.Planilha.abrir(str(falso))


@pytest.mark.parametrize(
    ("ref", "esperado"),
    [("A1", 0), ("AB12", 27), ("12", -1), ("", -1)],
)
def test_referencia_de_celula_sem_letra_e_descartada(ref, esperado):
    """.xlsx gerado fora do Excel traz `r` malformado; adivinhar coluna, nunca."""
    assert ingest._indice_coluna(ref) == esperado


def _cache_com_entrada(raiz) -> tuple[CacheParquet, dict]:
    cache = CacheParquet(raiz)
    bases = {
        schema.BASE_CPG: pd.DataFrame({"fabrica": ["Oficinas Jeans"]}),
        schema.BASE_MP: pd.DataFrame({"saldo_a_programar": [10.0]}),
    }
    cache.gravar("abc", bases, {"arquivo": "follow_up.xlsx"})
    return cache, bases


def test_falha_transitoria_de_leitura_nao_apaga_o_cache(tmp_path, monkeypatch):
    """Apagar aqui destrói para sempre um ponto da série do M7.

    Arquivo travado por antivírus ou por sincronização de nuvem é rotina no
    Windows e passa sozinho. O cache não pode ser reconstruído sem o .xlsx
    original de 139 MB, então erro de I/O devolve vazio e tenta de novo depois.
    """
    cache, _ = _cache_com_entrada(tmp_path)

    def travado(*_args, **_kwargs):
        raise OSError(22, "The process cannot access the file")

    monkeypatch.setattr(pd, "read_parquet", travado)
    assert cache.ler("abc") is None
    monkeypatch.undo()

    guardado = cache.ler("abc")
    assert guardado is not None
    assert set(guardado[0]) == {schema.BASE_CPG, schema.BASE_MP}


def test_cache_ilegivel_e_descartado_para_reprocessar(tmp_path):
    """Conteúdo inválido é o único caso em que apagar é a saída certa."""
    cache, _ = _cache_com_entrada(tmp_path)
    (cache._pasta("abc") / "metadados.json").write_text("{ isto não é json", encoding="utf-8")

    assert cache.ler("abc") is None
    assert not cache._pasta("abc").exists()
