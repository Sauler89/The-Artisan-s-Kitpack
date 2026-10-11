"""Run production WeiDU patches on synthetic 2DA/CRE fixtures (no game engine).
Usage: python3 tests/ranger_imoen_regressions.py /path/to/weidu
"""
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / 'ArtisansKitpack'


def cre(version, level, cls, dv, staff=0):
    data = bytearray(0x2d4)
    data[:8] = b'CRE V1.0'
    data[0x33] = version
    data[0x234] = level
    data[0x273] = cls
    data[0x280:0x280 + len(dv)] = dv.encode()
    for offset in (0x2a0, 0x2a8, 0x2b0, 0x2b8, 0x2bc):
        struct.pack_into('<I', data, offset, len(data))
    data += b'\xff' * 80  # empty item slots, equipped weapon and extra field
    struct.pack_into('<I', data, 0x2c4, len(data))
    effects = [(233, 1, 91), (233, 1, 105), (0, 2, 0)]
    if staff:
        effects.append((233, staff, 102))
    struct.pack_into('<I', data, 0x2c8, len(effects))
    for op, p1, p2 in effects:
        e = bytearray(264 if version else 48)
        if version:
            struct.pack_into('<I', e, 8, op)
            struct.pack_into('<II', e, 20, p1, p2)
            struct.pack_into('<I', e, 28, 9)
            struct.pack_into('<H', e, 36, 100)
        else:
            struct.pack_into('<H', e, 0, op)
            struct.pack_into('<II', e, 4, p1, p2)
            e[12], e[18] = 9, 100
        data += e
    return bytes(data)


def effects(data):
    offset, count = struct.unpack_from('<II', data, 0x2c4)
    version = data[0x33]
    stride, opoff, param = (264, 8, 20) if version else (48, 0, 4)
    return [(struct.unpack_from('<I' if version else '<H', data, offset + stride*i + opoff)[0],
             *struct.unpack_from('<II', data, offset + stride*i + param)) for i in range(count)]


