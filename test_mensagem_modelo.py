"""Modelo novo da Mensagem do dia (manual e automática): frase por dia, data por extenso, notícias, blocos em negrito e sem ❓ solto."""
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import comandos_tibia as c
import mensagem_formato as f
import mensagens_tibianas as mensagens
import zandaobot_report
from mensagem_automatica_core import UTC, reference_day
from mensagem_automatica_report import generate


class FraseDoDia(unittest.TestCase):
    def test_60_dias_seguidos_nao_repetem_e_nao_dependem_da_sessao(self):
        dias = [mensagens.do_dia(date(2026, 10, 1) + timedelta(days=i), 'CharAntica') for i in range(60)]
        self.assertEqual(len(set(dias)), 60)
        self.assertEqual(dias, [mensagens.do_dia(date(2026, 10, 1) + timedelta(days=i), 'CharAntica') for i in range(60)])

    def test_dia_seguinte_sempre_muda(self):
        for i in range(120):
            d = date(2026, 1, 1) + timedelta(days=i)
            self.assertNotEqual(mensagens.do_dia(d, 'x'), mensagens.do_dia(d + timedelta(days=1), 'x'))


class Formato(unittest.TestCase):
    def test_data_por_extenso_com_hora(self):
        self.assertEqual(f.data_hora(date(2026, 10, 22), datetime(2026, 10, 22, 8, 17)), 'quinta-feira, 22 de outubro de 2026 às 08:17')
        self.assertEqual(f.data_hora(date(2026, 3, 1)), 'domingo, 1 de março de 2026')

    def test_noticias_com_avisos_curtos_e_limite(self):
        artigos = [{'titulo': f'T{i}', 'data': '2026-10-20', 'categoria': 'development' if i == 0 else 'x'} for i in range(5)]
        r = f.noticias(artigos, [{'texto': 'Mundos  ok', 'data': '2026-10-22'}])
        self.assertTrue(r.startswith('📰 *O que rolou em Tibia*'))
        self.assertIn('• 🔥 *T0* (20/10)', r)
        self.assertIn('• 📰 *T1* (20/10)', r)
        self.assertNotIn('T3', r)
        self.assertIn('⚡ 22/10: Mundos ok', r)
        self.assertIsNone(f.noticias([], []))


R = {'dia': '2026-10-22', 'mundo': 'Rasteibra', 'personagem': 'Zandao', 'rashid': 'Ankrahmun',
     'boostados': {'criatura': {'nome': 'Lizard Henchman'}, 'boss': {'nome': 'The Scourge Of Oblivion'}},
     'yasir': {'estado': 'ausente'}, 'dream_court': {'velho': True},
     'calendario': {'estado': 'disponivel', 'eventos': [{'estado': 'ativo', 'titulo': 'Annual Autumn Vintage', 'fim': '2026-10-24'}]},
     'anuncios': [], 'noticias': [{'titulo': 'Balancing, Fixes and Changes', 'data': '2026-10-20', 'categoria': 'development'}],
     'news_ticker': [{'texto': 'Novos mundos', 'data': '2026-10-21'}]}


class MensagemManual(unittest.TestCase):
    def test_modelo_completo_na_ordem_certa_e_sem_ruido(self):
        t = zandaobot_report.gerar(R, {'comunidade': 'Piratas do Rocks', 'assinatura': 'Zandão'}, ['⚔️ *Top 10 criaturas*', '🏆 *Top XP*'],
                                   agora=datetime(2026, 10, 22, 8, 17))
        ordem = ['☀️ *Bom dia, Piratas do Rocks!*', '📅 quinta-feira, 22 de outubro de 2026 às 08:17', '💬 *Mensagem do dia:*', '🌍 *Mundo:* Rasteibra',
                 '🧭 *Rashid:* Ankrahmun', '🧬 *Criatura do dia:* Lizard Henchman', '👑 *Boss do dia:* The Scourge Of Oblivion',
                 '🎉 *Evento:* Annual Autumn Vintage (até 24/10)', '🐪 *Yasir:* 🔴 Inativo', '📰 *O que rolou em Tibia*',
                 '• 🔥 *Balancing, Fixes and Changes* (20/10)', '⚡ 21/10: Novos mundos', '⚔️ *Top 10 criaturas*', '🏆 *Top XP*', '━━━━━━━━━━━━━━', '✍️ Zandão']
        posicoes = [t.index(x) for x in ordem]
        self.assertEqual(posicoes, sorted(posicoes))
        for ruido in ('❓', 'consulta online', 'Próximo SS', 'Dream Court', 'Outras world changes', '\n\n\n'):
            self.assertNotIn(ruido, t)

    def test_frase_muda_de_um_dia_para_o_outro(self):
        a = zandaobot_report.gerar(R, agora=datetime(2026, 10, 22, 8, 0))
        b = zandaobot_report.gerar({**R, 'dia': '2026-10-23'}, agora=datetime(2026, 10, 23, 8, 0))
        self.assertNotEqual(a.split('"')[1], b.split('"')[1])

    def test_campos_manuais_so_aparecem_preenchidos(self):
        t = zandaobot_report.gerar(R, {'deeplings': 'Ferumbras', 'coin_compra': '43.552'}, agora=datetime(2026, 10, 22, 8, 0))
        self.assertIn('🔱 *Boss Deeplings:* Ferumbras', t)
        self.assertIn('comprar 43.552 gp', t)
        self.assertNotIn('Roshamuul', t)


