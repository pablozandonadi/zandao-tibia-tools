import copy
import inspect
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import assistente_tibiano as a
import chat
from voice.remote_ai_client import RemoteAIError

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
CTX = {'character_id': 'Teste', 'world_id': 'Antica', 'level': 438}
TOKEN = 'a' * 43
DRUME = {'boss_id': 'drume', 'killed_at': None, 'boosted': False}


def acao(action, parameters, clarification=None):
    return {'kind': 'action', 'text': None, 'intent': {'action': action, 'parameters': parameters, 'needs_clarification': clarification is not None, 'clarification': clarification}}


def resposta_ia(text):
    return {'kind': 'reply', 'text': text, 'intent': None}


class ChatCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        self.personagens('Teste')
        self.store = a.Store(self.pasta, clock=lambda: NOW)
        self.chat = chat.Chat(self.store, self.pasta)
        settings = patch('chat.load_settings', return_value=(True, TOKEN))
        settings.start()
        self.addCleanup(settings.stop)
        cliente = patch('chat.RemoteAIClient')
        self.classe = cliente.start()
        self.addCleanup(cliente.stop)
        self.ia = self.classe.return_value.chat
        self.ia.return_value = resposta_ia('Resposta da IA.')

    def personagens(self, atual):
        (self.pasta / 'meus_personagens.json').write_text(json.dumps({'atual': atual, 'lista': [{'nome': 'Teste', 'mundo': 'Antica', 'level': 438}, {'nome': 'Outro', 'mundo': 'Secura', 'level': 200}]}))

    def abates(self, boss='drume', ctx=CTX):
        return self.store.execute('bosstiary.get', {'boss_id': boss}, ctx)['boss']['real_kills']

    def eventos(self):
        return self.store.execute('history', {}, CTX)['events']

    def enviados(self):
        """Mensagens de cada chamada à IA (cópia: o Chat pode mudar a lista depois)."""
        return [copy.deepcopy(call.args[0]) for call in self.ia.call_args_list]


class ComandosLocais(ChatCase):
    def test_comando_executa_e_entendi_traz_o_nome_do_boss(self):
        r = self.chat.responder('matei drumi')
        self.assertEqual('local', r['origem'])
        self.assertIn('Drume', r['resposta'])
        self.assertEqual('Registrar abate · Drume · 16/10 às 08:00', r['entendi'])
        self.assertEqual(1, self.abates())
        self.assertEqual('manual', self.eventos()[-1]['source'])
        self.classe.assert_not_called()

    def test_id_wiki_vira_nome(self):
        r = self.chat.responder('matei wiki-25288')
        self.assertEqual('local', r['origem'])
        self.assertEqual('Registrar abate · Abyssador · 16/10 às 08:00', r['entendi'])

    def test_comando_sem_boss_tem_entendi_do_describe(self):
        r = self.chat.responder('timer de 30 segundos')
        self.assertEqual(('local', 'Criar timer · 30 s'), (r['origem'], r['entendi']))

    def test_erro_do_parse_nao_chama_a_ia(self):
        r = self.chat.responder('TC tá 1.500')
        self.assertEqual({'resposta': 'Preço ambíguo. Confirme o inteiro em GP ou use K/KK.', 'entendi': '—', 'origem': 'erro'}, r)
        self.classe.assert_not_called()

    def test_erro_do_execute_nao_chama_a_ia(self):
        r = self.chat.responder('cancela o timer de 2 minutos')
        self.assertEqual(('Nenhum timer correspondente.', '—', 'erro'), (r['resposta'], r['entendi'], r['origem']))
        self.classe.assert_not_called()

    def test_disco_falhou_nao_chama_a_ia(self):
        with patch('assistente_tibiano.os.replace', side_effect=OSError('disco')):
            r = self.chat.responder('matei drume')
        self.assertEqual(('erro', '—'), (r['origem'], r['entendi']))
        self.assertIn('Nenhuma alteração foi confirmada', r['resposta'])
        self.assertEqual(0, self.abates())
        self.classe.assert_not_called()


class TextoInvalido(ChatCase):
    def test_vazio_e_longo_demais_nao_vao_a_rede_nem_ao_historico(self):
        erro = {'resposta': 'Escreva uma mensagem de até 500 caracteres.', 'entendi': '—', 'origem': 'erro'}
        for texto in ('', '   \n ', 'x' * 501, '  ' + 'x' * 501):
            with self.subTest(len=len(texto)):
                self.assertEqual(erro, self.chat.responder(texto))
        self.classe.assert_not_called()
        self.chat.responder('Como funciona o imbuement?')
        self.assertEqual([[{'role': 'user', 'text': 'Como funciona o imbuement?'}]], self.enviados())

    def test_500_caracteres_passa_e_vai_sem_espacos_nas_pontas(self):
        self.assertEqual('ia', self.chat.responder('  ' + 'x' * 500 + ' ')['origem'])
        self.assertEqual([[{'role': 'user', 'text': 'x' * 500}]], self.enviados())