def run(weidu):
    ranger = (MOD / 'lib/Ranger.tpa').read_text()
    # Check BOTH source schedules, then execute the actual base CLAB patch below.
    schedules = re.findall(r'f_MinLevel\s*=\s*(\d+)\s+STR_VAR f_Entry = AP_C0RNH(\d+)\b', ranger)
    assert len(schedules) == 100
    assert all(a == b for a, b in schedules), schedules
    clab_patch = 'COPY_EXISTING ~CLABRN01.2DA~' + ranger.split('COPY_EXISTING ~CLABRN01.2DA~', 1)[1].split('BUT_ONLY', 1)[0] + 'BUT_ONLY\n'
    npc = (ROOT / 'ArtisansKitpack_npc/ArtisansKitpack_npc.TP2').read_text()
    npc = npc.split('BEGIN ~Rogue Archer~ DESIGNATED 7101', 1)[1]
    npc_patch = 'COPY_EXISTING_REGEXP' + npc.split('COPY_EXISTING_REGEXP', 1)[1].split('BUT_ONLY', 1)[0] + 'BUT_ONLY\n'
    assert ranger.count('LAF c0_ensure_ranger_trap_limit STR_VAR c0_trap_name = EVAL ~%kit_label%~ END') == 1
    cases = {
        'missing': 'THIEF 6\n',
        'substring': 'CLERIC_RANGER 0\nTHIEF 6\n',
        'existing': 'RANGER 0\nFERALAN 0\nSTALKER 9\nBEASTMASTER *\nTHIEF 6\nCUSTOM_RANGER 0\n',
    }
    for label, table in cases.items():
        with tempfile.TemporaryDirectory(prefix='ranger-regression-') as temp:
            game = pathlib.Path(temp)
            override = game / 'override'
            override.mkdir()
            (game / 'regression').mkdir()
            (game / 'chitin.key').write_bytes(b'KEY V1  ' + struct.pack('<4I', 0, 0, 64, 64) + bytes(40))
            (game / 'dialog.tlk').write_bytes(b'TLK V1  ' + struct.pack('<HII', 0, 0, 18))
            (game / 'baldur.ini').write_text('[Alias]\nHD0:=./\n')
            (override / 'traplimt.2da').write_text('2DA V1.0\n0\n LIMIT\n' + table)
            (override / 'kit.ids').write_text('IDS V1.0\n0x4001 C0ADVENT\n')
            clab = '2DA V1.0\n****\n ' + ' '.join(str(n) for n in range(1, 51)) + '\n'
            clab += 'ABILITY1 ' + ' '.join(['****'] * 50) + '\n'
            (override / 'clabrn01.2da').write_text(clab)
            original = {}
            for version in (0, 1):
                for name, level, cls, dv, staff in [('im1', 1, 4, 'Imoen', 0),
                                                   ('im4', 4, 4, 'IMOEN', 1),
                                                   ('dual', 1, 13, 'IMOEN2', 1),
                                                   ('other', 1, 4, 'OTHER', 0)]:
                    filename = f'{name}v{version}.cre'
                    original[filename] = cre(version, level, cls, dv, staff)
                    (override / filename).write_bytes(original[filename])
            actions = f'''BACKUP ~regression/backup~
AUTHOR ~regression fixtures~
BEGIN ~Ranger and Imoen regression fixtures~
OUTER_SPRINT MOD_FOLDER ~{MOD.as_posix()}~
INCLUDE ~%MOD_FOLDER%/lib/functions.tph~
'''
            for _ in range(2):
                actions += '''INCLUDE ~%MOD_FOLDER%/lib/ranger_trap_limits.tpa~
LAF c0_ensure_ranger_trap_limit STR_VAR c0_trap_name = ~CUSTOM_RANGER~ END
'''
                actions += npc_patch
            actions += clab_patch
            (game / 'regression/setup-regression.tp2').write_text(actions)
            result = subprocess.run([weidu, 'regression/setup-regression.tp2', '--noautoupdate',
                                     '--no-exit-pause', '--force-install-list', '0'], cwd=game,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode or 'SUCCESSFULLY INSTALLED' not in result.stdout:
                print(result.stdout)
                raise AssertionError('WeiDU fixture installation failed')
            files = {p.name.lower(): p for p in override.iterdir()}
            rows = [line.split() for line in files['traplimt.2da'].read_text().splitlines()[3:] if line.strip()]
            for name in ('RANGER', 'CLERIC_RANGER', 'FERALAN', 'STALKER', 'BEASTMASTER', 'CUSTOM_RANGER'):
                matched = [r for r in rows if r[0].upper() == name]
                assert len(matched) == 1, (label, name, rows)
                expected = '9' if label == 'existing' and name == 'STALKER' else '3'
                assert matched[0][1] == expected, (label, name, matched)
            assert ['THIEF', '6'] in rows
            clab_rows = [line.split()[1:] for line in files['clabrn01.2da'].read_text().splitlines()[3:] if line.strip()]
            for level in range(1, 51):
                resource = f'AP_C0RNH{level}'
                occurrences = [col + 1 for row in clab_rows for col, cell in enumerate(row) if cell == resource]
                assert occurrences == [level], (level, occurrences)
            for name, source in original.items():
                data = files[name].read_bytes()
                if name.startswith('other'):
                    assert data == source
                    continue
                fx = effects(data)
                prof = {p2: p1 for op, p1, p2 in fx if op == 233}
                expected = {91: 1, 105: 1 if name.startswith('im1') else 2}
                assert prof == expected, (name, prof)
                assert (0, 2, 0) in fx  # unrelated effect preserved
                assert struct.unpack_from('<H', data, 0x246)[0] == 0x4001
            print(f'PASS {label}: exact trap rows/idempotence, 50 HP grant levels, V1/V2 Imoen CREs and unrelated NPCs')
    print('No game engine, rest behavior or level-1 Toughness runtime has been simulated.')


if __name__ == '__main__':
    run(str(pathlib.Path(sys.argv[1]).resolve()))