class Noticias(unittest.TestCase):
    def test_extra_noticias_usa_titulos_e_avisos_sem_repetir(self):
        latest = {'news': [{'id': 1, 'date': '2026-10-20', 'news': 'Balancing', 'category': 'development', 'type': 'news'}]}
        ticker = {'news': [{'id': 1, 'date': '2026-10-20', 'news': 'Balancing', 'category': 'development', 'type': 'ticker'},
                           {'id': 2, 'date': '2026-10-22', 'news': 'Mundos ok', 'category': 'community', 'type': 'ticker'}]}
        with patch.object(c, '_get', side_effect=lambda chave, endpoint: ((latest if endpoint.endswith('latest') else ticker), False)):
            r = c.extra('noticias')
        self.assertIn('*Balancing* (20/10)', r)
        self.assertIn('⚡ 22/10: Mundos ok', r)
        self.assertEqual(r.count('Balancing'), 1)


class Transferencias(unittest.TestCase):
    def test_linhas_repetidas_do_guildstats_aparecem_uma_vez(self):
        linha = ('Leto Bugado', 266, 'EK', 'Xybra', 'Rasteibra', '2026-10-20')
        with patch.object(c, '_transferidos', return_value=[linha, linha]):
            r = c._transfer('Rasteibra', '', hoje=date(2026, 10, 22))
        self.assertEqual(r.count('Leto Bugado'), 2)  # uma em Entraram, outra em Saíram
        self.assertIn('🟢 *Entraram (1):*', r)
        self.assertIn('🔴 *Saíram (1):*', r)

    def test_level_com_ponto_de_milhar(self):
        with patch.object(c, '_transferidos', return_value=[('Alto', 1156, 'EK', 'Xybra', 'Rasteibra', '2026-10-20')]):
            self.assertIn('— Lv 1.156, de Xybra (20/10)', c._transfer('Rasteibra', '', hoje=date(2026, 10, 22)))

    def test_aviso_curto_fica_na_primeira_frase(self):
        r = f.noticias([], [{'texto': 'Novo episódio no ar. Nele, o host fala de coisas longas demais para caber', 'data': '2026-10-23'}])
        self.assertIn('⚡ 23/10: Novo episódio no ar', r)
        self.assertNotIn('host', r)


class MensagemAutomatica(unittest.TestCase):
    def test_modelo_novo_com_blocos_e_assinatura(self):
        now = datetime.now(UTC)
        ref = reference_day(now)

        class Provider:
            def summary(self, cfg, agora):
                base = {'consulta': agora.timestamp(), 'dia': ref}
                return {'calendario': {**base, 'estado': 'disponivel', 'eventos': [{'estado': 'ativo', 'titulo': 'Annual Autumn Vintage', 'fim': '2026-10-24'}]},
                        'yasir': {**base, 'estado': 'ausente', 'mudancas': []},
                        'boostados': {**base, 'boss': {'nome': 'Boss fixture'}, 'criatura': {'nome': 'Rat fixture'}}}
        cfg = {'personagem': 'Pirata Teste', 'mundo': 'Antica', 'timezone': 'America/Sao_Paulo',
               'blocks': {k: True for k in ('saudacao', 'dia', 'frase', 'mundo', 'rashid', 'criatura', 'boss', 'calendario', 'yasir', 'mudancas_online')},
               'fields': {'assinatura': True, 'comunidade': True}, 'values': {'assinatura': 'Zandão', 'comunidade': 'Piratas'}}
        t = generate(cfg, now, Provider())['text']
        for esperado in ('☀️ *Bom dia, Piratas!*', '📅 ', '💬 *Mensagem do dia:*', '🌍 *Mundo:* Antica', '🧬 *Criatura do dia:* Rat fixture',
                         '👑 *Boss do dia:* Boss fixture', '🎉 *Evento:* Annual Autumn Vintage (até 24/10)', '🐪 *Yasir:* 🔴 Inativo', '━━━━━━━━━━━━━━\n✍️ Zandão'):
            self.assertIn(esperado, t)
        self.assertNotIn('consulta online', t)
        self.assertNotIn('Outras world changes', t)  # lista vazia não vira bloco
        self.assertLess(t.index('Bom dia'), t.index('Mensagem do dia'))
        self.assertLess(t.index('Mensagem do dia'), t.index('Mundo'))


if __name__ == '__main__':
    unittest.main()
