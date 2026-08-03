"""Erros da camada de ingestão.

Regra do projeto: nada de zero silencioso. Quando o arquivo não bate com o
contrato, a carga falha com mensagem que diz o que fazer.
"""

from __future__ import annotations


class PCPError(Exception):
    """Base de todos os erros da aplicação."""


class ArquivoInvalidoError(PCPError):
    """O arquivo não é um .xlsx legível ou está corrompido."""


class AbaAusenteError(PCPError):
    def __init__(self, aba: str, disponiveis: list[str]) -> None:
        self.aba = aba
        self.disponiveis = disponiveis
        super().__init__(
            f"A aba '{aba}' não foi encontrada na planilha.\n"
            f"Abas presentes no arquivo: {', '.join(disponiveis)}.\n"
            f"Verifique se você subiu o arquivo de Follow Up correto."
        )


class ColunaAusenteError(PCPError):
    """Cabeçalho obrigatório não encontrado.

    É o erro que impede o bug histórico do bloco de fluxo produtivo de voltar:
    antes, coluna trocada virava zero silencioso; agora barra a carga.
    """

    def __init__(self, aba: str, faltando: list[str], encontradas: list[str]) -> None:
        self.aba = aba
        self.faltando = faltando
        super().__init__(
            f"A aba '{aba}' não tem as colunas obrigatórias abaixo:\n"
            + "".join(f"  - {c}\n" for c in faltando)
            + f"\nForam encontradas {len(encontradas)} colunas. "
            f"Se a base mudou de layout, o contrato em pcp/schema.py precisa ser "
            f"atualizado — não altere a planilha para 'encaixar'."
        )


class CabecalhoAmbiguoError(PCPError):
    """Dois cabeçalhos iguais e o contrato não diz qual usar.

    Resolver por convenção implícita ("a primeira serve") é o que produziu o bug
    original do fluxo produtivo. Aqui a ambiguidade é declarada no schema, via
    `Coluna(ocorrencia=...)`, ou a carga para.
    """

    def __init__(self, aba: str, header: str, quantidade: int) -> None:
        self.aba = aba
        self.header = header
        super().__init__(
            f"A aba '{aba}' tem {quantidade} colunas chamadas '{header}' e o "
            f"contrato não define qual usar.\n"
            f"Declare `ocorrencia=N` na coluna correspondente em pcp/schema.py "
            f"para escolher explicitamente."
        )


class TipoInvalidoError(PCPError):
    """Coluna numérica chegou como texto.

    Sintoma clássico de referência apontando para a coluna errada.
    """

    def __init__(self, aba: str, coluna: str, amostra: list[str]) -> None:
        super().__init__(
            f"A coluna '{coluna}' da aba '{aba}' deveria ser numérica, mas veio "
            f"como texto. Amostra do conteúdo: {amostra}.\n"
            f"Isso normalmente indica que a coluna mudou de posição ou de "
            f"significado na base de origem."
        )


class DadoVazioError(PCPError):
    def __init__(self, aba: str) -> None:
        super().__init__(
            f"A aba '{aba}' foi encontrada, mas não tem nenhuma linha de dado."
        )
