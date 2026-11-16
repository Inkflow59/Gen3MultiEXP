# Gen 3 Multi EXP

A tiny ROM patch for Pokémon **Emerald**, **FireRed** and **LeafGreen** (GBA).

**Effect:** after a battle, every living Pokémon in your party receives the
**full** experience amount, as if it were the only participant. Held Exp. Share
items no longer split or halve the experience (they become redundant).

Supported ROMs: 14 versions (Emerald USA/EU, ES, DE, FR; FireRed USA rev 0/1,
JP, ES, FR; LeafGreen USA rev 0/1, DE, FR, IT).

## Use

Ready-made IPS patches are in `patches/` (one per ROM version, 4 two-byte edits
each). Apply the one matching your ROM with any IPS patcher (Lunar IPS, Floating
IPS, …).

Or generate patches / patched ROMs yourself:

```bash
python tools/gen3_multi_exp.py build <roms_dir>   # writes patches/*.ips
python tools/gen3_multi_exp.py apply <roms_dir>   # writes patched/*.gba
```

ROMs are never stored in this repository.

## How it works

`Cmd_getexp` (battle command `0x23`) is located through the battle command
table, then four Thumb instructions are rewritten in place: all six party slots
count as participants, the participant divisor becomes 1, and both counters in
the party loop become no-ops. See the docstring in
[`tools/gen3_multi_exp.py`](tools/gen3_multi_exp.py).

## Status

Verified statically (byte signatures matched uniquely in all 14 ROMs, patched
instructions disassembled). **Not yet tested in an emulator** — please test at
least one ROM in game.