class ComIA(ChatCase):
    def test_sem_acesso(self):
        for config in ((False, TOKEN), (True, None), (False, None)):
            with self.subTest(config=config), patch('chat.load_settings', return_value=config):
                r = self.chat.responder('Como funciona o imbuement?')
                self.assertEqual({'resposta': chat.SEM_ACESSO, 'entendi': '—', 'origem': 'erro'}, r)
        self.classe.assert_not_called()

    def test_reply(self):
        self.ia.return_value = resposta_ia('Imbuement dá bônus.')
        r = self.chat.responder('Como funciona o imbuement?')
        self.assertEqual({'resposta': 'Imbuement dá bônus.', 'entendi': '—', 'origem': 'ia'}, r)
        self.classe.assert_called_once_with(TOKEN)
        mensagens, request_id = self.ia.call_args.args
        self.assertEqual([{'role': 'user', 'text': 'Como funciona o imbuement?'}], mensagens)
        self.assertEqual(36, len(request_id))

    def test_load_settings_le_a_pasta_do_chat(self):
        with patch('chat.load_settings', return_value=(True, TOKEN)) as load:
            self.chat.responder('Como funciona o imbuement?')
        load.assert_called_once_with(self.pasta)

    def test_action_executa_no_contexto_capturado_antes_da_rede(self):
        def troca_de_personagem(*_):
            self.personagens('Outro')
            return acao('boss.kill', DRUME)
        self.ia.side_effect = troca_de_personagem
        r = self.chat.responder('registra o drume pra mim')
        self.assertEqual(('ia', 'Registrar abate · Drume'), (r['origem'], r['entendi']))
        self.assertIn('Drume', r['resposta'])
        self.assertEqual(1, self.abates())
        self.assertEqual(0, self.abates(ctx={**CTX, 'character_id': 'Outro'}))
        self.assertEqual('manual', self.eventos()[-1]['source'])

    def test_action_com_boss_pelo_id_wiki_mostra_o_nome(self):
        self.ia.return_value = acao('boss.kill', {**DRUME, 'boss_id': 'wiki-25288'})
        self.assertEqual('Registrar abate · Abyssador', self.chat.responder('registra o abyssador pra mim')['entendi'])

    def test_action_com_clarification_mostra_a_pergunta_e_nao_grava(self):
        ia = acao('boss.kill', DRUME, 'Confirme a data pelo formulário.')
        ia['text'] = 'Registrei o Drume!'
        self.ia.return_value = ia
        r = self.chat.responder('registra a morte do drume ontem')
        self.assertEqual({'resposta': 'Confirme a data pelo formulário.', 'entendi': '—', 'origem': 'ia'}, r)
        self.assertEqual(0, self.abates())
        self.assertEqual([], self.eventos())

    def test_boss_kill_boosted_da_ia_nao_grava(self):
        self.ia.return_value = acao('boss.kill', {**DRUME, 'boosted': True})
        r = self.chat.responder('registra o drume boosted')
        self.assertEqual(('ia', '—'), (r['origem'], r['entendi']))
        self.assertIn('Confirme no formulário', r['resposta'])
        self.assertEqual(0, self.abates())

    def test_out_of_scope(self):
        self.ia.return_value = {'kind': 'out_of_scope', 'text': None, 'intent': None}
        self.assertEqual({'resposta': chat.FORA_DO_ESCOPO, 'entendi': '—', 'origem': 'fora'}, self.chat.responder('receita de bolo'))

    def test_falha_da_ia(self):
        for erro in (RemoteAIError('limite'), OSError('rede')):
            with self.subTest(erro=type(erro).__name__):
                self.ia.side_effect = erro
                self.assertEqual({'resposta': chat.IA_INDISPONIVEL, 'entendi': '—', 'origem': 'erro'}, self.chat.responder('Como funciona o imbuement?'))


