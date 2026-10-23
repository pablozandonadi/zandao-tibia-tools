"""Modelos de resposta dos bots: texto com variáveis entre chaves, como `{mundo}`.

Variável desconhecida fica como foi escrita (aparece na prévia). Linha que só tem variáveis e fica vazia some, para um campo
opcional não deixar buraco na mensagem. Substituição em passada única: um valor que contém `{x}` não é expandido de novo."""
import re

VARIAVEL = re.compile(r'\{([a-z][a-z_0-9]*)\}')


def renderizar(modelo, variaveis):
    linhas = []
    for linha in str(modelo).split('\n'):
        if not VARIAVEL.search(linha):
            linhas.append(linha)
            continue
        saida = VARIAVEL.sub(lambda m: str(variaveis[m[1]]) if m[1] in variaveis else m[0], linha)
        if saida.strip():
            linhas.append(saida)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(linhas)).strip()


def usa_variaveis(modelo):
    return bool(VARIAVEL.search(str(modelo)))
