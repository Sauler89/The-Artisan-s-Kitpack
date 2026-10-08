"""Execute production patches with WeiDU against synthetic resources, not a game.

Usage: python tests/run_weidu_regressions.py /absolute/path/to/weidu
This checks installation-time transformations only; no engine/EEex is simulated.
"""
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / 'ArtisansKitpack'


def asset(name):
    return next(p for p in MOD.rglob('*') if p.is_file() and p.name.lower() == name.lower())


def run(weidu):
    with tempfile.TemporaryDirectory(prefix='kitpack-regression-') as directory:
        game = pathlib.Path(directory)
        override = game / 'override'
        override.mkdir()
        # Empty but valid KEY/TLK files; all tested resources are synthetic or mod-owned.
        (game / 'chitin.key').write_bytes(b'KEY V1  ' + struct.pack('<4I', 0, 0, 64, 64) + bytes(40))
        (game / 'dialog.tlk').write_bytes(b'TLK V1  ' + struct.pack('<HII', 0, 0, 18))
        (game / 'baldur.ini').write_text('[Alias]\nHD0:=./\n')
        (game / 'regression').mkdir()
        # Preserve real multi-header/effect data while substituting a wizard type/level.
        source = bytearray(asset('C0NINJ1.SPL').read_bytes())
        struct.pack_into('<H', source, 0x1c, 1)
        struct.pack_into('<I', source, 0x34, 2)
        for name in ('spwi112.spl', 'spwi205.spl'):
            (override / name).write_bytes(source)
        for suffix in 'ABCDE':
            (override / f'c0dmm01{suffix.lower()}.2da').write_text(
                '2DA V1.0\n\n  ResRef Type\nMISSILE SPWI112 3\nMIRROR SPWI205 3\n')
        shutil.copyfile(asset('c0dwd03.spl'), override / 'c0dwd03.spl')
        (override / 'kitlist.2da').write_text(
            '2DA V1.0\n*\n ROWNAME LOWER MIXED HELP ABILITIES PROFICIENCY UNUSABLE CLASS KITIDS\n'
            '0 RESERVE 0 0 0 **** 0 0 0 0\n'
            '42 C0ILM 0 0 0 C0ILMCL 0 0x8 6 0x402a\n')
        (override / 'kittable.2da').write_text(
            '2DA V1.0\n*\n HUMAN ELF OTHER\nPALADIN K_P_H K_P_E K_P_NO\nFIGHTER K_F_H * *\n')
        (override / 'k_p_h.2da').write_text('2DA V1.0\n*\n KIT\n1 0\n7 99\n')
        (override / 'k_p_e.2da').write_text('2DA V1.0\n*\n KIT\n1 0\n3 42\n')
        fighter = '2DA V1.0\n*\n KIT\n1 0\n'
        (override / 'k_f_h.2da').write_text(fighter)
        # Run the exact Shield Bash installation block, not a test reimplementation.
        defender = (MOD / 'lib/dwarvendefender.tpa').read_text()
        shield = defender.split('COPY_EXISTING ~C0DWD03.SPL~ OVERRIDE', 1)[1].split('COPY_EXISTING', 1)[0]
        actions = f'''BACKUP ~regression/backup~
AUTHOR ~regression test~
BEGIN ~Synthetic kit regression fixtures~
OUTER_SPRINT MOD_FOLDER ~{MOD.as_posix()}~
INCLUDE ~%MOD_FOLDER%/lib/a7#add_kit_ex.tpa~
INCLUDE ~%MOD_FOLDER%/lib/dark_moon_lineage.tpa~
INCLUDE ~%MOD_FOLDER%/lib/dark_moon_lineage.tpa~
INCLUDE ~%MOD_FOLDER%/lib/martyr_visibility.tpa~
INCLUDE ~%MOD_FOLDER%/lib/martyr_visibility.tpa~
COPY_EXISTING ~C0DWD03.SPL~ ~override~
{shield}
'''
        # These source reads used to combine proficiency and minimum Charisma.
        for rel in ('eeex/profs_eeex.tpa', 'lib/profs_eeex_patch.tpa'):
            text = (MOD / rel).read_text()
            read = re.search(r'READ_(?:BYTE|SHORT)\s+0x31\s+proficiency', text).group()
            actions += f'''OUTER_PATCH ~{' ' * 114}~ BEGIN
WRITE_BYTE 0x31 91
WRITE_SHORT 0x32 18
{read}
PATCH_IF (proficiency != 91) BEGIN PATCH_FAIL ~Proficiency overlaps minimum Charisma~ END
END
'''
        (game / 'regression/setup-regression.tp2').write_text(actions)
        result = subprocess.run([weidu, 'regression/setup-regression.tp2', '--noautoupdate',
                                 '--no-exit-pause', '--force-install-list', '0'],
                                cwd=game, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            print(result.stdout)
            debug = game / 'SETUP-REGRESSION.DEBUG'
            if debug.exists():
                print(debug.read_text(errors='replace'))
            raise SystemExit(result.returncode)
        files = {p.name.lower(): p for p in override.iterdir()}
        expected = bytearray(source)
        struct.pack_into('<H', expected, 0x1c, 4)
        struct.pack_into('<I', expected, 0x34, 1)
        for original, copied in (('spwi112', 'c0dl112'), ('spwi205', 'c0dl205')):
            assert files[original + '.spl'].read_bytes() == source, original
            assert files[copied + '.spl'].read_bytes() == expected, copied
        for suffix in 'abcde':
            rows = files[f'c0dmm01{suffix}.2da'].read_text().splitlines()
            assert any('C0DL112' in x for x in rows)
            assert any('C0DL205' in x for x in rows)
            assert any(x.split() == ['MISSILE', 'C0DL112', '3'] for x in rows)
        for table in ('k_p_h', 'k_p_e'):
            rows = [x.split() for x in files[table + '.2da'].read_text().splitlines()]
            assert sum(len(x) == 2 and x[1] == '42' for x in rows) == 1, rows
        rows = [x.split() for x in files['k_p_h.2da'].read_text().splitlines()]
        assert ['7', '99'] in rows and ['8', '42'] in rows, rows
        assert files['k_f_h.2da'].read_text() == fighter
        assert 'k_p_no.2da' not in files
        shield_data = files['c0dwd03.spl'].read_bytes()
        assert struct.unpack_from('<I', shield_data, 0x34)[0] == 1
        print('PASS: production WeiDU patches preserve spell payloads and originals, remap all five selectors,')
        print('restore one Martyr entry without duplicates or unrelated-table edits, normalize Shield Bash,')
        print('and read weapon proficiency independently of minimum Charisma.')


if __name__ == '__main__':
    run(str(pathlib.Path(sys.argv[1]).resolve()))
