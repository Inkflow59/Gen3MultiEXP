# Gen 3 Multi EXP

A tiny ROM patch for Pokémon **Emerald**, **FireRed** and **LeafGreen** (GBA).

**Effect:** after a battle, every living Pokémon in your party receives the
**full** experience amount, as if it were the only participant. Held Exp. Share
items no longer split or halve the experience (they become redundant).

## Supported versions

20 versions, all patched successfully from real dumps:

| Game      | USA/EU        | Japan | Spain | Germany | France | Italy |
|-----------|---------------|-------|-------|---------|--------|-------|
| Emerald   | ✅            | ✅    | ✅    | ✅      | ✅     | ✅    |
| FireRed   | ✅ (rev 0, 1) | ✅    | ✅    | ✅      | ✅     | ✅    |
| LeafGreen | ✅ (rev 0, 1) | ✅    | ✅    | ✅      | ✅     | ✅    |

Not covered: any other revision or region — the tool refuses ROMs whose
signatures do not match exactly one location rather than guessing.

## Use

Generate IPS patches (one per ROM version, 4 two-byte edits each) or patched
ROMs yourself from a folder containing your own dumps. IPS patches can be
applied with any IPS patcher (Lunar IPS, Floating IPS, …).

```bash
python tools/gen3_multi_exp.py build <roms_dir>   # writes patches/*.ips
python tools/gen3_multi_exp.py apply <roms_dir>   # writes patched/*.gba
```

Use `--out <dir>` to choose the output folder. Patched ROMs are named
`<original name> (Multi EXP).gba`; the original files are left untouched.

ROMs are never stored in this repository.

## How it works

`Cmd_getexp` (battle command `0x23`) is located through the battle command
table, then four Thumb instructions are rewritten in place: all six party slots
count as participants, the participant divisor becomes 1, and both counters in
the party loop become no-ops. See the docstring in
[`tools/gen3_multi_exp.py`](tools/gen3_multi_exp.py).

## Status

Verified statically (byte signatures matched uniquely in all 20 versions, patched
instructions disassembled).
