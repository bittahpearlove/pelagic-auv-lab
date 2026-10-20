"""Meaningful physics/controller integration tests; no browser or serial needed."""
import importlib.util
from pathlib import Path
import unittest
import json

spec = importlib.util.spec_from_file_location('lab_server', Path(__file__).resolve().parents[1]/'lab/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.lab = module.Lab()
    def setUp(self):
        self.lab.lock.acquire()
        self.lab.source = 'offline'; self.lab.mode = 0
        self.lab.params = module.DEFAULTS.copy(); self.lab.reset()
    def tearDown(self):
        self.lab.running = False; self.lab.lock.release()
    def run_mission(self, mode):
        lab = self.lab
        lab.action(dict(action='configure', mode=mode, noise=0))
        lab.action(dict(action='start'))
        for _ in range(3700):
            if not lab.running: break
            lab.offline_tick()
        self.assertEqual(lab.latest['state'], 5)
        self.assertEqual(lab.latest['faults'], 0)
        return lab.ms, list(lab.rows)
    def test_port_selection_is_portable_and_never_guesses_between_boards(self):
        from types import SimpleNamespace
        def port(device,vid,pid):return SimpleNamespace(device=device,vid=vid,pid=pid)
        ftdi=port('/dev/ttyUSB0',0x0403,0x6001)
        clone=port('/dev/ttyUSB1',0x1a86,0x7523)
        self.assertEqual(module.select_serial_port([clone]),clone.device)
        self.assertEqual(module.select_serial_port([ftdi]),ftdi.device)
        with self.assertRaises(ValueError):module.select_serial_port([ftdi,clone])
        with self.assertRaises(ValueError):module.select_serial_port([])
        self.assertEqual(module.select_serial_port([ftdi,clone],clone.device),clone.device)
        with self.assertRaises(ValueError):module.select_serial_port([ftdi],clone.device)

    def test_three_modes_complete_and_adapt(self):
        durations=[]
        for mode in (0,1,2):
            duration, rows=self.run_mission(mode); durations.append(duration)
            self.assertTrue(all(abs(r['command'])<=0.25001 for r in rows))
            if mode==0:
                self.assertTrue(any(r['transition'] and r['state']==2 for r in rows))
                self.assertTrue(any(r['transition'] and r['state']==4 for r in rows))
                self.assertTrue(any(abs(r['temperature_c']-r['true_temperature_c'])>.1 for r in rows))
            if mode==1:
                self.assertTrue(all(r['speed_limit_mps']>.049 for r in rows if r['state']==2))
        self.assertLess(durations[1],durations[0]); self.assertLess(durations[0],durations[2])
    def test_flat_water_does_not_trigger(self):
        self.lab.params.update(drop=0,noise=0)
        self.lab.action(dict(action='start'))
        while self.lab.running: self.lab.offline_tick()
        self.assertFalse(any(r['transition'] for r in self.lab.rows))
    def test_faults_stop_commands_and_latch(self):
        for name,bit in [('leak',4),('stale',2),('battery',8),('tilt',32)]:
            self.lab.reset(); self.lab.action(dict(action='start'))
            for _ in range(150): self.lab.offline_tick()
            self.lab.action(dict(action='fault',value=name))
            for _ in range(25):
                if not self.lab.running: break
                self.lab.offline_tick()
            self.assertEqual(self.lab.latest['state'],6)
            self.assertTrue(self.lab.latest['faults']&bit)
            self.assertEqual(self.lab.latest['command'],0)
    def test_serial_startup_noise_then_verified_frame(self):
        log=(Path(__file__).resolve().parents[1]/'output/logs/nano_adaptive_demo.txt').read_text().splitlines()
        banner=next(x for x in log if x.startswith('# AUV Nano adaptive v0.2;'))
        header=next(x for x in log if x.startswith('ms,sample_ms,'))
        row=next(x for x in log if x[:1].isdigit())
        class FakeSerial:
            def __init__(self): self.data=(('0.000,0,0,0.000\n'*1500)+'\n'+banner+'\n'+header+'\n'+row+'\n').encode()
            @property
            def in_waiting(self): return len(self.data)
            def read(self,count): result,self.data=self.data[:count],self.data[count:]; return result
        self.lab.serial=FakeSerial(); self.lab.banner_seen=False; self.lab.header=None
        try:
            for _ in range(20): self.lab.serial_tick()
            self.assertTrue(self.lab.verified)
            self.assertEqual(len(self.lab.rows),1)
        finally: self.lab.serial=None; self.lab.verified=False

    def test_handshake_requests_identity_and_times_out(self):
        class QuietSerial:
            in_waiting=0
            def __init__(self): self.writes=[]; self.closed=False
            def read(self,count): return b''
            def write(self,data): self.writes.append(data)
            def flush(self): pass
            def close(self): self.closed=True
        link=QuietSerial()
        self.lab.serial=link; self.lab.verified=False
        self.lab.connect_started=module.time.monotonic(); self.lab.last_hello=0
        try:
            self.lab.serial_tick()
            self.assertEqual(link.writes,[b'HELLO\n'])
            self.lab.connect_started-=9
            with self.assertRaisesRegex(ValueError,'handshake timed out'): self.lab.serial_tick()
            self.lab.disconnect(); self.assertTrue(link.closed)
        finally: self.lab.serial=None; self.lab.connect_started=0

    def test_unplugged_port_cleanup_does_not_kill_worker(self):
        class GoneSerial:
            closed=False
            def write(self,data): raise OSError('unplugged')
            def close(self): self.closed=True
        link=GoneSerial(); self.lab.serial=link; self.lab.verified=True
        self.lab.disconnect()
        self.assertTrue(link.closed); self.assertIsNone(self.lab.serial)
        self.assertFalse(self.lab.verified)

    def test_config_provenance_validation_and_disconnect(self):
        lab = self.lab
        native = lab.snapshot(0)
        self.assertEqual(native['config_source'], 'native C++ core')
        self.assertAlmostEqual(native['firmware_config']['target_depth_m'], 1.0)
        self.assertAlmostEqual(native['firmware_config']['probe_tau_s'], 2.0)
        class ConfigSerial:
            def __init__(self, payload): self.data = payload.encode()
            @property
            def in_waiting(self): return len(self.data)
            def read(self, count): result,self.data=self.data[:count],self.data[count:]; return result
            def write(self, data): pass
            def flush(self): pass
            def close(self): pass
        config = dict(lab.native_config, probe_tau_s=3.25)
        packet = '# AUV Nano adaptive v0.4; simulated=1; motors=0\n# CONFIG,' + ','.join(f'{k}={v}' for k,v in config.items()) + '\n'
        lab.serial = ConfigSerial(packet); lab.source='nano'; lab.banner_seen=False
        try:
            lab.serial_tick()
            self.assertEqual(lab.firmware_config['probe_tau_s'],3.25)
            self.assertEqual(lab.snapshot(0)['firmware_config'], {}) # Not verified by a sample yet.
            lab.verified=True
            self.assertEqual(lab.snapshot(0)['firmware_config']['probe_tau_s'],3.25)
            lab.serial=ConfigSerial('# CONFIG,probe_tau_s=nan\n')
            with self.assertRaisesRegex(ValueError,'Incomplete'): lab.serial_tick()
            config['probe_tau_s']=float('nan')
            lab.serial=ConfigSerial('# CONFIG,' + ','.join(f'{k}={v}' for k,v in config.items()) + '\n')
            with self.assertRaisesRegex(ValueError,'Invalid firmware'): lab.serial_tick()
        finally: lab.disconnect(); lab.source='offline'
        self.assertEqual(lab.firmware_config,{})

    def test_shared_fields_and_vertical_profile_slice(self):
        lab=self.lab
        for case in json.loads((Path(__file__).parent/'thermal_fields.json').read_text()):
            actual=lab.core.lab_water(case['x'],case['z'],module.SHAPES[case['shape']],case['center'],case['width'],case['drop'])
            self.assertAlmostEqual(actual,case['temperature'],places=4)
        # Level layer, sloped layer and lateral front share a temperature at x=4,z=center.
        for shape in (0,1,2):self.assertAlmostEqual(lab.core.lab_water(4,.5,shape,.5,.07,3),20.5,places=4)
        self.assertGreater(lab.core.lab_water(7,.5,1,.5,.07,3),lab.core.lab_water(1,.5,1,.5,.07,3))
        self.assertAlmostEqual(lab.core.lab_water(4,.2,2,.5,.07,3),lab.core.lab_water(4,.9,2,.5,.07,3),places=5)
        # Patch follows the layer-centre setting, so it is reachable by a shallow profile.
        base=lab.core.lab_water(5.3,.85,0,.5,.07,3)
        self.assertAlmostEqual(lab.core.lab_water(5.3,.85,3,.5,.07,3)-base,2,places=4)
        lab.action(dict(action='configure',shape='combined',profile_x=5.3,noise=0))
        lab.action(dict(action='start'))
        while lab.running:lab.offline_tick()
        self.assertEqual(lab.latest['state'],5)
        self.assertTrue(any(r['transition'] for r in lab.rows))
        self.assertTrue(all(abs(r['profile_x_m']-5.3)<1e-6 for r in lab.rows))
        with self.assertRaises(ValueError):lab.action(dict(action='field',shape='unknown'))
        lab.action(dict(action='field',shape='front',profile_x=4))
        self.assertEqual(lab.params['shape'],'front')

    def test_nano_v05_field_commands_and_legacy_guard(self):
        lab=self.lab
        class CommandSerial:
            def __init__(self):self.writes=[]
            def write(self,data):self.writes.append(data)
            def flush(self):pass
            def close(self):pass
        link=CommandSerial();lab.serial=link;lab.source='nano';lab.verified=True;lab.last_rx=module.time.monotonic()
        try:
            lab.identity='v0.4 · simulated sensors · motors disabled'
            with self.assertRaisesRegex(ValueError,'v0.5'):lab.action(dict(action='field',shape='combined',profile_x=5.3))
            self.assertEqual(link.writes,[])
            lab.identity='v0.5 · simulated sensors · motors disabled'
            lab.action(dict(action='field',shape='combined',profile_x=5.3))
            self.assertEqual(link.writes,[b'DISARM\nWATER4\nX5.300\nCONFIG\n'])
            self.assertFalse(lab.running)
            lab.last_rx-=3
            with self.assertRaisesRegex(ValueError,'v0.5'):lab.action(dict(action='field',shape='layer'))
        finally:lab.disconnect();lab.source='offline'

    def test_console_raw_output_commands_deltas_and_reset(self):
        lab=self.lab
        class ConsoleSerial:
            def __init__(self):
                self.data=b'# disarmed\n# laboratory reply <not-html>\n'
                self.writes=[]
            @property
            def in_waiting(self): return len(self.data)
            def read(self,count): result,self.data=self.data[:count],self.data[count:]; return result
            def write(self,data): self.writes.append(data)
            def flush(self): pass
            def close(self): pass
        link=ConsoleSerial();lab.source='nano';lab.serial=link;lab.verified=True
        cursor=lab.console_seq
        try:
            lab.action(dict(action='diagnostics'))
            lab.serial_tick()
            entries=lab.snapshot(0,cursor)['console']
            self.assertEqual([(e['origin'],e['text']) for e in entries],
                [('TX','HELLO'),('TX','STATUS'),('NANO','# disarmed'),('NANO','# laboratory reply <not-html>')])
            self.assertEqual(link.writes,[b'HELLO\nSTATUS\n'])
            last=lab.console_seq;lab.reset()
            self.assertEqual(lab.snapshot(0,last)['console'],[])
            self.assertTrue(any(e['text']=='# disarmed' for e in lab.console))
            for i in range(520):lab.log('BRIDGE',str(i))
            self.assertEqual(len(lab.console),500)
            self.assertEqual(lab.console[-1]['text'],'519')
            lab.log('BRIDGE','x'*5000)
            self.assertEqual(len(lab.console[-1]['text']),2048)
        finally:lab.disconnect();lab.source='offline'
        self.assertEqual(link.writes[-1],b'DISARM\n')
        self.assertEqual(lab.console[-1]['text'],'USB closed')
        with self.assertRaisesRegex(ValueError,'Connect and verify'):lab.action(dict(action='diagnostics'))

    def test_native_exploration_and_two_way_measurement_contract(self):
        lab=self.lab
        lab.action(dict(action='explore_start',shape='tilted',drop=3,center=1.3))
        for _ in range(6100):lab.exploration_tick()
        self.assertTrue(lab.running);self.assertTrue(lab.explore_status['active'])
        self.assertEqual(lab.explore_status['reason'],0)
        self.assertGreater(lab.explore_status['visits'],0)
        self.assertTrue(any(r['gradient_2d_valid'] for r in lab.rows))
        self.assertGreater(lab.ms,600000)
        self.assertIn(lab.explore_status['mission_phase'],(0,1,2,5,6,7))
        self.assertTrue(any(r['explore_phase']=='transit' for r in lab.rows))
        self.assertEqual(lab.explore_status['rechecks'],0)
        self.assertGreater(lab.explore_status['known_cells'],0)
        self.assertTrue(all(a['known_cells']<=b['known_cells'] for a,b in zip(lab.rows,list(lab.rows)[1:])))
        tail=[r for r in lab.rows if r['ms']>510000]
        self.assertGreater(tail[-1]['known_cells'],tail[0]['known_cells'])
        for phase in ('backtrack','probe','monitor'):
            start=None
            for row in lab.rows:
                if row['explore_phase']!=phase:start=None
                elif start is None:start=row['input_ms']
                else:self.assertLessEqual(row['input_ms']-start,8000)
        self.assertTrue(all(abs(r['x_m']-4)<.002 for r in lab.rows if r['explore_phase'] in ('descend','backtrack')))
        self.assertTrue(any(r['explore_phase'] in ('backtrack','probe','follow') for r in lab.rows))
        self.assertTrue(all(.2<=r['x_m']<=7.8 and .08<=r['depth_m']<=2.85 for r in lab.rows))
        self.assertEqual(lab.snapshot(0)['exploration']['controller'],'Native C++')
        lab.reset();lab.action(dict(action='explore_start',shape='layer',drop=0))
        for _ in range(6100):lab.exploration_tick()
        self.assertEqual(lab.explore_status['visits'],0)
        self.assertTrue(lab.running)
        lab.action(dict(action='stop'))
        self.assertFalse(lab.running)
        self.assertFalse(lab.explore_status['active'])
        self.assertEqual(lab.explore_status['reason'],4)
        self.assertEqual(lab.latest['command'],0)
        self.assertTrue(all(abs(r['x_m']-4)<.001 for r in lab.rows if r['explore_phase']=='descend'))
        self.assertTrue(any(r['explore_phase']=='transit' for r in lab.rows))
        lab.reset()
        with self.assertRaisesRegex(ValueError,'Sweep policies removed'):lab.action(dict(action='explore_start',adaptive=False))

    def test_nano_exploration_correlates_replies_and_fails_closed(self):
        lab=self.lab
        class Link:
            def __init__(self):self.data=b'';self.writes=[]
            @property
            def in_waiting(self):return len(self.data)
            def read(self,n):out,self.data=self.data[:n],self.data[n:];return out
            def write(self,data):self.writes.append(data)
            def flush(self):pass
            def close(self):pass
        link=Link();lab.serial=link;lab.source='nano';lab.verified=True;lab.last_rx=module.time.monotonic();lab.identity='v0.5'
        try:
            with self.assertRaisesRegex(ValueError,'v0.12'):lab.action(dict(action='explore_start'))
            lab.identity='v0.12';lab.action(dict(action='explore_start',shape='patch',drop=0))
            self.assertEqual(link.writes[0],b'DISARM\nEXPL,1,2.000\n')
            lab.exploration_tick();sequence=lab.explore_pending
            packet=link.writes[-1].decode().strip().split(',')
            self.assertEqual(packet[0],'OBS');self.assertEqual(len(packet),8) # No truth field, gradients or hidden patch position.
            lab.exploration_tick();self.assertEqual(lab.ms,0) # No advance without response.
            link.data=b'# EXP,999999,1,0,0,0.2,0,0.4,0.2,0,0,0,0,0,0,0,0,0\n';lab.serial_tick();self.assertIsNone(lab.explore_reply)
            link.data=f'# EXP,{sequence},1,0,0,0.2,0,0.4,0.2,0,0,0,0,0,0,0,0,0\n'.encode();lab.serial_tick();lab.exploration_tick()
            self.assertEqual(lab.ms,100);self.assertGreater(lab.explore_x,2)
            lab.exploration_tick();lab.explore_sent-=2
            with self.assertRaisesRegex(ValueError,'reply timeout'):lab.exploration_tick()
            lab.action(dict(action='stop'));self.assertEqual(lab.latest['surge'],0);self.assertFalse(lab.running)
        finally:lab.disconnect();lab.source='offline'

    def test_exploration_field_persists_and_clears_old_samples(self):
        lab=self.lab
        lab.action(dict(action='explore_start',shape='patch',drop=0))
        for _ in range(10):lab.exploration_tick()
        with self.assertRaisesRegex(ValueError,'Stop exploration'):lab.action(dict(action='explore_field',shape='tilted',drop=3))
        lab.action(dict(action='stop'))
        lab.action(dict(action='explore_field',shape='tilted',drop=3,center=1.3,width=.1))
        state=lab.snapshot(0)
        self.assertTrue(state['exploring']);self.assertFalse(state['running'])
        self.assertEqual(state['params']['drop'],3);self.assertEqual(state['params']['shape'],'tilted')
        self.assertEqual(state['rows'],[]);self.assertIsNone(state['latest'])
        warm=lab.core.lab_water(4,.4,1,1.3,.1,3);cold=lab.core.lab_water(4,2.4,1,1.3,.1,3)
        self.assertGreater(warm-cold,2.9)
        lab.action(dict(action='explore_start'))
        self.assertEqual(lab.params['shape'],'tilted');self.assertEqual(lab.params['drop'],3)

    def test_nano_exploration_field_changes_lab_not_onboard_profile(self):
        lab=self.lab
        class Link:
            def __init__(self):self.writes=[]
            def write(self,data):self.writes.append(data)
            def flush(self):pass
            def close(self):pass
        link=Link();lab.serial=link;lab.source='nano';lab.verified=True
        try:
            lab.action(dict(action='explore_field',shape='combined',drop=3,center=1.3))
            self.assertEqual(link.writes,[b'DISARM\n'])
            self.assertEqual(lab.snapshot(0)['params']['shape'],'combined')
            with self.assertRaises(ValueError):lab.action(dict(action='explore_field',shape='bad'))
            with self.assertRaises(ValueError):lab.action(dict(action='explore_field',drop=float('nan')))
            self.assertEqual(lab.params['drop'],3)
        finally:lab.disconnect();lab.source='offline'

    def test_runtime_parameters_lock_and_invalid_inputs(self):
        with self.assertRaises(ValueError): self.lab.action(dict(action='configure',tau=0))
        self.lab.action(dict(action='start'))
        with self.assertRaises(ValueError): self.lab.action(dict(action='configure',tau=3))
        with self.assertRaises(ValueError): self.lab.action(dict(action='mode',value=2))
        self.lab.action(dict(action='pause')); self.assertTrue(self.lab.paused)
        self.lab.action(dict(action='stop')); self.assertFalse(self.lab.running)

if __name__=='__main__': unittest.main()
