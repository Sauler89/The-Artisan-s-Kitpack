"""Static regression checks for kit files (not a substitute for in-game testing)."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "ArtisansKitpack"


def read(relative):
    return (MOD / relative).read_text(encoding="utf-8-sig")


class KitRegressionSourceTests(unittest.TestCase):
    def test_enlightened_fist_uses_d6_table(self):
        source = read("lib/EnlightenedFist.tpa")
        self.assertRegex(source, r"(?m)^\s*hpclass\s*=\s*~HPROG~")

    def test_wolf_shape_patches_both_stat_references(self):
        source = read("lib/Shapeshifter.tpa")
        self.assertRegex(source, r"COPY_EXISTING\s+~C0SS-W\.ITM~")
        self.assertRegex(source, r"match_resource\s*=\s*~C0SS-FS~\s+resource\s*=\s*~C0SS-WS~")
        self.assertRegex(source, r"match_resource\s*=\s*~C0SS-FD~\s+resource\s*=\s*~C0SS-WD~")

    def test_ninja_smoke_bomb_is_present_in_packaged_level_one_clab(self):
        source = read("MonkRevision/Ninja/2da/C0NINJA.2DA")
        self.assertRegex(source, r"(?m)^ABILITY\d+\s+GA_C0NINJ1\b")

    def test_dwarven_defender_clab_grants_shield_bash(self):
        source = read("lib/dwarvendefender.tpa")
        self.assertIn("f_Entry = GA_C0DWD03", source)


if __name__ == "__main__":
    unittest.main()