class ExecutarIntencao(ChatCase):
    def executar(self, action, parameters, request_id='r1', **extra):
        return chat.executar_intencao(self.store, action, parameters, CTX, request_id, **extra)

    def test_acoes_legadas(self):
        self.assertEqual(('Timer de 30 segundos iniciado.', 'Criar timer · 30 s'), self.executar('create_timer', {'seconds': 30}))
        resposta, entendi = self.executar('shared', {'level': 100}, 'r2')
        self.assertEqual(('Seu shared vai do level 67 até 150.', 'Consultar shared · level 100'), (resposta, entendi))
        self.assertEqual(('Seu shared vai do level 292 até 657.', 'Consultar shared'), self.executar('shared', {'level': None}, 'r3'))
        self.assertEqual(('Timer de 30 segundos cancelado.', 'Cancelar timer'), self.executar('cancel_last_timer', {}, 'r4'))

    def test_consulta_e_cancela_timer_pelo_id(self):
        timer = self.store.execute('timer.create', {'duration_seconds': 90}, CTX)['timer']
        self.assertEqual(('Faltam 90 segundos no timer 90 segundos.', 'Consultar timer'), self.executar('query_timer', {'timer_id': timer['id']}, 'r1'))
        self.assertEqual(('Timer de 90 segundos cancelado.', 'Cancelar timer'), self.executar('cancel_timer', {'timer_id': timer['id']}, 'r2'))
        self.assertEqual(('Nenhum timer correspondente.', '—'), self.executar('cancel_timer', {'timer_id': 'sumiu'}, 'r3'))

    def test_acao_de_dominio_ignora_parametros_none(self):
        resposta, entendi = self.executar('timer.create', {'duration_seconds': 45, 'label': None, 'personal': False})
        self.assertEqual(('Timer de 45 segundos iniciado.', 'Criar timer · 45 s'), (resposta, entendi))

    def test_unknown_e_acao_desconhecida(self):
        self.assertEqual((chat.NAO_ENTENDI, '—'), self.executar('unknown', {}))
        self.assertEqual((chat.NAO_ENTENDI, '—'), self.executar('apagar_tudo', {}))

    def test_source_padrao_manual_e_voice_quando_pedido(self):
        self.executar('market.price.add', {'item': 'TC', 'price': '35k', 'offer_type': 'sell', 'observed_at': None}, 'r1')
        self.executar('market.price.add', {'item': 'TC', 'price': '36k', 'offer_type': 'sell', 'observed_at': None}, 'r2', source='voice')
        self.assertEqual(['manual', 'voice'], [e['source'] for e in self.eventos()])

    def test_ao_executar_recebe_intencao_argumentos_e_resultado(self):
        visto = []
        self.executar('boss.kill', {**DRUME, 'boss_id': 'drumi'}, ao_executar=lambda *args: visto.append(args))
        (intent, args, result), = visto
        self.assertEqual(('boss.kill', {'boss_id': 'drumi', 'boosted': False}), (intent, args))
        self.assertEqual('Drume', result['boss']['name'])
        self.executar('boss.kill', {**DRUME, 'boosted': True}, ao_executar=lambda *args: visto.append(args))
        self.assertEqual(1, len(visto), 'o que não executou não é registrado')


