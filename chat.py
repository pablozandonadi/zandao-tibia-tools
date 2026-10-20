"""Chat de texto do Assistente: comando local primeiro; só o que as regras não entendem vai à IA. Histórico só em memória."""
import threading
import uuid
from decimal import Decimal, InvalidOperation

import assistente_tibiano as assistente
import calculadora_gold
import comandos_tibia
from voice import device_id
from voice.remote_ai_client import RemoteAIClient, RemoteAIError, load_settings, utf16_length, truncate_utf16

FORA_DO_ESCOPO = 'Posso ajudar só com o Tibia e contas do jogo (gold, TC, stamina, shared), além das ferramentas do Tibia Tudo.'
SEM_ACESSO = 'Para conversar com a IA, ative o acesso online em Configurações. Os comandos do canal Help funcionam sem isso.'
IA_INDISPONIVEL = 'Não consegui falar com a IA agora. Os comandos do canal Help continuam funcionando.'
NAO_ENTENDI = 'Não entendi. Tente um dos comandos do canal Help.'
TEXTO_INVALIDO = 'Escreva uma mensagem de até 500 caracteres.'
SEM_SALVAR = 'Não consegui salvar. Nenhuma alteração foi confirmada.'
BOOSTED = 'Confirme no formulário que era o Archfoe boosted do dia e elegível; nenhum abate foi registrado.'
NADA = '—'
SEM_ACAO = 'Tudo bem. Nenhuma ação executada.'
ACAO_MANUAL = 'Para isso, use o comando ou o formulário da aba correspondente.'
MAX_TEXTO, MAX_MENSAGENS, MAX_BYTES = 500, 6, 3000


def entendi_de(intent, args, result):
    """"Entendi" da ação executada; o boss aparece pelo nome que a Store resolveu ("drumi" -> Drume, wiki-123 -> nome)."""
    values = dict(args or {})
    if values.get('boss_id') and result.get('boss'):
        values['boss_id'] = result['boss']['name']
    return assistente.describe(intent, values)


def executar_intencao(store, action, parameters, context, request_id, source='manual', ao_executar=None, origem_ia=False):
    """Executa a intenção validada que veio da IA. Devolve (resposta, entendi); entendi é '—' quando nada foi feito.
    ao_executar(intent, args, result) roda só depois de uma execução bem-sucedida (a voz registra os bosses recentes)."""
    if origem_ia and action in ('boss.kill.undo', 'market.price.delete', 'bosstiary.set_total'):
        return ACAO_MANUAL, NADA
    try:
        if action in assistente.FIELDS:
            intent, args = action, {k: v for k, v in parameters.items() if v is not None}
            if action == 'boss.kill' and args.get('boosted') is True:
                return BOOSTED, NADA
        elif action == 'create_timer':
            intent, args = 'timer.create', {'duration_seconds': parameters['seconds']}
        elif action == 'cancel_last_timer':
            intent, args = 'timer.cancel', {'last': True}
        elif action == 'shared':
            intent, args = 'shared.range', ({'reference_level': parameters['level']} if parameters['level'] is not None else {})
        elif action in ('cancel_timer', 'query_timer'):
            intent, args = ('timer.cancel' if action == 'cancel_timer' else 'timer.get'), {'timer_id': parameters['timer_id']}
        else:
            return NAO_ENTENDI, NADA
        result = store.execute(intent, args, context, request_id, source=source)
    except ValueError as error:
        return str(error), NADA
    except OSError:
        return SEM_SALVAR, NADA
    if ao_executar:
        ao_executar(intent, args, result)
    return assistente.reply(result), entendi_de(intent, args, result)


