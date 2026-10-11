"""Execute Nalia/Xan production patches with relocated CRE spell tables."""
import collections
import pathlib
import struct
import subprocess
import sys
import tempfile
from ranger_imoen_regressions import ROOT, cre, effects


SPELLS = [
    ['SPWI106', 'SPWI112', 'SPWI114', 'SPWI118', 'SPWI110'],
    ['SPWI206', 'SPWI212', 'SPWI215', 'SPWI217'],
    ['SPWI303', 'SPWI312', 'SPWI307'],
    ['SPWI405', 'SPWI412'],
]


def fixture(version, reverse):
    data = bytearray(cre(version, 9, 13, 'NALIA'))
    data[0x274] = 93
    # Append a nonstandard-order table after effects, with nonzero upper bytes.
    rows = [(level, kind) for kind, levels in [(0, 7), (1, 9), (2, 1)]
            for level in range(levels)]
    if reverse:
        rows.reverse()
    struct.pack_into('<II', data, 0x2a8, len(data), len(rows))
    for level, kind in rows:
        data += struct.pack('<HHHHII', level, 0x123, 0x234, kind, 0, 0)
    return data, rows


def run(weidu):
    source = (ROOT / 'ArtisansKitpack_npc/ArtisansKitpack_npc.TP2').read_text()
    nalia = 'ACTION_IF FILE_EXISTS_IN_GAME ~nalia8.cre~' + source.split(
        'ACTION_IF FILE_EXISTS_IN_GAME ~nalia8.cre~', 1)[1].split('BEGIN ~Bardic Wonders:', 1)[0]
    xan = 'ACTION_IF FILE_EXISTS_IN_GAME ~O#XAN09.cre~' + source.split(
        'ACTION_IF FILE_EXISTS_IN_GAME ~O#XAN09.cre~', 1)[1].split(
        'ACTION_IF FILE_EXISTS_IN_GAME ~SW1H13.ITM~', 1)[0]
    for version, reverse, present in [(0, False, ('nalia8', 'nalia18', 'o#xan09', 'o#xan25')),
                                      (1, True, ('nalia18', 'o#xan25')),
                                      (1, False, ('nalia8', 'o#xan09')),
                                      (0, True, ())]:
        with tempfile.TemporaryDirectory(prefix='nalia-xan-') as temp:
            game = pathlib.Path(temp)
            override = game / 'override'
            override.mkdir()
            (game / 'regression').mkdir()
            (game / 'chitin.key').write_bytes(b'KEY V1  ' + struct.pack('<4I', 0, 0, 64, 64) + bytes(40))
            (game / 'dialog.tlk').write_bytes(b'TLK V1  ' + struct.pack('<HII', 0, 0, 18))
            (game / 'baldur.ini').write_text('[Alias]\nHD0:=./\n')
            (override / 'class.ids').write_text('IDS V1.0\n19 SORCERER\n')
            (override / 'kit.ids').write_text('IDS V1.0\n0x4001 C0_ARCANE_TRICKSTER_SORC\n0x4002 C0EK\n')
            original = {}
            for name in present:
                data, rows = fixture(version, reverse)
                if name.startswith('o#'):
                    # Keep the existing class guard: non-fighter/mage Xan stays untouched.
                    data[0x273] = 7 if name.endswith('25') else 1
                original[name] = bytes(data)
                (override / (name + '.cre')).write_bytes(data)
            actions = f'''BACKUP ~regression/backup~
AUTHOR ~regression fixtures~
BEGIN ~Nalia and Xan regression fixtures~
{nalia}
{xan}
'''
            (game / 'regression/setup-regression.tp2').write_text(actions)
            result = subprocess.run([weidu, 'regression/setup-regression.tp2', '--noautoupdate',
                                     '--no-exit-pause', '--force-install-list', '0'], cwd=game,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode or 'SUCCESSFULLY INSTALLED' not in result.stdout:
                print(result.stdout)
                raise AssertionError('WeiDU fixture failed')
            files = {p.name.lower(): p for p in override.iterdir()}
            assert {p[:-4] for p in files if p.endswith('.cre')} == set(present)
            for name in present:
                data = files[name + '.cre'].read_bytes()
                if name.startswith('o#'):
                    expected = bytearray(original[name])
                    if expected[0x273] == 7:
                        struct.pack_into('<H', expected, 0x246, 0x4002)
                    assert data == expected, name
                    continue
                assert data[0x273:0x275] == bytes([19, 93])
                assert struct.unpack_from('<HH', data, 0x24) == (36, 36)
                assert struct.unpack_from('<H', data, 0x246)[0] == 0x4001
                assert set(effects(data)) == {(233, 1, 91), (233, 1, 105), (0, 2, 0)}
                known_off, known_count, info_off, info_count, mem_off, mem_count = struct.unpack_from('<6I', data, 0x2a0)
                known = {struct.unpack_from('<8sHH', data, known_off + 12*i) for i in range(known_count)}
                expected_known = {(s.encode().ljust(8, b'\0'), level, 1)
                                  for level, spells in enumerate(SPELLS) for s in spells}
                assert known == expected_known
                assert info_count == len(rows)
                total = 0
                for i, (level, kind) in enumerate(rows):
                    actual_level, base, modified, actual_kind, index, count = struct.unpack_from('<HHHHII', data, info_off + 16*i)
                    assert (actual_level, actual_kind) == (level, kind)
                    target = kind == 1 and level < 4
                    expected_slots = ((5, 5) if level == 3 else (7, 7)) if target else (0x123, 0x234)
                    assert (base, modified) == expected_slots
                    actual = collections.Counter()
                    for j in range(index, index + count):
                        resource, flags = struct.unpack_from('<8sI', data, mem_off + 12*j)
                        assert flags == 1
                        actual[resource.rstrip(b'\0').decode()] += 1
                    expected = collections.Counter({s: 3 if level == 3 else 5 for s in SPELLS[level]}) if target else collections.Counter()
                    assert actual == expected, (name, level, kind, actual)
                    total += count
                assert total == mem_count == 66
            print(f'PASS Nalia relocated spell tables (EFF V{version + 1}, reverse={reverse}), preserved spells/effects and independent NPC presence: {present}')


if __name__ == '__main__':
    run(str(pathlib.Path(sys.argv[1]).resolve()))
