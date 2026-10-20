"""Run the motor-disabled v0.5 simulator on the identified project Nano.
Requires pyserial. Never enables physical motor outputs. Leaves firmware disarmed.
"""
import csv
from pathlib import Path
import time
import serial
from serial.tools import list_ports

project = Path(__file__).resolve().parents[1]
log = project / 'output/logs/nano_adaptive_demo.txt'
ports=[p for p in list_ports.comports() if (p.vid,p.pid) in {(0x0403,0x6001),(0x1a86,0x7523)}]
assert len(ports)==1,'Connect exactly one supported Nano adapter'
with serial.Serial(ports[0].device, 115200, timeout=0.1, exclusive=True) as link:
    link.dtr = False
    time.sleep(0.2)
    link.reset_input_buffer()
    link.dtr = True
    buffer = bytearray()
    records = []
    header = None
    seen_version = False
    started = False
    complete = False
    slowed = False
    saw_states = set()
    previous = None
    rows = 0
    deadline = time.monotonic() + 195
    try:
        while time.monotonic() < deadline:
            buffer.extend(link.read(min(max(link.in_waiting, 1), 512)))
            while b'\n' in buffer:
                raw, _, buffer = buffer.partition(b'\n')
                line = raw.decode('ascii', errors='replace').strip()
                if not line:
                    continue
                records.append(line)
                if line.startswith('# AUV Nano adaptive v0.'):
                    seen_version = True
                if line.startswith('ms,sample_ms,'):
                    header = line.split(',')
                    assert len(header) == 27, 'Unexpected telemetry schema'
                if seen_version and header and not started:
                    link.write(b'DISARM\nADAPT\nDEMO\n')
                    started = True
                if header and line[:1].isdigit():
                    fields = line.split(',')
                    assert len(fields) == len(header), 'Malformed row'
                    row = dict(zip(header, fields))
                    rows += 1
                    assert row['simulated'] == '1', 'Expected simulation only'
                    assert row['left_cmd'] == row['right_cmd'] == '0'
                    assert int(row['faults']) == 0, 'Unexpected firmware fault'
                    state = int(row['state'])
                    saw_states.add(state)
                    if row['transition'] == '1' and state in (2, 4):
                        assert float(row['speed_limit_mps']) <= 0.0201
                        slowed = True
                    event = (state, row['transition'])
                    if event != previous:
                        print('ms={}, state={}, transition={}, speed_limit={}'.format(
                            row['ms'], state, row['transition'], row['speed_limit_mps']), flush=True)
                        previous = event
                    if state == 5:
                        complete = True
                        break
            if complete:
                break
            if not started and len(records) > 30:
                raise AssertionError('Expected v0.5 startup not observed')
        assert complete and slowed and {1, 2, 3, 4, 5}.issubset(saw_states), 'Incomplete adaptive demonstration'
        link.write(b'DISARM\n')
        end = time.monotonic() + 2
        acknowledged = False
        while time.monotonic() < end:
            if link.readline().strip() == b'# disarmed':
                acknowledged = True
                break
        assert acknowledged, 'Disarm acknowledgment missing'
        print('PASS: {} rows; full adaptive mission, slow region, disarm acknowledged'.format(rows), flush=True)
    finally:
        link.write(b'DISARM\n')
        link.flush()
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('\n'.join(records) + '\n')
        print('Saved', log, flush=True)
