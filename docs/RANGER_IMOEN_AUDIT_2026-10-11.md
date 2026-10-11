# Ranger / Imoen audit — 2026-10-11

Baseline: `f38b48da73a8e06a41acad59241d357bb59d3678` on `master`.

| Report | Change | Verification limit |
| --- | --- | --- |
| First ranger snare reports too many traps | Replace the blanket `APPEND ... UNLESS RANGER` with exact, independent row updates. Add absent rows and repair zero/malformed caps for the base ranger, cleric/ranger, vanilla ranger kits and installed kits receiving `GA_SPCL412`. Preserve existing nonzero limits and unrelated classes. | The installer defect is reproducible with an existing zero RANGER row or a CLERIC_RANGER substring suppressing the old append. The user's installed table is still needed to establish which case occurred. |
| Rest becomes unavailable after a failed snare | No speculative change to global snare spells or area scripts. | Need a save immediately before/after the failure, the rest error text, `TRAPLIMT.2DA`, `SPCL412.SPL`, and WeiDU.log. Correcting the cap does not by itself demonstrate that rest is repaired. |
| Ranger misses initial +4 HP | Shipped `C0RNH1` casts `C0RNH_1`, whose opcode 18 adds 4 HP; the level-1 CLAB grant exists. The cast-once HP effect uses timing 1 with a self-protection effect. No initial-HP change was made without a reproduction. | Need kit/campaign, Constitution, difficulty, whether the deficit remains after entering the game, a level-1 save, installed CLAB and `C0RNH1.SPL` / `C0RNH_1.SPL`. |
| Related Toughness progression defect | Correct two level typos in both the base and kit schedules: `C0RNH20` belongs at 20, not 10; `C0RNH30` belongs at 30, not 20. | This corrects early grants and does **not** resolve the reported initial +4 HP deficit. |
| Level-1 Rogue Archer Imoen has three proficiency pips | Assign one shortbow pip to the level-1 single-class thief resource, retaining her existing melee pip. Preserve the existing two-pip shortbow allocation for higher-level and dual-class resources. | Tested against vanilla-shaped synthetic level-1/level-4/dual-class CREs in both effect formats. Other mods that replace her proficiency allocation or a save containing an already recruited Imoen need separate inspection. |

The CI runs official WeiDU 251 syntax checks and executes production patch blocks on synthetic resources: absent/zero/substring-conflicting trap rows, custom kit caps, repeated execution, all 50 base Toughness grant levels, both source Toughness schedules, both CRE effect formats, higher-level and dual-class Imoen, and an unrelated NPC. No game engine or full installation is simulated.

Reproduce with:

```sh
python3 tests/ranger_imoen_regressions.py /absolute/path/to/weidu
```

Changes affect newly installed resources; they are not a save-game hotfix. Earlier audit fixes remain on the separate draft branch and are not included here.

## Follow-up: Stalker and NPC resource writes

- **Stalker inherited abilities:** remove the complete `AP_C0RNG00` and `GA_C0CL922` entries before installing Stalker replacements. The former expression targeted an unused resource name; the latter left a malformed `GA_****` token. The Stalker's own passive bonuses and unrestricted Tracking remain, while the inherited Woodland Stride is removed as its description specifies.
- **Stalker d8 HP table:** locate the STALKER row by its label instead of requiring one exact number of spaces. Other HPCLASS rows are preserved.
- **Valygar variants:** the level-9/11/12/14 branches all copied `valyg8.cre`. Each now patches its corresponding resource; existing HP constants are unchanged. Tests include a partial installation containing `valyg9.cre` but no `valyg8.cre`.
- **NPC binary field widths:** use one byte for Class (`0x273`), two bytes for current/max HP (`0x24`/`0x26`) and four bytes for XP (`0x18`). Nine class writes previously also cleared the adjacent Specific field. Ten HP writes and two XP writes left high bytes unchanged, potentially producing wrong values on modified resources.

Additional WeiDU fixtures execute the production Stalker CLAB/HPCLASS/Valygar blocks and all 25 relevant NPC header writes, checking the exact resulting bytes and preservation of neighboring data. Existing ranger/Imoen tests continue to run.

The reported Stalker slowdown is not established by this audit: the shipped movement effects specify a 130% multiplier. Nalia's hard-coded spell-memorization offsets and variant guards remain candidates for a separate compatibility audit; they are not changed in this pass. Initial ranger +4 HP, failed-snare resting and the earlier unresolved runtime reports still require game evidence.