class Chat:
    def __init__(self, store, pasta):
        self.store, self.pasta = store, pasta
        self._lock = threading.Lock()  # só o histórico; nunca fica preso durante a rede
        self._historico = []
        self._geracao = 0
        self._perfil = None

    def limpar(self):
        with self._lock:
            self._historico = []
            self._geracao += 1  # uma resposta que ainda está na rede não volta ao histórico limpo

    def _fim(self, texto, resposta, entendi, origem, geracao, registrar=True):
        with self._lock:
            if registrar and geracao == self._geracao:
                # as 6 últimas bastam: a IA vê no máximo 5 delas + a fala atual
                self._historico = [*self._historico, {'role': 'user', 'text': texto}, {'role': 'assistant', 'text': truncate_utf16(resposta, MAX_TEXTO)}][-MAX_MENSAGENS:]
        return {'resposta': resposta, 'entendi': entendi, 'origem': origem}

    def _preco_tc(self, context):
        """Mediana de venda do TC no Market local; sem dado ou com erro, o preço padrão."""
        try:
            stats = self.store.execute('market.stats', {'item': 'TC', 'offer_type': 'sell', 'days': 30}, context, None, source='manual')
            if stats.get('count') and stats.get('median'):
                return Decimal(str(stats['median'])), 'Market local'
        except (ValueError, OSError, InvalidOperation):
            pass
        return Decimal(48000), 'padrão'

    def _mensagens(self, texto):
        with self._lock:
            mensagens = [*self._historico[-(MAX_MENSAGENS - 1):], {'role': 'user', 'text': texto}]
        while len(mensagens) > 1 and sum(len(m['text'].encode('utf-8')) for m in mensagens) > MAX_BYTES:
            mensagens.pop(0)
        return mensagens

    def responder(self, texto, permitir_ia=True):
        texto = texto.strip() if isinstance(texto, str) else ''
        if not texto or utf16_length(texto) > MAX_TEXTO:
            return {'resposta': TEXTO_INVALIDO, 'entendi': NADA, 'origem': 'erro'}
        context = self.store.context()
        perfil = (context.get('character_id'), context.get('world_id'))
        with self._lock:
            if perfil != self._perfil:
                self._historico = []
                self._geracao += 1
                self._perfil = perfil
            geracao = self._geracao
        consulta = comandos_tibia.responder(texto, context.get('world_id') or '', personagem=context.get('character_id') or '')
        if consulta is None:
            consulta = calculadora_gold.responder(texto, self.pasta, lambda: self._preco_tc(context))
        if consulta is not None:
            return self._fim(texto, consulta, 'Consulta Tibia', 'local', geracao, registrar=permitir_ia)
        somente_resposta, erro_local = False, None
        try:
            comando = assistente.parse(texto, self.store.clock())
        except ValueError as error:
            if permitir_ia and (str(error) == SEM_ACAO or str(error).startswith('Comando ambíguo.')):
                comando, somente_resposta, erro_local = None, True, str(error)
            else:
                return self._fim(texto, str(error), NADA, 'erro', geracao, registrar=permitir_ia)
        if comando:
            resposta, entendi = executar_intencao(self.store, *comando, context, str(uuid.uuid4()))
            # sem "entendi" nada foi executado (erro do comando): não é um comando local bem-sucedido
            return self._fim(texto, resposta, entendi, 'local' if entendi != NADA else 'erro', geracao, registrar=permitir_ia)
        if not permitir_ia:
            return self._fim(texto, 'Comando local não reconhecido. Use Tudo IA para perguntas.', NADA, 'local', geracao, registrar=False)
        enabled, token = load_settings(self.pasta)
        if not enabled or not token:
            return self._fim(texto, erro_local if somente_resposta else SEM_ACESSO, NADA, 'erro', geracao, registrar=permitir_ia)
        try:
            ia = RemoteAIClient(token, device_id=device_id.carregar(self.pasta)).chat(self._mensagens(texto), str(uuid.uuid4()))
        except (RemoteAIError, OSError) as error:
            if somente_resposta:
                return self._fim(texto, erro_local, NADA, 'erro', geracao, registrar=permitir_ia)
            mensagem = IA_INDISPONIVEL
            if isinstance(error, RemoteAIError) and error.status == 401:
                mensagem = 'Código de acesso recusado. Confira em Configurações.'
            elif isinstance(error, RemoteAIError) and error.status in (403, 429):
                mensagem = str(error)
            return self._fim(texto, mensagem, NADA, 'erro', geracao, registrar=permitir_ia)
        if ia['kind'] == 'reply':
            return self._fim(texto, ia['text'], NADA, 'ia', geracao, registrar=permitir_ia)
        if ia['kind'] == 'out_of_scope':
            return self._fim(texto, FORA_DO_ESCOPO, NADA, 'fora', geracao, registrar=permitir_ia)
        if somente_resposta:
            return self._fim(texto, erro_local, NADA, 'ia', geracao, registrar=permitir_ia)
        intent = ia['intent']
        if intent['needs_clarification']:
            return self._fim(texto, intent['clarification'], NADA, 'ia', geracao, registrar=permitir_ia)
        resposta, entendi = executar_intencao(self.store, intent['action'], intent['parameters'], context, str(uuid.uuid4()), origem_ia=True)
        return self._fim(texto, resposta, entendi, 'ia', geracao, registrar=permitir_ia)
