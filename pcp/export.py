"""M9 — Exportação do detalhamento em Excel.

Camada de aplicação: conhece `Carga` e o motor de regras, e não sabe que existe
Streamlit. Devolve **bytes**, não escreve arquivo — quem decide onde salvar é a
interface (ou o teste).

O que sai daqui é o detalhamento em dado, não a imagem do painel: uma aba por
bloco da tela, com o mesmo recorte de filtros que estava valendo. O objetivo é
o que hoje se faz na mão — abrir a planilha, filtrar e copiar para o e-mail da
reunião — sem a chance de copiar o filtro errado.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd

from . import rules
from .loader import Carga

# Rótulo de cada KPI na aba Resumo. A ordem é a da faixa de cartões do painel:
# quem receber o arquivo reconhece a sequência da tela.
ROTULOS_KPI: dict[str, str] = {
    "carteira_total": "Carteira Total",
    "programado": "Programado",
    "a_programar": "A Programar",
    "sem_avi": "Sem AVI",
    "sem_mp": "Sem MP",
    "sem_prototipo": "Sem Protótipo",
    "mp_prot_sem_avi": "MP + Protótipo (sem AVI)",
    "disponivel_para_programar": "Disponível para Programar",
}


def _resumo(carga: Carga, filtros: rules.Filtros, titulo_periodo: str) -> pd.DataFrame:
    """Carimbo + os 8 indicadores. É a aba que sustenta as outras.

    O carimbo não é decoração: como cada um sobe a própria planilha, um arquivo
    exportado sem data de snapshot vira discussão de número na reunião seguinte.
    """
    k = rules.kpis(carga.cpg, carga.mp, filtros)
    contexto = [
        ("Unidade", carga.unidade),
        ("Competência", titulo_periodo),
        ("Snapshot da base", carga.rotulo_snapshot),
        ("Arquivo de origem", carga.arquivo),
        ("Exportado em", datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")),
        *[(f"Filtro · {chave}", valor) for chave, valor in filtros.dimensoes_ativas().items()],
    ]
    linhas = [{"Indicador": rotulo, "Valor": valor} for rotulo, valor in contexto]
    linhas.append({"Indicador": "", "Valor": ""})
    linhas += [
        {"Indicador": ROTULOS_KPI[chave], "Valor": valor}
        for chave, valor in k.as_dict().items()
    ]
    linhas.append({"Indicador": "% Programado", "Valor": k.pct_programado})
    return pd.DataFrame(linhas)


def _fluxo(carga: Carga, filtros: rules.Filtros) -> pd.DataFrame:
    """Funil e WIP na mesma aba, separados por uma coluna 'Bloco'.

    Uma linha em branco entre os dois blocos seria mais parecida com a tela,
    mas quebra filtro e tabela dinâmica do lado de quem recebe.
    """
    f = rules.fluxo_produtivo(carga.cpg, filtros)
    linhas = [
        # NaN float, não None: coluna toda-nula de dtype object faz o concat
        # abaixo mudar o tipo do bloco seguinte.
        {"Bloco": "Funil", "Etapa": rotulo, "Peças": valor, "% do WIP": float("nan")}
        for rotulo, valor, _ in f.funil()
    ]
    wip = f.como_tabela().assign(Bloco="WIP por etapa")
    return pd.concat(
        [pd.DataFrame(linhas), wip], ignore_index=True
    )[["Bloco", "Etapa", "Peças", "% do WIP"]]


def _full_kit(carga: Carga, filtros: rules.Filtros) -> pd.DataFrame:
    itens = rules.full_kit(carga.mp, filtros).itens.copy()
    if itens.empty:
        return itens
    # Lista de pedidos vira texto: célula de Excel não guarda lista.
    itens["pedidos"] = itens["pedidos"].map(lambda p: " | ".join(p) if p else "")
    return itens.rename(
        columns={
            "componente": "Componente",
            "descricao": "Descrição",
            "tipo": "Tipo MP",
            "saldo_bloqueado": "Bloqueado por MP",
            "saldo_total": "Saldo total",
            "estoque": "Estoque disponível",
            "reserva": "Reserva",
            "disponibilidade": "Disponibilidade x Consumo",
            "status": "Aderência",
            "analise": "Análise do PCP",
            "pedidos": "Pedidos de compra",
            "previsao": "Previsão",
        }
    )


def _prazos(carga: Carga, filtros: rules.Filtros) -> pd.DataFrame:
    itens = rules.prazos(carga.cpg, filtros, carga.data_snapshot).itens
    return itens.rename(
        columns={
            "pedido": "Pedido",
            "familia": "Família",
            "departamento": "Grupo",
            "toc": "TOC",
            "data_lib_recomendada": "Lib. recomendada",
            "entrega_cd": "Entrega CD",
            "a_programar": "A programar",
            "carteira_total": "Carteira total",
            "dias": "Dias até o prazo",
            "faixa": "Situação",
        }
    )


def _semanas(programacao: rules.ProgramacaoSemanal) -> pd.DataFrame:
    """Agenda por semana. `inicio` e `fim` saem junto para permitir reordenar.

    Sem elas, quem recebe o arquivo só teria o texto '27/07 a 02/08' e uma
    ordenação alfabética que embaralha a agenda na virada do mês.
    """
    return programacao.semanas.rename(
        columns={
            "inicio": "Início",
            "fim": "Fim",
            "semana": "Semana",
            "periodo": "Período",
            "situacao": "Situação",
            "saldo": "Saldo da semana",
            "disponivel": "Disponível",
            "sem_mp": "Sem MP",
            "sem_prototipo": "Sem protótipo",
            "sem_avi": "Sem AVI",
            "travado": "Travado",
            "pct_disponivel": "% Disponível",
        }
    )


def _disponivel(programacao: rules.ProgramacaoSemanal) -> pd.DataFrame:
    """O detalhamento do que está liberado — a lista que hoje se filtra na mão."""
    return programacao.itens.rename(
        columns={
            "referencia": "Referência",
            "material": "Material",
            "descricao_material": "Descrição",
            "familia": "Família",
            "departamento": "Grupo",
            "toc": "TOC",
            "quinzena": "Quinzena",
            "componente": "Componente",
            "recomendado": "Data recomendada",
            "semana": "Semana",
            "periodo": "Período",
            "situacao": "Situação",
            "saldo_a_programar": "Peças disponíveis",
        }
    )


def _por_dimensao(carga: Carga, filtros: rules.Filtros, dimensao: str) -> pd.DataFrame:
    tabela = rules.kpis_por_dimensao(carga.cpg, carga.mp, filtros, dimensao)
    return tabela.rename(columns={**ROTULOS_KPI, "pct_programado": "% Programado"})


def abas(carga: Carga, filtros: rules.Filtros, titulo_periodo: str) -> dict[str, pd.DataFrame]:
    """Uma aba por bloco de tela, na ordem da navegação."""
    # As duas abas semanais são dois recortes do mesmo cálculo: agenda e itens
    # saem do mesmo `ProgramacaoSemanal`, então ele é feito uma vez só.
    programacao = rules.programacao_semanal(carga.mp, filtros, carga.data_snapshot)
    return {
        "Resumo": _resumo(carga, filtros, titulo_periodo),
        "Carteira por TOC": _por_dimensao(carga, filtros, "toc"),
        "Carteira por Grupo": _por_dimensao(carga, filtros, "departamento"),
        "Fluxo Produtivo": _fluxo(carga, filtros),
        "Full Kit": _full_kit(carga, filtros),
        "Prazos": _prazos(carga, filtros),
        "Programação Semanal": _semanas(programacao),
        "Disponível por Semana": _disponivel(programacao),
    }


def excel(
    carga: Carga,
    filtros: rules.Filtros,
    titulo_periodo: str,
    serie: pd.DataFrame | None = None,
) -> bytes:
    """Detalhamento completo do recorte em .xlsx, pronto para anexar."""
    conteudo = abas(carga, filtros, titulo_periodo)
    if serie is not None and not serie.empty:
        conteudo["Evolução"] = serie

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter", datetime_format="dd/mm/yyyy") as escritor:
        for nome, df in conteudo.items():
            df.to_excel(escritor, sheet_name=nome[:31], index=False)
            _formatar(escritor, nome[:31], df)
    return buffer.getvalue()


def _formatar(escritor: pd.ExcelWriter, aba: str, df: pd.DataFrame) -> None:
    """Cabeçalho fixo, largura por conteúdo e milhar brasileiro.

    Sem isso o arquivo chega com colunas de 8 caracteres e números colados —
    e a primeira coisa que o destinatário faz é reformatar tudo à mão.
    """
    livro, planilha = escritor.book, escritor.sheets[aba]
    cabecalho = livro.add_format(
        {"bold": True, "bg_color": "#12301E", "font_color": "#FFFFFF", "border": 0}
    )
    numero = livro.add_format({"num_format": "#,##0"})

    for coluna, nome in enumerate(df.columns):
        planilha.write(0, coluna, str(nome), cabecalho)
        largura = max(len(str(nome)), _largura_do_conteudo(df[nome]))
        formato = numero if pd.api.types.is_numeric_dtype(df[nome]) else None
        planilha.set_column(coluna, coluna, min(largura + 2, 46), formato)

    if len(df.columns):
        planilha.freeze_panes(1, 0)


def _largura_do_conteudo(serie: pd.Series, amostra: int = 200) -> int:
    valores = serie.head(amostra).astype(str)
    return int(valores.str.len().max()) if not valores.empty else 0
