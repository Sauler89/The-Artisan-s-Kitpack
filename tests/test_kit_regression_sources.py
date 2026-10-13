"""Inspect shipped resources; WeiDU patch execution lives in run_weidu_regressions.py."""
import pathlib
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "ArtisansKitpack"


def read(relative):
    return (MOD / relative).read_text(encoding="utf-8-sig")


def asset(name):
    return next(p for p in MOD.rglob("*") if p.is_file() and p.name.lower() == name.lower())


class KitRegressionSourceTests(unittest.TestCase):
    def test_enlightened_fist_uses_d6_table(self):
        self.assertRegex(read("lib/EnlightenedFist.tpa"), r"(?m)^\s*hpclass\s*=\s*~HPROG~")

    def test_wolf_shape_already_uses_wolf_stat_effects(self):
        data = asset("C0SS-W.ITM").read_bytes()
        self.assertEqual(data[:8], b"ITM V1  ")
        offset = struct.unpack_from("<I", data, 0x6a)[0]
        first, count = struct.unpack_from("<HH", data, 0x6e)
        references = set()
        for index in range(first, first + count):
            effect = offset + index * 48
            if struct.unpack_from("<H", data, effect)[0] == 177:
                references.add(data[effect + 20:effect + 28].rstrip(b"\0").upper())
        self.assertTrue({b"C0SS-WS", b"C0SS-WD"} <= references)
        self.assertFalse({b"C0SS-FS", b"C0SS-FD"} & references)
        for resref in ("C0SS-WS.EFF", "C0SS-WD.EFF"):
            self.assertEqual(asset(resref).read_bytes()[:8], b"EFF V2.0")

    def test_ninja_smoke_bomb_has_level_one_grant_and_visible_header(self):
        source = read("MonkRevision/Ninja/2da/C0NINJA.2DA")
        self.assertRegex(source, r"(?m)^ABILITY\d+\s+GA_C0NINJ1\b")
        data = asset("C0NINJ1.SPL").read_bytes()
        self.assertEqual(struct.unpack_from("<H", data, 0x1c)[0], 4)
        self.assertEqual(struct.unpack_from("<I", data, 0x34)[0], 1)
        header = struct.unpack_from("<I", data, 0x64)[0]
        self.assertEqual(data[header + 2], 4)
        self.assertEqual(struct.unpack_from("<H", data, header + 0x10)[0], 1)
        icon = data[header + 4:header + 12].rstrip(b"\0").decode()
        self.assertTrue(asset(icon + ".BAM").is_file())

    def test_dwarven_defender_clab_grants_shield_bash(self):
        self.assertIn("f_Entry = GA_C0DWD03", read("lib/dwarvendefender.tpa"))


if __name__ == "__main__":
    unittest.main()