class Historico(ChatCase):
    def test_ate_seis_mensagens_terminando_na_fala_atual(self):
        for i in range(1, 7):
            self.ia.return_value = resposta_ia(f'resposta {i}')
            self.chat.responder(f'pergunta {i} sobre tibia')
        enviados = self.enviados()
        self.assertEqual([1, 3, 5, 6, 6, 6], [len(m) for m in enviados])
        self.assertEqual([('assistant', 'resposta 2'), ('user', 'pergunta 3 sobre tibia'), ('assistant', 'resposta 3'), ('user', 'pergunta 4 sobre tibia'),
                          ('assistant', 'resposta 4'), ('user', 'pergunta 5 sobre tibia')], [(m['role'], m['text']) for m in enviados[4]])

    def test_limite_de_3000_bytes_utf8_descarta_as_mais_antigas(self):
        for i in range(4):
            self.ia.return_value = resposta_ia(f'{i}' + 'ã' * 399)
            self.chat.responder(f'{i}' + 'ç' * 399)
        ultima = self.enviados()[-1]
        self.assertEqual([('user', '2' + 'ç' * 399), ('assistant', '2' + 'ã' * 399), ('user', '3' + 'ç' * 399)], [(m['role'], m['text']) for m in ultima])
        self.assertLessEqual(sum(len(m['text'].encode('utf-8')) for m in ultima), 3000)

    def test_fala_atual_de_4_bytes_por_letra_sempre_fica(self):
        for _ in range(2):
            self.ia.return_value = resposta_ia('ã' * 400)
            self.chat.responder('ç' * 400)
        self.chat.responder('😀' * 500)
        ultima = self.enviados()[-1]
        self.assertEqual([('assistant', 'ã' * 400), ('user', '😀' * 500)], [(m['role'], m['text']) for m in ultima])
        self.assertLessEqual(sum(len(m['text'].encode('utf-8')) for m in ultima), 3000)

    def test_resposta_longa_entra_truncada_em_500(self):
        self.ia.return_value = resposta_ia('z' * 600)
        self.assertEqual('z' * 600, self.chat.responder('Como funciona o imbuement?')['resposta'])
        self.chat.responder('e o prey?')
        self.assertEqual('z' * 500, self.enviados()[-1][1]['text'])

    def test_comandos_locais_e_respostas_de_erro_entram_no_historico(self):
        self.chat.responder('timer de 30 segundos')
        self.chat.responder('TC tá 1.500')
        self.chat.responder('Como funciona o imbuement?')
        self.assertEqual(['timer de 30 segundos', 'Timer de 30 segundos iniciado.', 'TC tá 1.500', 'Preço ambíguo. Confirme o inteiro em GP ou use K/KK.', 'Como funciona o imbuement?'],
                         [m['text'] for m in self.enviados()[0]])

    def test_falha_da_ia_tambem_entra_no_historico(self):
        self.ia.side_effect = RemoteAIError('x')
        self.chat.responder('Como funciona o imbuement?')
        self.ia.side_effect = None
        self.chat.responder('e o prey?')
        self.assertEqual(['Como funciona o imbuement?', chat.IA_INDISPONIVEL, 'e o prey?'], [m['text'] for m in self.enviados()[-1]])

    def test_limpar_zera_o_historico(self):
        self.chat.responder('Como funciona o imbuement?')
        self.chat.limpar()
        self.chat.responder('e o prey?')
        self.assertEqual([{'role': 'user', 'text': 'e o prey?'}], self.enviados()[-1])

    def test_nada_e_gravado_em_disco(self):
        self.chat.responder('Como funciona o imbuement?')
        self.assertEqual(['meus_personagens.json'], [p.name for p in self.pasta.iterdir()])


class Concorrencia(ChatCase):
    def test_rede_sem_lock_e_limpar_durante_a_rede_vale(self):
        def durante_a_rede(*_):
            fio = threading.Thread(target=self.chat.limpar, daemon=True)
            fio.start()
            fio.join(2)
            self.assertFalse(fio.is_alive(), 'limpar() travou: o lock foi segurado durante a rede')
            return resposta_ia('tarde demais')
        self.ia.side_effect = durante_a_rede
        self.assertEqual('tarde demais', self.chat.responder('Como funciona o imbuement?')['resposta'])
        self.ia.side_effect = None
        self.chat.responder('e o prey?')
        self.assertEqual([{'role': 'user', 'text': 'e o prey?'}], self.enviados()[-1])


class Ponte(ChatCase):
    def setUp(self):
        super().setUp()
        import web_api
        self.web_api = web_api
        base = patch('web_api.BASE_DIR', self.pasta)
        base.start()
        self.addCleanup(base.stop)
        self.api = object.__new__(web_api.API)
        self.api._chat, self.api._chat_lock = None, threading.Lock()
        self.api._voz_obter = lambda: SimpleNamespace(store=self.store)

    def test_assistente_chat_usa_um_unico_chat_com_a_store_do_assistente(self):
        r = self.api.assistente_chat('matei drume')
        self.assertEqual(('local', 1), (r['origem'], self.abates()))
        self.assertIs(self.api._chat_obter(), self.api._chat_obter())
        self.assertIs(self.store, self.api._chat.store)
        self.assertEqual(self.pasta, self.api._chat.pasta)

    def test_historico_vive_entre_chamadas_e_limpar_zera(self):
        self.api.assistente_chat('Como funciona o imbuement?')
        self.api.assistente_chat('e o prey?')
        self.assertEqual(3, len(self.enviados()[-1]))
        self.assertEqual({'ok': True}, self.api.assistente_chat_limpar())
        self.api.assistente_chat('e o prey?')
        self.assertEqual(1, len(self.enviados()[-1]))

    def test_excecao_inesperada_vira_erro_amigavel(self):
        with patch.object(chat.Chat, 'responder', side_effect=RuntimeError('boom')):
            self.assertEqual({'erro': 'Não consegui responder agora.'}, self.api.assistente_chat('oi'))

    def test_parametro_nao_pode_se_chamar_arguments(self):
        # o wrapper JS do pywebview usa o nome do parâmetro e "arguments" apaga a chamada
        self.assertEqual(['self', 'texto'], list(inspect.signature(self.web_api.API.assistente_chat).parameters))


if __name__ == '__main__':
    unittest.main()
