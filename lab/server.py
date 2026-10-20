#!/usr/bin/env python3
"""Loopback-only AUV lab. Native firmware core + virtual water, optional Nano USB.
Run: python3 lab/server.py (requires C++ compiler and pyserial for USB mode).
"""
import argparse
from collections import deque
import ctypes
import csv
import io
import json
import math
from pathlib import Path
import random
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
TOKEN = secrets.token_urlsafe(24)
DEFAULTS = dict(center=0.5, width=0.07, drop=3.0, tau=2.0, noise=0.005, shape='layer', profile_x=4.0)
FIELDS = ['seq', 'ms', 'state', 'faults', 'depth_m', 'temperature_c', 'true_temperature_c',
          'vertical_mps', 'command', 'target_depth_m', 'speed_limit_mps', 'gradient_cpm',
          'gradient_valid', 'transition', 'mode', 'voltage_v', 'current_a', 'energy_j', 'profile_x_m', 'x_m', 'surge', 'explore_phase', 'explore_visits', 'gradient_x_cpm', 'gradient_depth_cpm', 'gradient_2d_valid', 'explore_reason', 'controller_source', 'field_shape', 'probe_tau_s', 'field_center_m', 'field_width_m', 'field_drop_c', 'input_ms', 'input_temperature_c', 'input_x_m', 'input_depth_m', 'input_vx_mps', 'input_vz_mps', 'vx_mps', 'travel_m', 'local_exit', 'trajectory_policy', 'known_cells', 'thermal_rechecks']
LIMITS = dict(center=(0.2, 2.2), width=(0.03, 0.2), drop=(0, 6), tau=(0.1, 8), noise=(0, 0.05), profile_x=(0.5, 7.5))

CONFIG_KEYS = ['target_depth_m', 'max_depth_m', 'normal_speed_mps', 'slow_speed_mps', 'probe_tau_s', 'allowed_lag_m', 'gradient_window_m', 'gradient_enter_cpm', 'gradient_exit_cpm', 'control_ms', 'telemetry_ms', 'mission_timeout_ms', 'water_center_m', 'water_width_m', 'water_drop_c', 'water_surface_c', 'water_shape', 'profile_x_m']
SHAPES = {'layer':0, 'tilted':1, 'front':2, 'patch':3, 'combined':4}

def select_serial_port(ports, explicit=None):
    """Select a USB adapter; the HELLO handshake subsequently verifies firmware."""
    if explicit:
        matches=[p for p in ports if p.device==explicit]
    else:
        adapters={(0x0403,0x6001),(0x1A86,0x7523),(0x1A86,0x5523),(0x10C4,0xEA60)}
        matches=[p for p in ports if (p.vid,p.pid) in adapters]
    if len(matches)!=1:
        raise ValueError('Connect one Nano USB adapter, or restart with --serial-port PORT to select it explicitly.')
    return matches[0].device

