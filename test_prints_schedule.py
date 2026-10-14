from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import prints_schedule as ps


class PrintsScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'routine.json'
        self.now = datetime(2026, 1, 1, 10)
        self.callback = Mock(return_value={'ok':True,'mensagem':'2 prints novos.'})
        self.agenda = ps.Agendador(self.callback, self.path, lambda:self.now)

    def configure(self, **values):
        return self.agenda.configurar({'enabled':True,**values}, {'copy':True,'destination':'test'})

    def test_interval_waits_then_runs_once(self):
        self.configure(mode='interval', interval_minutes=15)
        self.assertFalse(self.agenda.passo())
        self.now += timedelta(minutes=15)
        self.assertTrue(self.agenda.passo())
        self.assertFalse(self.agenda.passo())
        self.callback.assert_called_once_with({'copy':True,'destination':'test'})
        self.assertEqual(self.agenda.estado()['next'], '2026-01-01T10:30:00')

    def test_daily_count_is_distributed_in_24_hours(self):
        config = ps.normalizar({'enabled':True,'mode':'daily','daily_count':3,'daily_start':'08:00'})
        self.assertEqual(ps.horarios(config), ['00:00','08:00','16:00'])
        self.assertEqual(ps.proxima(config,self.now), datetime(2026,1,1,16))
        self.assertEqual(ps.proxima(config,datetime(2026,1,1,20)),datetime(2026,1,2))
        for count in (1,7,24,1440):
            config['daily_count']=count
            self.assertEqual(len(ps.horarios(config)),count)

    def test_exact_times_normalize_deduplicate_and_cross_midnight(self):
        config = ps.normalizar({'enabled':True,'mode':'times','times':'9:00, 18:30; 09:00'})
        self.assertEqual(config['times'], ['09:00','18:30'])
        self.assertEqual(ps.proxima(config,self.now),datetime(2026,1,1,18,30))
        self.assertEqual(ps.proxima(config,datetime(2026,1,1,23)),datetime(2026,1,2,9))

    def test_pause_survives_restart_without_running(self):
        self.configure(mode='interval', interval_minutes=1)
        self.agenda.configurar({'enabled':False}, {})
        self.now += timedelta(days=1)
        restored=ps.Agendador(self.callback,self.path,lambda:self.now)
        self.assertFalse(restored.passo())
        self.assertEqual(restored.estado()['next'],'')
        self.callback.assert_not_called()

    def test_restart_skips_past_due_slots(self):
        self.configure(mode='times',times=['10:05','11:00'])
        self.now += timedelta(minutes=30)
        restored=ps.Agendador(self.callback,self.path,lambda:self.now)
        self.assertEqual(restored.estado()['next'],'2026-01-01T11:00:00')
        self.assertFalse(restored.passo())

    def test_suspension_runs_once_and_skips_backlog(self):
        self.configure(mode='interval', interval_minutes=1)
        self.now += timedelta(hours=5)
        self.agenda.passo()
        self.assertFalse(self.agenda.passo())
        self.callback.assert_called_once()
        self.assertEqual(self.agenda.estado()['next'],'2026-01-01T15:01:00')

    def test_busy_operation_retries_without_counting_as_completed(self):
        self.callback.side_effect=[{'ocupado':True},{'ok':True,'mensagem':'Concluído.'}]
        self.configure(mode='interval',interval_minutes=1)
        self.now += timedelta(minutes=1)
        self.agenda.passo()
        self.assertEqual(self.agenda.estado()['last'],'')
        self.assertEqual(self.agenda.estado()['next'],'2026-01-01T10:01:05')
        self.now += timedelta(seconds=5)
        self.agenda.passo()
        self.assertEqual(self.callback.call_count,2)

    def test_long_operation_skips_slots_missed_while_saving(self):
        def execute(cfg):
            self.now += timedelta(minutes=10)
            return {'ok':True}
        self.callback.side_effect=execute
        self.configure(mode='interval',interval_minutes=1)
        self.now += timedelta(minutes=1)
        self.agenda.passo()
        self.assertEqual(self.agenda.estado()['next'],'2026-01-01T10:12:00')
        self.assertFalse(self.agenda.passo())
        self.callback.assert_called_once()

    def test_callback_failure_is_recorded_and_next_run_remains_scheduled(self):
        self.callback.side_effect=OSError('Destino indisponível')
        self.configure(mode='interval',interval_minutes=1)
        self.now += timedelta(minutes=1)
        self.assertTrue(self.agenda.passo())
        self.assertIn('Destino indisponível',self.agenda.estado()['result'])
        self.assertTrue(self.agenda.estado()['next'])

    def test_does_not_start_a_second_run_while_callback_is_running(self):
        started, release=threading.Event(),threading.Event()
        self.callback.side_effect=lambda cfg:(started.set(),release.wait(2),{'ok':True})[-1]
        self.configure(mode='interval',interval_minutes=1)
        self.now += timedelta(minutes=1)
        worker=threading.Thread(target=self.agenda.passo)
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            self.now += timedelta(minutes=2)
            self.assertFalse(self.agenda.passo())
            self.assertTrue(self.agenda.estado()['running'])
            self.assertEqual(self.callback.call_count,1)
        finally:
            release.set();worker.join(2)

    def test_corrupted_config_is_disabled(self):
        self.path.write_text('{broken')
        restored=ps.Agendador(self.callback,self.path,lambda:self.now)
        self.assertFalse(restored.estado()['config']['enabled'])
        self.assertIn('ler a rotina',restored.estado()['result'])

    def test_invalid_values_are_rejected(self):
        for cfg in [{'mode':'other'},{'interval_minutes':0},{'interval_minutes':'1.5'},{'mode':'daily','daily_count':1441},{'mode':'daily','daily_start':'25:00'},{'mode':'times','times':[]},{'mode':'times','times':'12:99'}]:
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):ps.normalizar(cfg)

    def test_save_failure_preserves_previous_schedule(self):
        self.configure(mode='interval',interval_minutes=15)
        previous=self.agenda.estado()
        with patch.object(self.agenda,'_salvar',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.configure(mode='times',times=['12:00'])
        self.assertEqual(self.agenda.estado(),previous)


class PrintsScheduleApiTests(unittest.TestCase):
    def setUp(self):
        import web_api
        import organizer
        self.web_api,self.organizer=web_api,organizer
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.source=root/'source';self.source.mkdir()
        self.destination=root/'destination'
        self.cfg={**organizer.DEFAULTS,'print-dir':str(self.source),'destination':str(self.destination)}
        self.api=web_api.API.__new__(web_api.API)
        self.api._prints_lock=threading.Lock();self.api._prints_agenda_lock=threading.Lock()
        self.api._prints_agenda=None;self.api._organizando=False
        self.api._emit=Mock()
        self.api.abrir_pasta=Mock()
        for mock in (patch.object(ps,'ARQUIVO',str(root/'routine.json')),patch.object(organizer,'SETTINGS_PATH',str(root/'settings.json'))):
            mock.start();self.addCleanup(mock.stop)
        self.addCleanup(lambda:self.api._prints_agenda.parar(esperar=True) if self.api._prints_agenda else None)

    def test_routine_saves_preferences_and_can_be_paused(self):
        result=self.api.prints_rotina_salvar({'enabled':True,'interval_minutes':10},self.cfg)
        self.assertTrue(result['ok'])
        self.assertEqual(result['estado']['prints']['destination'],str(self.destination))
        self.assertTrue(self.api.prints_rotina_pausar()['ok'])
        self.assertFalse(self.api.prints_rotina_estado()['config']['enabled'])

    def test_missing_source_and_same_destination_do_not_activate(self):
        for cfg in [{**self.cfg,'print-dir':'missing'}, {**self.cfg,'destination':str(self.source)}]:
            self.assertFalse(self.api.prints_rotina_salvar({'enabled':True},cfg)['ok'])
        self.assertIsNone(self.api._prints_agenda)

    def test_scheduled_copy_uses_existing_organizer_without_opening_explorer(self):
        filename='2026-01-01_120000000_Test_LevelUp.png'
        (self.source/filename).write_bytes(b'test image')
        result=self.api._organizar_agendado({**self.cfg,'open-when-done':True})
        self.assertTrue(result['ok'])
        self.assertEqual((self.destination/'Test'/'LevelUp'/filename).read_bytes(),b'test image')
        self.assertTrue((self.source/filename).exists())
        self.api.abrir_pasta.assert_not_called()
        second=self.api._organizar_agendado(self.cfg)
        self.assertIn('0 prints novos; 1 já salvos',second['mensagem'])

    def test_backup_restore_stops_old_agenda_and_reloads_restored_preferences(self):
        import backup
        self.assertTrue(self.api.prints_rotina_salvar({'enabled':True,'interval_minutes':10},self.cfg)['ok'])
        original=self.api._prints_agenda
        saved={'config':{'enabled':False,'mode':'times','times':['11:00']},'prints':self.cfg,'next':''}
        self.api._backup_pendente={'formato':backup.FORMATO,'arquivos':{'prints_rotina':saved}}
        self.api._caminhos_backup=lambda:{'prints_rotina':ps.ARQUIVO}
        result=self.api.config_restaurar()
        self.assertTrue(result['ok'])
        self.assertTrue(original._stop.is_set())
        self.assertFalse(original._thread.is_alive())
        self.assertIsNone(self.api._prints_agenda)
        restored=self.api.prints_rotina_estado()
        self.assertFalse(restored['config']['enabled'])
        self.assertEqual(restored['config']['times'],['11:00'])

    def test_manual_and_scheduled_operations_share_lock(self):
        self.api._prints_lock.acquire()
        try:
            self.assertFalse(self.api.organizar(self.cfg)['ok'])
            self.assertTrue(self.api._organizar_agendado(self.cfg)['ocupado'])
        finally:self.api._prints_lock.release()
        self.assertFalse(self.api._organizando)


if __name__=='__main__':unittest.main()
