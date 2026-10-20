# Conversão de gold no Market Tracker

A opção automática usa `sell_average_price` de `tibiaCoinPrice.list` do TibiaTrade, por mundo selecionado. É uma **média diária de venda**, não uma oferta ao vivo. A tela informa a data-base da linha daquele mundo e a consulta ao serviço.

Somente linhas com até 36 horas são aplicadas. Ausência, inconsistência, data inválida ou falha de rede mantém o valor manual e informa isso na tela. O cache de todos os mundos vive apenas em memória por uma hora; atualização forçada e novas tentativas após falha respeitam intervalo mínimo de um minuto. Não há gravação de cotações no histórico do Market.

O preço em reais e a quantidade de TC por pacote continuam manuais. `Salvar valores` guarda o gold por TC **manual**, os dois parâmetros do pacote e a preferência automática no arquivo privado `market-conversao-tc.json`. Arquivos antigos com os três parâmetros continuam aceitos e iniciam com a opção automática ligada. O gold obtido não é salvo. A calculadora do chatbot permanece independente.

Fonte: https://tibiatrade.gg/tc-to-gold
