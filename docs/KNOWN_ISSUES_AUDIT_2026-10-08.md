# Artisan's Kitpack — regression audit (2026-10-08)

Scope: `Sauler89/The-Artisan-s-Kitpack`, draft PR #1. Installation-time fixes and resource inspection are distinct from gameplay verification. No BGEE/BG2EE/EET engine or EEex runtime was available during this audit.

## Findings and changes

| Report | Evidence and action | Remaining verification |
| --- | --- | --- |
| Dark Moon Monk: Sorcerous Lineage scaling ([#57](https://github.com/TheArtisanBG/The-Artisan-s-Kitpack/issues/57)) | The **non-EEex** selector referenced original wizard spells, giving a monk wizard caster-level behavior. `dark_moon_lineage.tpa` now creates private innate `C0DL###` copies and remaps the five selectors, preserving installed effects and level headers. Original wizard spells are untouched. The separate EEex implementation is unchanged. | Compare Magic Missile and Mirror Image at monk levels 1/5/9/13 without EEex. Modded nested cast subspells are not recursively converted and need separate compatibility tests. |
| Favored Soul: favored short swords unusable in ToB ([#61](https://github.com/TheArtisanBG/The-Artisan-s-Kitpack/issues/61)) | Both proficiency passes read ITM offset `0x31` as a short, incorrectly including minimum Charisma at `0x32`. Changed both to `READ_BYTE`. This fixes incorrect proficiency matching on items with a nonzero minimum Charisma byte. | **The specific ToB report remains open:** this defect does not explain an item whose minimum Charisma is zero. Need the failing item resources, save and mod order; do not remove general item restrictions. |
| Shapeshifter: Wolf Shape STR/DEX references ([PR #25](https://github.com/TheArtisanBG/The-Artisan-s-Kitpack/pull/25)) | Packaged `C0SS-W.ITM` already references `C0SS-WS` and `C0SS-WD` in opcode 177 effects. Removed the previous no-op patch (also overwritten by a subsequent copy). Replaced its misleading source test with binary resource assertions. | No new fix needed for the shipped references. Inspect final installed ITM/EFF if stats still fail. |
| Trickster: Mimicry compatibility/crashes ([PR #20](https://github.com/TheArtisanBG/The-Artisan-s-Kitpack/pull/20)) | Nine base selectors contain 30 entries each; conditional additions alone do not prove an overflow. PR #20 replaces curated integration with automatic CLAB ability discovery, rather than merely removing some additions. No speculative feature removal. | Exact crashing ability, WeiDU.log, installed selector tables and repeatable save. |
| Dwarven Defender + revised Vanguard: hidden Shield Bash | `C0DWD03.SPL` is an innate with **spell level 0**. The installer now sets level 1, matching innate memorization and the optional EEex modal menu's search range. Both revised kits share this resource. | Fresh characters and level-ups, with/without the optional modal menu. Standalone vanilla Vanguard does not advertise/grant Shield Bash; this patch does not add that feature. |
| Martyr missing after Sirene | `ADD_KIT_EX` skips an already registered `C0ILM`, including chargen registration. New helper reuses its existing numeric KITLIST ID and ensures one entry in existing paladin selection tables. It leaves other classes and kit IDs intact and does not create absent race tables. | Test Sirene → Martyr and reverse order using the user's actual versions and selection UI. Current Sirene source confirms shared registration, but does not by itself reproduce every reported disappearance. |
| Paladin: Divine Grace lost when Aura of Courage expires | Grace's `C0PAL03*` spells and Courage's `C0PAL04*` spells remove their own respective families. Inspection did not demonstrate cross-removal. No speculative opcode replacement. | Save before/after expiration, final SPL resources and active creature effects. |
| Eldritch Knight: restrictions affect other items | Fixed Boolean grouping in the armor pass: item type must be armor for **both** chain and plate appearance checks. Previously the plate appearance bypassed the type condition. | This is a concrete scope bug, **not proof of resolution of the reported weapon restrictions**. Compare final affected ITM on EK and an unrelated class. |
| Ninja: Smoke Bomb missing at BG2 chargen | Packaged CLAB grants it at level 1. `C0NINJ1.SPL` already has innate type, level 1, a level-1 ability header at location 4 and an existing icon. No missing grant/resource found. | New BG2 character save, installed CLAB/SPL, EEex and UI versions. |
| Enlightened Fist: d4 instead of d6 | Earlier commit enabled the commented `hpclass = ~HPROG~` entry. Retained. | Verify chargen and level-up HP with controlled Constitution and difficulty settings. |
| Shared Gift: cannot revert | Transformation includes the `C0SS-WN` revert grant; that resource exists as a level-1 innate and contains revert/removal effects. No simple missing-revert-resource defect demonstrated. | Affected recipient save, form used, steps, installed transformation resources. |
| Shapeshifter: deselection/XP while wolf transformed | Wolf item contains a short opcode 365 effect and equipped class/XP changes. Temporary zero XP while transformed is not sufficient evidence of permanent loss. | Record XP before transform, during kill/quest rewards, after revert and after reload. No speculative deletion of class/form effects. |

## Automated verification

Run locally:

```sh
python3 -m unittest discover -s tests -v
python3 tests/run_weidu_regressions.py /absolute/path/to/weidu
```

The four source/binary checks cover the d6 declaration, real wolf EFF references, Ninja's shipped grant/header/icon, and Shield Bash's grant. The GitHub Actions workflow also downloads official WeiDU 251 with a pinned SHA-256, parses changed TPA files and executes production patches in a synthetic empty game directory. No copyrighted game files are needed.

The synthetic fixture checks that the five Dark Moon selectors are remapped while original spells and copied effect/header payloads remain intact; repeated helper execution is idempotent; Martyr uses a stored kit ID different from its physical row number, avoids duplicate entries and preserves unrelated tables; Shield Bash becomes level 1; and proficiency reads exclude minimum Charisma. These checks **do not simulate the game engine or a complete mod installation**.

## Files needed for unresolved runtime reports

- `WeiDU.log`, `SETUP-ARTISANSKITPACK.DEBUG`, and the tweaks DEBUG if those components are installed.
- A ZIP of the complete affected save folder, with game/campaign version, exact steps and expected/observed behavior.
- For Martyr: installed `KITLIST.2DA`, `KITTABLE.2DA` and `K_P_*.2DA` exported from the affected installation.
- For item restrictions: exact failing item name/resource and final installed `.ITM`; for spell issues, final relevant `.SPL`/`.EFF` files. Near Infinity can export resources that are not present in override.

Do not install this draft over the only copy of a working modded game. Validate on a separate installation with the same order before promoting the draft.
