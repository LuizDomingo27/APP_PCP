"""M9 — Relatório imprimível dos painéis.

**Por que HTML e não PDF gerado no servidor.** Um PDF fiel exigiria ou um
navegador headless (dependência pesada de instalar na máquina de quem usa) ou
redesenhar cada painel em ReportLab — e aí passariam a existir dois layouts
para o mesmo painel, que divergem na primeira mudança de CSS. Este relatório é
montado pelos **mesmos construtores da tela**: o que está no papel é o que está
no monitor, por construção. Quem precisa de PDF abre o arquivo e imprime
(Ctrl+P → Salvar como PDF), com quebra de página e cores já ajustadas aqui.

É também o motivo de importar os construtores privados das views: reimplementá-los
aqui recriaria exatamente a divergência que este módulo existe para evitar.
"""

from __future__ import annotations

from datetime import datetime

from pcp import Carga
from pcp.rules import (
    Filtros,
    fluxo_produtivo,
    full_kit,
    kpis,
    prazos as regra_prazos,
    programacao_semanal,
)

from . import components as c
from . import theme
from .views import carteira as v_carteira
from .views import detratores as v_detratores
from .views import fluxo as v_fluxo
from .views import fullkit as v_fullkit
from .views import prazos as v_prazos
from .views import semanal as v_semanal

# Blocos que o usuário escolhe levar para a reunião, na ordem da navegação.
BLOCOS: dict[str, str] = {
    "carteira": "Carteira Geral",
    "detratores": "Detratores",
    "fluxo": "Fluxo Produtivo",
    "fullkit": "Full Kit & MP",
    "prazos": "Prazos & Deadline",
    "semanal": "Programação Semanal",
}

# Impressão: fundo branco, cor preservada nos cartões e nenhum bloco partido no
# meio de uma página.
_CSS_IMPRESSAO = """
<style>
body { background: #F4F6F4; margin: 0; padding: 22px; }
.pcp-rel { max-width: 1180px; margin: 0 auto; }
.pcp-rel__secao { margin-bottom: 22px; break-inside: avoid; }
.pcp-rel__tit {
  font-size: .68rem; font-weight: 800; letter-spacing: .12em;
  text-transform: uppercase; color: #5C6B60; margin: 0 0 8px;
  font-family: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
}
.pcp-rel__rodape {
  margin-top: 26px; padding-top: 12px; border-top: 1px solid #DFE4E0;
  font-size: .68rem; color: #8B9A90;
  font-family: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
}
@media print {
  @page { size: A4 landscape; margin: 10mm; }
  body { background: #fff; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .pcp-kpi, .pcp-painel, .pcp-nota { box-shadow: none !important; }
  .pcp-rel__secao { page-break-inside: avoid; }
}
</style>
"""


def _secao(titulo: str, *blocos: str) -> str:
    corpo = "".join(b for b in blocos if b)
    return (
        f'<section class="pcp-rel__secao">'
        f'<h2 class="pcp-rel__tit">{titulo}</h2>{corpo}</section>'
    )


def _conteudo(carga: Carga, filtros: Filtros, escolhidos: list[str]) -> str:
    partes = []
    # Só os dois primeiros blocos dependem dos KPIs; calcular sempre fazia um
    # relatório de "só Prazos" varrer as duas bases inteiras à toa.
    k = (
        kpis(carga.cpg, carga.mp, filtros)
        if {"carteira", "detratores"}.intersection(escolhidos)
        else None
    )

    if "carteira" in escolhidos and k is not None:
        partes.append(
            _secao(
                BLOCOS["carteira"],
                v_carteira._faixa(k),
                v_carteira._performance(k),
                v_carteira._tabela_toc(carga, filtros, k),
            )
        )
    if "detratores" in escolhidos and k is not None and k.a_programar > 0:
        partes.append(_secao(BLOCOS["detratores"], v_detratores._ranking(k)))
    if "fluxo" in escolhidos:
        f = fluxo_produtivo(carga.cpg, filtros)
        partes.append(
            _secao(BLOCOS["fluxo"], v_fluxo._faixa(f), v_fluxo._etapas(f), v_fluxo._leitura(f))
        )
    if "fullkit" in escolhidos:
        fk = full_kit(carga.mp, filtros)
        if fk.saldo_pendente > 0:
            partes.append(_secao(BLOCOS["fullkit"], v_fullkit._faixa(fk), v_fullkit._ranking(fk)))
    if "prazos" in escolhidos:
        p = regra_prazos(carga.cpg, filtros, carga.data_snapshot)
        if p.total > 0:
            partes.append(
                _secao(BLOCOS["prazos"], v_prazos._faixa(p), v_prazos._distribuicao(p),
                       v_prazos._leitura(p), v_prazos._tabela(p))
            )
    if "semanal" in escolhidos:
        ps = programacao_semanal(carga.mp, filtros, carga.data_snapshot)
        if ps.saldo > 0:
            partes.append(
                _secao(BLOCOS["semanal"], v_semanal._faixa(ps), v_semanal._agenda(ps),
                       v_semanal._leitura(ps), v_semanal._tabela_semanas(ps),
                       v_semanal._tabela_itens(ps))
            )
    return "".join(partes)


def pagina(
    carga: Carga,
    filtros: Filtros,
    titulo_periodo: str,
    escolhidos: list[str] | None = None,
) -> str:
    """Documento HTML completo e autocontido — nada de CDN, nada de imagem externa.

    `unidade` e `arquivo` vêm da planilha e do nome do upload, e este arquivo é
    aberto direto do disco (`file://`) e mandado por e-mail para a reunião — ou
    seja, roda fora de qualquer proteção do Streamlit. Tudo que não é texto
    nosso é escapado antes de entrar no documento.
    """
    escolhidos = escolhidos if escolhidos is not None else list(BLOCOS)
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    titulo = f"Follow Up · {carga.unidade} · {titulo_periodo}"

    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<title>{c.escapar(titulo)}</title>{theme.CSS}{_CSS_IMPRESSAO}</head><body>"
        f'<div class="pcp-rel">'
        + c.cabecalho(titulo, f"{carga.unidade} · {titulo_periodo}",
                      [("Atualizado em", carga.rotulo_snapshot)])
        + _conteudo(carga, filtros, escolhidos)
        + f'<div class="pcp-rel__rodape">Gerado pela aplicação de PCP em {gerado} · '
        f"base de {c.escapar(carga.rotulo_snapshot)} · "
        f"arquivo {c.escapar(carga.arquivo)}</div>"
        "</div></body></html>"
    )


def nome_arquivo(carga: Carga, titulo_periodo: str, extensao: str) -> str:
    """`follow-up_oficinas-jeans_setembro-2026_31-07-2026.xlsx`."""
    def limpar(texto: str) -> str:
        seguro = "".join(ch if ch.isalnum() else "-" for ch in texto.lower())
        return "-".join(p for p in seguro.split("-") if p)

    return (
        f"follow-up_{limpar(carga.unidade)}_{limpar(titulo_periodo)}"
        f"_{limpar(carga.rotulo_snapshot)}.{extensao}"
    )
