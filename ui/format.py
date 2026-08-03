"""Formatação pt-BR. Camada de apresentação pura."""

from __future__ import annotations

import pandas as pd


def numero(valor: float | int | None, casas: int = 0) -> str:
    """574934 -> '574.934' (separador de milhar brasileiro)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", " ").replace(".", ",").replace(" ", ".")


def pct(valor: float | None, casas: int = 0) -> str:
    """0.8602 -> '86%'."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    return f"{valor * 100:.{casas}f}".replace(".", ",") + "%"


def pct_programado(valor: float | None) -> str:
    """Avanço da programação — sempre com 2 casas.

    No início da competência o avanço é fracionário (2.860 de 645.939 = 0,44%)
    e arredondar para inteiro exibia '0%', escondendo que já existe programação
    feita. Os demais percentuais seguem inteiros: são pesos sobre o saldo, onde
    a casa decimal não muda decisão nenhuma.
    """
    return pct(valor, casas=2)


def sinal(valor: float, casas: int = 0) -> str:
    """Variação com sinal explícito: '+12.400' / '−3.200'."""
    if valor == 0:
        return "0"
    return ("+" if valor > 0 else "−") + numero(abs(valor), casas)


def data(momento: pd.Timestamp | None) -> str:
    """NaT entra no mesmo caminho de None: 'NaT' na tela seria vazamento técnico."""
    if momento is None or pd.isna(momento):
        return "—"
    return pd.Timestamp(momento).strftime("%d/%m/%Y")


MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def nome_mes(mes: int) -> str:
    return MESES[mes - 1] if 1 <= mes <= 12 else str(mes)


def competencia(ano: int, mes: int) -> str:
    return f"{nome_mes(mes)}/{ano}"
