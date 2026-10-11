"""Execute the changed Stalker/NPC patches with WeiDU on synthetic resources."""
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
from ranger_imoen_regressions import ROOT, MOD, cre


def run(weidu):
    stalker = (MOD / 'lib/stalker.tpa').read_text()
    npc = (ROOT / 'ArtisansKitpack_npc/ArtisansKitpack_npc.TP2').read_text()
    clab_patch = 'COPY_EXISTING ~CLABRN01.2DA~' + stalker.split('COPY_EXISTING ~CLABRN01.2DA~', 1)[1].split('ACTION_IF', 1)[0]
    hp_patch = stalker.split('// STALKER - HIT DIE', 1)[1].split('// STALKER - HLA', 1)[0]
    valyg_patch = stalker.split('// VALYGAR', 1)[1].split('ACTION_IF MOD_IS_INSTALLED', 1)[0]
    writes = re.findall(r'^\s*(WRITE_(?:BYTE|SHORT|LONG)\s+(0x(?:273|18|24|26))\b[^\r\n]*)', npc, re.M)
    assert len(writes) == 25, len(writes)
    for present in [('valyg8', 'valyg9', 'valyg11', 'valyg12', 'valyg14'), ('valyg9',)]:
        with tempfile.TemporaryDirectory(prefix='stalker-npc-') as temp:
            game = pathlib.Path(temp)
            override = game / 'override'
            override.mkdir()
            (game / 'regression').mkdir()
            (game / 'chitin.key').write_bytes(b'KEY V1  ' + struct.pack('<4I', 0, 0, 64, 64) + bytes(40))
            (game / 'dialog.tlk').write_bytes(b'TLK V1  ' + struct.pack('<HII', 0, 0, 18))
            (game / 'baldur.ini').write_text('[Alias]\nHD0:=./\n')
            (override / 'class.ids').write_text('IDS V1.0\n6 PALADIN\n3 CLERIC\n7 FIGHTER_MAGE\n19 SORCERER\n')
            hp = '2DA V1.0\n*\n TABLE\nRANGER HPWAR\nSTALKER\tHPWAR\nMAGE HPWIZ\n'
            (override / 'hpclass.2da').write_text(hp)
            headers = '2DA V1.0\n****\n ' + ' '.join(str(i) for i in range(1, 51)) + '\n'
            abilities = ['AP_C0RNG00', 'GA_C0CL922', 'AP_C0RNH1', 'AP_C0RNH20', 'GA_SPCL412', 'GA_SPCL311', 'AP_C0RNG01']
            for index, ability in enumerate(abilities):
                headers += f'A{index} ' + ' '.join([ability] + ['****'] * 49) + '\n'
            (override / 'clabrn01.2da').write_text(headers)
            originals = {}
            for name in present:
                data = cre(1, int(name[5:]), 12, name)
                originals[name] = data
                (override / (name + '.cre')).write_bytes(data)
            actions = f'''BACKUP ~regression/backup~
AUTHOR ~regression fixtures~
BEGIN ~Stalker and NPC regression fixtures~
OUTER_SPRINT MOD_FOLDER ~{MOD.as_posix()}~
INCLUDE ~%MOD_FOLDER%/lib/functions.tph~
{clab_patch}
{hp_patch}
{valyg_patch}
'''
            expected_writes = {}
            for index, (statement, field) in enumerate(writes):
                name = f'write{index}.cre'
                data = bytearray(cre(index % 2, 1, 4, 'TEST'))
                # Nonzero high bytes expose partial writes; adjacent sentinels expose overwrites.
                struct.pack_into('<I', data, 0x18, 0x12345678)
                struct.pack_into('<H', data, 0x24, 0x1234)
                struct.pack_into('<H', data, 0x26, 0x2345)
                data[0x272:0x276] = bytes([17, 4, 93, 2])
                expected = bytearray(data)
                symbol = re.search(r'~class~\s+~(\w+)~', statement)
                if symbol:
                    value = {'PALADIN': 6, 'CLERIC': 3, 'FIGHTER_MAGE': 7, 'SORCERER': 19}[symbol[1]]
                else:
                    value = int(statement.split()[2])
                offset = int(field, 16)
                width = {0x273: '<B', 0x18: '<I', 0x24: '<H', 0x26: '<H'}[offset]
                struct.pack_into(width, expected, offset, value)
                expected_writes[name] = bytes(expected)
                (override / name).write_bytes(data)
                actions += f'COPY_EXISTING ~{name}~ ~override~\n{statement}\n'
            (game / 'regression/setup-regression.tp2').write_text(actions)
            result = subprocess.run([weidu, 'regression/setup-regression.tp2', '--noautoupdate', '--no-exit-pause',
                                     '--force-install-list', '0'], cwd=game, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode or 'SUCCESSFULLY INSTALLED' not in result.stdout:
                print(result.stdout)
                raise AssertionError('WeiDU fixture failed')
            files = {p.name.lower(): p for p in override.iterdir()}
            for name, expected in expected_writes.items():
                assert files[name].read_bytes() == expected, name
            for name, original in originals.items():
                expected = bytearray(original)
                hp = {'valyg8':64, 'valyg9':72, 'valyg11':80, 'valyg12':92, 'valyg14':92}[name]
                struct.pack_into('<HH', expected, 0x24, hp, hp)
                assert files[name + '.cre'].read_bytes() == expected, name
            if 'valyg8' not in present:
                assert 'valyg8.cre' not in files
            rows = [line.split() for line in files['hpclass.2da'].read_text().splitlines()[3:]]
            assert rows == [['RANGER', 'HPWAR'], ['STALKER', 'HPARCH'], ['MAGE', 'HPWIZ']], rows
            tokens = files['clabrn03.2da'].read_text().split()
            assert not any(x in tokens for x in ('AP_C0RNG00', 'GA_C0CL922', 'AP_C0RNH1', 'AP_C0RNH20', 'GA_****', 'AP_****'))
            assert all(x in tokens for x in ('GA_C0STK01', 'AP_C0STK00', 'GA_SPCL412', 'GA_SPCL311', 'AP_C0RNG01'))
            print(f'PASS Stalker CLAB, whitespace-independent d8 mapping, Valygar {present}, and 25 exact NPC field writes')
    print('Installation transformations only; no engine behavior simulated.')


if __name__ == '__main__':
    run(str(pathlib.Path(sys.argv[1]).resolve()))