class Lab:
    def __init__(self, serial_port=None):
        self.serial_port_override=serial_port
        build = PROJECT / 'build/lab'
        build.mkdir(parents=True, exist_ok=True)
        subprocess.run(['c++', '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', str(ROOT/'controller_bridge.cpp'), '-o', str(build/'core.so')], check=True)
        self.core = ctypes.CDLL(str(build/'core.so'))
        self.core.lab_tick.argtypes = [ctypes.c_uint32, ctypes.c_float,
                                     ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
        values = (ctypes.c_float * len(CONFIG_KEYS))()
        self.core.lab_config.argtypes = [ctypes.POINTER(ctypes.c_float)]
        assert self.core.lab_config(values) == len(CONFIG_KEYS)
        self.native_config = dict(zip(CONFIG_KEYS, values))
        self.firmware_config = {}
        self.core.lab_water.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        self.core.lab_water.restype = ctypes.c_float
        self.core.lab_explore_tick.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
        self.explore_sequence = 0
        self.lock = threading.RLock()
        self.serial = None
        self.source = 'offline'
        self.connected = False
        self.verified = False
        self.error = ''
        self.buffer = bytearray()
        self.header = None
        self.last_rx = 0
        self.connect_started = 0
        self.last_hello = 0
        self.identity = ''
        self.port = ''
        self.params = DEFAULTS.copy()
        self.mode = 0
        self.speed = 1
        self.console = deque(maxlen=500)
        self.console_seq = 0
        self.events = deque(maxlen=12)
        self.reset()
        threading.Thread(target=self.worker, daemon=True).start()

    def log(self, origin, message, kind='message'):
        self.console_seq += 1
        self.console.append(dict(id=self.console_seq, time=time.strftime('%H:%M:%S'),
                                 origin=origin, kind=kind, text=str(message)[:2048]))

    def send(self, payload):
        if not self.serial: raise ValueError('Nano is disconnected')
        self.serial.write(payload)
        for line in payload.decode('ascii').splitlines(): self.log('TX', line, 'telemetry' if line.startswith('OBS,') else 'command')

    def event(self, message):
        self.log('BRIDGE', message)
        self.events.appendleft(dict(time=round(self.ms/1000, 1), text=message))

    def reset(self):
        self.explore_last_worker=time.monotonic()
        self.exploring = False
        self.explore_pending = None
        self.explore_reply = None
        self.explore_status = {}
        self.explore_adaptive=True
        self.explore_x=2.0; self.explore_z=.2; self.explore_vx=self.explore_vz=0.0
        self.core.lab_reset(self.mode)
        self.ms = 0
        self.depth = self.velocity = self.command = self.energy = 0.0
        self.measured = self.truth = 22.0
        self.rows = deque(maxlen=10000)
        self.seq = 0
        self.running = self.paused = False
        self.fault = ''
        self.latest = None
        self.random = random.Random(42)
        self.previous_event = None
        self.events.clear()

    def disconnect(self):
        self.explore_pending = None
        self.explore_reply = None
        link, was_verified = self.serial, self.verified
        self.serial = None
        self.connected = self.verified = self.running = False
        self.header = None
        self.identity = ''
        self.firmware_config = {}
        self.connect_started = 0
        self.banner_seen = False
        self.buffer.clear()
        if link:
            try:
                if was_verified:
                    link.write(b'DISARM\n')
                    self.log('TX', 'DISARM', 'command')
                link.flush()
            except OSError as e:
                self.log('BRIDGE', 'USB cleanup: ' + str(e), 'error')
            finally:
                try: link.close()
                except OSError: pass
            self.log('BRIDGE', 'USB closed')

    def connect(self):
        import serial
        from serial.tools import list_ports
        port=select_serial_port(list_ports.comports(),self.serial_port_override)
        self.disconnect()
        self.serial = serial.Serial(port,115200,timeout=0,write_timeout=1,exclusive=True)
        self.serial.dtr = False
        time.sleep(0.2)
        self.serial.reset_input_buffer()
        self.serial.dtr = True
        self.connected = True
        self.port = port
        self.connect_started = time.monotonic()
        self.last_hello = 0
        self.last_rx = self.connect_started
        self.error = ''
        self.event('USB open · requesting Nano firmware identity')

    def exploration_params(self, body):
        updated=self.params.copy()
        for key,(low,high) in LIMITS.items():
            value=float(body.get(key,updated[key]))
            if not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid '+key)
            updated[key]=value
        shape=body.get('shape',updated['shape'])
        if shape not in SHAPES:raise ValueError('Unknown water shape')
        updated['shape']=shape;updated['noise']=0
        return updated

    def action(self, body):
        with self.lock:
            action = body.get('action')
            if action == 'source':
                if body.get('value') not in ('offline', 'nano'): raise ValueError('Unknown source')
                self.disconnect()
                self.source = body['value']
                self.reset()
                self.error = ''
                self.event('Source: ' + self.source)
            elif action == 'connect':
                if self.source != 'nano': raise ValueError('Select Nano first')
                self.connect()
            elif action == 'disconnect':
                self.disconnect(); self.running = False
            elif action == 'explore_field':
                if self.running:raise ValueError('Stop exploration before changing water')
                updated=self.exploration_params(body)
                if self.source=='nano' and self.verified:self.send(b'DISARM\n')
                self.reset();self.params=updated;self.exploring=True
                self.explore_status=dict(active=False,reason=0,phase='field ready',
                    controller='Nano USB' if self.source=='nano' else 'Native C++')
                self.event('Exploration water: '+updated['shape']+'; layer drop '+str(updated['drop'])+' C')
            elif action == 'explore_start':
                if self.running: raise ValueError('Stop the current run first')
                if self.source == 'nano' and (not self.verified or time.monotonic()-self.last_rx>2 or not self.identity.startswith('v0.12')):
                    raise ValueError('Exploration needs Nano firmware v0.12, connected and verified')
                updated=self.exploration_params(body)
                shape=updated['shape']
                adaptive=body.get('adaptive',True)
                if adaptive is not True:raise ValueError('Sweep policies removed; use vertical exploration')
                self.reset();self.explore_adaptive=adaptive;self.params=updated;self.exploring=True;self.running=True
                self.explore_x=updated['profile_x']
                self.measured=self.core.lab_water(self.explore_x,self.explore_z,SHAPES[shape],updated['center'],updated['width'],updated['drop'])
                if self.source=='nano':self.send(f'DISARM\nEXPL,{int(adaptive)},{updated["tau"]:.3f}\n'.encode('ascii'))
                else:
                    self.core.lab_explore_begin()
                    # This tau is sensor characterization supplied to the controller, not truth.
                    self.core.lab_explore_tau(ctypes.c_float(updated['tau']))
                self.event('Nano-in-the-loop exploration' if self.source=='nano' else 'Native firmware exploration · same C++ controller')
            elif action == 'diagnostics':
                if self.source != 'nano' or not self.verified: raise ValueError('Connect and verify Nano first')
                self.send(b'HELLO\nSTATUS\n')
            elif action == 'field':
                if self.running: raise ValueError('Reset before changing the field')
                shape = body.get('shape', self.params['shape'])
                x = float(body.get('profile_x', self.params['profile_x']))
                if shape not in SHAPES or not math.isfinite(x) or not .5 <= x <= 7.5: raise ValueError('Invalid field selection')
                if self.source == 'nano':
                    if not self.verified or time.monotonic()-self.last_rx>2 or not self.identity.startswith(('v0.5','v0.6','v0.7','v0.12')): raise ValueError('Upload firmware v0.5 to select fields on Nano')
                    self.send(f'DISARM\nWATER{SHAPES[shape]}\nX{x:.3f}\nCONFIG\n'.encode('ascii'))
                self.params.update(shape=shape, profile_x=x)
                self.reset()
                self.event(f'Field: {shape}; vertical profile at x={x:.2f} m')
            elif action == 'configure':
                if self.running: raise ValueError('Reset the run before changing the experiment')
                if self.source != 'offline': raise ValueError('Environment controls apply to offline water only')
                updated = self.params.copy()
                shape = body.get('shape', self.params['shape'])
                if shape not in SHAPES: raise ValueError('Unknown water shape')
                updated['shape'] = shape
                for key, (low, high) in LIMITS.items():
                    value = float(body.get(key, self.params[key]))
                    if not math.isfinite(value) or not low <= value <= high: raise ValueError('Invalid ' + key)
                    updated[key] = value
                mode = int(body.get('mode', self.mode))
                if mode not in (0, 1, 2): raise ValueError('Invalid mode')
                self.mode = mode
                self.params = updated
                self.reset()
            elif action == 'speed':
                value = int(body.get('value', 1))
                if self.source != 'offline' or value not in (1, 4, 10): raise ValueError('Offline speed only')
                self.speed = value
            elif action == 'mode':
                if self.running: raise ValueError('Reset before changing mode')
                mode = int(body.get('value', 0))
                if mode not in (0, 1, 2): raise ValueError('Invalid mode')
                self.mode = mode
                if self.source == 'offline': self.core.lab_reset(mode)
            elif action == 'start':
                if self.running: raise ValueError('Run already active')
                if self.source == 'nano':
                    if not self.verified or time.monotonic()-self.last_rx > 2: raise ValueError('Connect and verify the Nano first')
                    self.send(b'DISARM\n' + [b'ADAPT\n', b'FAST\n', b'SLOW\n'][self.mode] + b'DEMO\n')
                    self.rows.clear(); self.seq = 0; self.energy = 0
                else:
                    self.reset()
                    if not self.core.lab_arm(0): raise ValueError('Controller rejected arm')
                self.running = True
                self.event('Profile started · 5 s arming wait')
            elif action == 'pause':
                if not self.running: raise ValueError('No active run')
                if self.source!='offline' and not self.exploring:raise ValueError('Pause is available in offline runs')
                if self.exploring and self.source=='nano':raise ValueError('Use Stop for Nano exploration; observations must stay live')
                self.paused = not self.paused
            elif action in ('stop', 'reset'):
                if self.source == 'nano' and self.verified:
                    self.send(b'STOP\n' if action == 'stop' else b'DISARM\n')
                if action == 'stop':
                    self.core.lab_stop(); self.running = self.paused = False
                    if self.latest:
                        self.latest = dict(self.latest, state=6, faults=512, command=0,surge=0,explore_reason=4)
                    if self.exploring:self.explore_status.update(active=False,local=False,reason=4,surge=0,heave=0)
                    self.event('Operator STOP · motors disabled')
                else: self.reset(); self.event('Reset · disarmed')
            elif action == 'fault':
                if self.source != 'offline' or not self.running or self.exploring: raise ValueError('Fault injection needs an offline profile run')
                if body.get('value') not in ('leak', 'stale', 'battery', 'tilt'): raise ValueError('Unknown fault')
                self.fault = body['value']
                self.event('Injected fault: ' + self.fault)
            else: raise ValueError('Unknown action')

    def append(self, values):
        self.seq += 1
        row = dict(zip(FIELDS[1:], values))
        row['seq'] = self.seq
        self.latest = row
        self.rows.append(row)
        key = (row['state'], row['transition'],row.get('explore_phase'))
        if key != self.previous_event:
            names = ['Disarmed', 'Arming', 'Descending', 'Depth hold', 'Ascending', 'Complete', 'Fault']
            self.event(('Gradient following' if row.get('explore_phase')=='follow' else 'Slow upward retrace' if row.get('explore_phase')=='backtrack' else 'Local geometry probe' if row['transition'] else 'Vertical descent') if self.exploring and row['state']==2 else names[int(row['state'])] + (' · temperature transition' if row['transition'] else ''))
            self.previous_event = key
        if row['state'] in (5, 6): self.running = False

    def exploration_tick(self):
        if self.paused:return
        now=time.monotonic()
        if self.explore_pending is not None:
            if self.explore_reply is None:
                if now-self.explore_sent>1.5:raise ValueError('Nano exploration reply timeout; simulation stopped')
                return
            out=self.explore_reply;self.explore_pending=None;self.explore_reply=None
        elif self.source=='nano':
            self.explore_sequence=self.explore_sequence%4294967295+1;self.explore_pending=self.explore_sequence;self.explore_sent=now
            # Only measured temperature, estimated position/velocity and time cross USB.
            self.send((f'OBS,{self.explore_sequence},{self.ms%4294967296},{self.explore_x:.4f},{self.explore_z:.4f},'
                       f'{self.explore_vx:.4f},{self.explore_vz:.4f},{self.measured:.4f}\n').encode('ascii'))
            return
        else:
            inputs=(ctypes.c_float*5)(*[round(v,4) for v in (self.explore_x,self.explore_z,self.explore_vx,self.explore_vz,self.measured)])
            values=(ctypes.c_float*16)();self.core.lab_explore_tick(self.ms%4294967296,inputs,values);out=[round(float(v),4) for v in values]
        input_values=[self.measured,self.explore_x,self.explore_z,self.explore_vx,self.explore_vz]
        input_values=[round(v,4) for v in input_values]
        input_ms=self.ms
        active,local,reason,surge,heave,tx,tz,gx,gz,valid,visits,mission_phase,travel,local_exit,known_cells,rechecks=out
        self.explore_status=dict(active=bool(active),local=bool(local),reason=int(reason),target_x=tx,target_z=tz,
            surge=surge,heave=heave,gx=gx,gz=gz,gradient_valid=bool(valid),visits=int(visits),mission_phase=int(mission_phase),travel=travel,local_exit=int(local_exit),known_cells=int(known_cells),rechecks=int(rechecks),phase={0:'vertical profiling',1:'slow upward retrace',2:'local geometry probe',3:'local gradient investigation',4:'complete',5:'hold (maximum 8 s)',6:'moving to unvisited water',7:'domain sampled; awaiting Stop'}[int(mission_phase)],policy='vertical',
            controller='Nano USB' if self.source=='nano' else 'Native C++',sequence=self.explore_sequence)
        # Freeze the plant if the controller has terminated; never reuse a stale request.
        if active:
            for _ in range(2):
                dt=.05
                self.explore_vx+=(.8*surge-1.4*self.explore_vx)*dt
                self.explore_vz+=(.6*heave-1.8*self.explore_vz-.018)*dt
                self.explore_x+=self.explore_vx*dt;self.explore_z+=self.explore_vz*dt
                self.explore_x=max(.2,min(7.8,self.explore_x));self.explore_z=max(.08,min(2.85,self.explore_z))
                p=self.params
                self.truth=self.core.lab_water(self.explore_x,self.explore_z,SHAPES[p['shape']],p['center'],p['width'],p['drop'])
                self.measured+=(self.truth-self.measured)*(1-math.exp(-dt/p['tau']))
            self.ms+=100
        else:surge=heave=0
        state=2 if active else (5 if int(reason) in (1,2) else 6)
        self.append([self.ms,state,0,self.explore_z,self.measured,self.truth,self.explore_vz,heave,tz,
            .10 if int(mission_phase) in (0,6) else min(.04,.08/self.params['tau']) if local==1 else min(.08,.1/self.params['tau']),0,0,int(bool(local)),0,12,0,0,self.explore_x,
            self.explore_x,surge,'complete' if not active else 'transit' if mission_phase==6 else 'exhausted' if mission_phase==7 else 'monitor' if mission_phase==5 else 'follow' if local==3 else 'probe' if local==2 else 'backtrack' if local==1 else 'descend',int(visits),gx,gz,int(valid),int(reason),
            'nano_v0.12_lab_plant' if self.source=='nano' else 'native_v0.12_lab_plant',self.params['shape'],self.params['tau'],self.params['center'],self.params['width'],self.params['drop'],input_ms,*input_values,self.explore_vx,travel,int(local_exit),'vertical_then_local',int(known_cells),int(rechecks)])

    def offline_tick(self):
        dt = 0.05
        self.ms += 50
        self.velocity += (self.command * 1.2 - self.velocity * 1.5 - 0.01) * dt
        self.depth += self.velocity * dt
        if self.depth <= 0: self.depth = self.velocity = 0
        p = self.params
        self.truth = self.core.lab_water(p['profile_x'], self.depth, SHAPES[p['shape']], p['center'], p['width'], p['drop'])
        self.measured += (self.truth-self.measured) * (1-math.exp(-dt/p['tau']))
        temp = self.measured + self.random.gauss(0, p['noise'])
        voltage = 9 if self.fault == 'battery' else 12
        current = abs(self.command) * 4
        self.energy += voltage * current * dt # Toy propulsion-only energy, not battery sizing.
        sample_ms = self.ms-1000 if self.fault == 'stale' else self.ms
        inputs = (ctypes.c_float*9)(max(0, sample_ms), temp, self.depth, self.velocity, voltage,
                                    current, 40 if self.fault == 'tilt' else 0, 1, self.fault == 'leak')
        outputs = (ctypes.c_float*9)()
        self.core.lab_tick(self.ms, dt, inputs, outputs)
        state, faults, self.command, target, speed, gradient, valid, transition, mode = outputs
        self.append([self.ms, int(state), int(faults), self.depth, temp, self.truth, self.velocity,
                     self.command, target, speed, gradient, int(valid), int(transition), int(mode),
                     voltage, current, self.energy, p['profile_x']])

    def serial_tick(self):
        if not self.serial: return
        now = time.monotonic()
        if not self.verified and self.connect_started:
            if now-self.connect_started > 8:
                raise ValueError('USB opened but firmware handshake timed out. Expected AUV firmware v0.5; close other serial monitors and reconnect.')
            if now-self.last_hello >= 0.75:
                self.send(b'HELLO\n')
                self.last_hello = now
        self.buffer.extend(self.serial.read(min(self.serial.in_waiting, 8192)))
        while b'\n' in self.buffer:
            line, _, self.buffer = self.buffer.partition(b'\n')
            line = line.decode('ascii', errors='replace').strip()
            if line: self.log('NANO', line, 'telemetry' if line[:1].isdigit() or line.startswith('# EXP,') else 'message')
            if line.startswith(('# AUV Nano adaptive v0.12;', '# AUV Nano adaptive v0.7;', '# AUV Nano adaptive v0.6;', '# AUV Nano adaptive v0.5;', '# AUV Nano adaptive v0.4;', '# AUV Nano adaptive v0.3;')):
                if '; simulated=1; motors=0' not in line:
                    raise ValueError('Nano must use simulated sensors and disabled motor outputs for this lab')
                self.banner_seen = True
                self.identity = line.split(';')[0].removeprefix('# AUV Nano adaptive ') + ' · simulated sensors · motors disabled'
            elif line.startswith('# AUV Nano adaptive v0.2;'):
                self.banner_seen = True
                self.identity = 'v0.2 · legacy startup handshake'
            if line.startswith('# CONFIG,') and getattr(self, 'banner_seen', False):
                pairs = dict(part.split('=', 1) for part in line[9:].split(','))
                expected = set(CONFIG_KEYS)
                legacy = expected - {'water_shape', 'profile_x_m'}
                if set(pairs) != expected and not (self.identity.startswith('v0.4') and set(pairs) == legacy): raise ValueError('Incomplete firmware configuration')
                parsed = {key: float(value) for key,value in pairs.items()}
                if not all(math.isfinite(v) and 0 <= v < 1e7 for v in parsed.values()):
                    raise ValueError('Invalid firmware configuration')
                if 'water_shape' in parsed and parsed['water_shape'] not in range(5): raise ValueError('Invalid water shape')
                if any(parsed[k] <= 0 for k in parsed if k not in ('water_shape', 'water_drop_c')): raise ValueError('Invalid firmware configuration')
                if 'profile_x_m' in parsed and not .5 <= parsed['profile_x_m'] <= 7.5: raise ValueError('Invalid profile position')
                self.firmware_config = parsed
            if line.startswith('ms,sample_ms,'):
                self.header = line.split(',')
                if len(self.header) != 27: raise ValueError('Unsupported firmware schema')
            if line.startswith('# EXP,'):
                parts=line[6:].split(',')
                if len(parts)!=17:raise ValueError('Invalid exploration output frame')
                values=[float(v) for v in parts]
                if not all(math.isfinite(v) for v in values):raise ValueError('Invalid exploration numbers')
                sequence=int(values[0]);out=values[1:]
                if out[0] not in (0,1) or out[1] not in (0,1,2,3,5) or not 0<=out[2]<=5 or abs(out[3])>1 or abs(out[4])>1 or not .39<=out[5]<=7.61 or not .19<=out[6]<=2.71:raise ValueError('Invalid exploration motion request')
                if out[11] not in (0,1,2,3,4,5,6,7) or not 0<=out[14]<=1536 or not 0<=out[15]<=65535:raise ValueError('Invalid exploration memory status')
                if self.exploring and sequence==0 and not out[0]:raise ValueError('Nano stopped exploration: observation link timeout')
                if self.exploring and sequence==self.explore_pending:self.explore_reply=out
            if line[:1].isdigit() and self.header:
                vals = line.split(',')
                if len(vals) != 27: continue
                r = dict(zip(self.header, vals))
                if r['simulated'] != '1': raise ValueError('Lab accepts simulated firmware only')
                if not getattr(self, 'banner_seen', False): continue
                if not self.verified: self.event('Nano verified · live USB telemetry')
                self.verified = True
                self.last_rx = time.monotonic()
                if self.exploring:continue
                stamp = int(r['ms'])
                elapsed = max(0, min((stamp-self.ms)/1000, 1))
                self.ms = stamp
                v, a = float(r['voltage_v']), float(r['current_a'])
                self.energy += v*a*elapsed
                self.append([stamp, int(r['state']), int(r['faults']), float(r['depth_m']),
                    float(r['temp_c']), None, float(r['vertical_mps']), float(r['vertical_cmd']),
                    float(r['target_depth_m']), float(r['speed_limit_mps']), float(r['gradient_cpm']),
                    int(r['gradient_valid']), int(r['transition']), int(r['mode']), v, a, self.energy, self.firmware_config.get('profile_x_m', 4.0)])

        if len(self.buffer) > 16384:
            if self.verified: raise ValueError('Serial frame overflow; reconnect Nano')
            self.buffer.clear()  # Discard unframed startup noise before the banner.

    def worker(self):
        while True:
            time.sleep(0.05)
            with self.lock:
                try:
                    if self.source == 'nano': self.serial_tick()
                    if self.exploring and self.running and (self.source=='nano' or time.monotonic()-self.explore_last_worker>=.1):
                        self.explore_last_worker=time.monotonic()
                        for _ in range(1 if self.source=='nano' else self.speed):
                            if self.running:self.exploration_tick()
                    elif not self.exploring and self.source=='offline' and self.running and not self.paused:
                        for _ in range(self.speed):
                            if self.running: self.offline_tick()
                except Exception as e:
                    self.error = str(e); self.running = False
                    self.log('BRIDGE', self.error, 'error')
                    if self.latest:self.latest=dict(self.latest,command=0,surge=0,state=6)
                    self.disconnect()

    def snapshot(self, since, console_since=0):
        with self.lock:
            return dict(source=self.source, connected=self.connected, verified=self.verified,
                stale=self.connected and self.verified and time.monotonic()-self.last_rx > 2, error=self.error,
                identity=self.identity, port=self.port,exploring=self.exploring,exploration=self.explore_status,
                console=[entry for entry in self.console if entry['id'] > console_since],
                console_seq=self.console_seq,
                running=self.running, paused=self.paused, mode=self.mode, speed=self.speed,
                params=self.params, latest=self.latest, seq=self.seq,
                firmware_config=dict(self.native_config, water_center_m=self.params['center'], water_width_m=self.params['width'], water_drop_c=self.params['drop'], water_shape=SHAPES[self.params['shape']], profile_x_m=self.params['profile_x']) if self.source == 'offline' else (self.firmware_config if self.verified else {}),
                config_source='native C++ core' if self.source == 'offline' else 'Nano USB CONFIG',
                rows=[r for r in self.rows if r['seq'] > since][-(10000 if since == 0 else 500):], events=list(self.events))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def response(self, data, status=200, mime='application/json'):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers(); self.wfile.write(raw)
    def authorized(self):
        return self.headers.get('X-Lab-Token') == TOKEN
    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
    def do_GET(self):
        if not self.valid_host(): return self.response({'error':'Host rejected'},403)
        url = urlparse(self.path)
        if url.path.startswith('/api/'):
            if not self.authorized(): return self.response({'error':'Unauthorized'},403)
            if url.path == '/api/state':
                try:
                    query = parse_qs(url.query)
                    since = max(0, int(query.get('since',['0'])[0]))
                    console_since = max(0, int(query.get('console_since',['0'])[0]))
                except ValueError: return self.response({'error':'Invalid sequence'},400)
                return self.response(lab.snapshot(since, console_since))
            if url.path == '/api/comparison':
                path=PROJECT/'output/experiments/exploration_comparison.json'
                return self.response(json.loads(path.read_text()) if path.exists() else [])
            if url.path == '/api/export':
                with lab.lock:
                    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=FIELDS)
                    writer.writeheader(); writer.writerows(lab.rows)
                return self.response(output.getvalue().encode(),mime='text/csv')
            return self.response({'error':'Not found'},404)
        paths = {'/':'index.html','/app.js':'app.js','/style.css':'style.css',
                 '/demo2d':'index.html','/demo2d/':'index.html','/demo2d.mjs':'demo2d.mjs',
                 '/survey-planner.mjs':'survey-planner.mjs','/thermal-map.mjs':'thermal-map.mjs','/keyboard.mjs':'keyboard.mjs','/demo-model.mjs':'demo-model.mjs','/demo2d.css':'demo2d.css'}
        if url.path not in paths: return self.response({'error':'Not found'},404)
        name = paths[url.path]
        raw = (ROOT/'static'/name).read_bytes()
        if name == 'index.html': raw = raw.replace(b'__TOKEN__',TOKEN.encode())
        mime = 'text/html; charset=utf-8' if name.endswith('.html') else ('text/css' if name.endswith('.css') else 'text/javascript')
        self.response(raw,mime=mime)
    def do_POST(self):
        if not self.valid_host(): return self.response({'error':'Host rejected'},403)
        if not self.authorized(): return self.response({'error':'Unauthorized'},403)
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.response({'error':'Origin rejected'},403)
        if self.path != '/api/action': return self.response({'error':'Not found'},404)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length < 4096: raise ValueError('Invalid request size')
            lab.action(json.loads(self.rfile.read(length)))
            self.response({'ok':True})
        except (ValueError, OSError, ImportError) as e:
            with lab.lock: lab.log('BRIDGE', 'Action rejected: ' + str(e), 'error')
            self.response({'error':str(e)},400)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--serial-port',help='Explicit USB serial device, e.g. /dev/ttyUSB0')
    args = parser.parse_args()
    lab = Lab(serial_port=args.serial_port)
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'AUV lab ready: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        with lab.lock: lab.disconnect()
        server.server_close()
