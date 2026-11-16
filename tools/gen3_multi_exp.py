#!/usr/bin/env python3
"""Gen 3 Multi EXP patch generator (Pokemon Emerald / FireRed / LeafGreen).

Effect of the patch
-------------------
After a battle, EVERY living Pokemon in the player's party receives the full
experience amount, as if it had been the only participant. Held Exp. Share
items no longer split or halve the experience (they become redundant).

How it works
------------
The routine ``Cmd_getexp`` (battle script command 0x23) is located in each ROM
through the battle command table, then four 2-byte Thumb instructions are
rewritten in place (no code is moved, so the patch is tiny and safe):

  1. ``sentIn = gSentPokesToOpponent[..]``  ->  ``sentIn = 0x3F``
     (all six party slots count as participants)
  2. ``viaSentIn = 0``                      ->  ``viaSentIn = 1``
     (the experience is divided by one)
  3. ``viaSentIn++``                        ->  ``nop``
  4. ``viaExpShare++``                      ->  ``nop``
     (the Exp. Share branch is never taken, so nothing is halved)

Usage
-----
  python gen3_multi_exp.py build  <roms_dir> [--out patches]   # write .ips files
  python gen3_multi_exp.py apply  <roms_dir> [--out patched]   # write patched ROMs
"""

import argparse
import os
import struct
import sys

ROM_SIZE = 16 * 1024 * 1024
ROM_BASE = 0x08000000
GETEXP_OPCODE = 0x23          # index of Cmd_getexp in the battle command table
COMMAND_COUNT = 248           # number of entries in the battle command table

NOP = bytes.fromhex("c046")   # Thumb "mov r8, r8"

# Known game codes (header offset 0xAC).
GAME_NAMES = {
    "BPEE": "Emerald (USA/Europe)",
    "BPES": "Emerald (Spain)",
    "BPED": "Emerald (Germany)",
    "BPEF": "Emerald (France)",
    "BPEI": "Emerald (Italy)",
    "BPEJ": "Emerald (Japan)",
    "BPRE": "FireRed (USA/Europe)",
    "BPRS": "FireRed (Spain)",
    "BPRD": "FireRed (Germany)",
    "BPRF": "FireRed (France)",
    "BPRI": "FireRed (Italy)",
    "BPRJ": "FireRed (Japan)",
    "BPGE": "LeafGreen (USA/Europe)",
    "BPGS": "LeafGreen (Spain)",
    "BPGD": "LeafGreen (Germany)",
    "BPGF": "LeafGreen (France)",
    "BPGI": "LeafGreen (Italy)",
    "BPGJ": "LeafGreen (Japan)",
}

# Byte signatures inside Cmd_getexp (identical in Emerald, FireRed, LeafGreen).
SIG_SENT_IN = bytes.fromhex("0978" "8846")             # ldrb r1,[r1] ; mov r8,r1
SIG_LOOP_INIT = bytes.fromhex("0025" "0027" "6420")    # movs r5,#0 ; movs r7,#0 ; movs r0,#100
SIG_LOOP_END = bytes.fromhex("052f")                   # cmp r7,#5
INS_VIA_SENT_IN_INC = bytes.fromhex("0135")            # adds r5,#1
INS_VIA_EXP_SHARE_INC = bytes.fromhex("0136")          # adds r6,#1


class PatchError(Exception):
    pass


def find_command_table(rom: bytes) -> int:
    """Return the file offset of the battle script command table."""
    words = struct.unpack("<%dI" % (len(rom) // 4), rom)
    found = []
    i = 0
    n = len(words)
    while i < n:
        j = i
        while j < n and ROM_BASE < words[j] < 0x08400000 and words[j] & 1:
            j += 1
        if COMMAND_COUNT <= j - i <= COMMAND_COUNT + 4:
            found.append(i * 4)
        i = j + 1
    if len(found) != 1:
        raise PatchError("battle command table not found uniquely (%d candidates)" % len(found))
    return found[0]


def compute_edits(rom: bytes):
    """Return a list of (file_offset, original_bytes, new_bytes)."""
    table = find_command_table(rom)
    ptr = struct.unpack_from("<I", rom, table + 4 * GETEXP_OPCODE)[0]
    start = (ptr & ~1) - ROM_BASE
    body = rom[start:start + 0x400]

    def find_once(sig, lo, hi, what):
        pos = body.find(sig, lo, hi)
        if pos < 0 or body.find(sig, pos + 1, hi) >= 0:
            raise PatchError("signature for %s not found uniquely" % what)
        return pos

    edits = []

    # 1. sentIn = 0x3F (movs r1, #0x3f replaces ldrb r1, [r1])
    pos = find_once(SIG_SENT_IN, 0, 0x80, "sentIn load")
    edits.append((start + pos, body[pos:pos + 2], bytes.fromhex("3f21")))

    # 2. viaSentIn starts at 1
    pos_init = find_once(SIG_LOOP_INIT, 0, 0x200, "party loop init")
    edits.append((start + pos_init, body[pos_init:pos_init + 2], bytes.fromhex("0125")))

    # 3 & 4. Remove the two counters inside the party loop
    loop_end = body.find(SIG_LOOP_END, pos_init)
    if loop_end < 0:
        raise PatchError("end of party loop not found")
    for sig, what in ((INS_VIA_SENT_IN_INC, "viaSentIn++"), (INS_VIA_EXP_SHARE_INC, "viaExpShare++")):
        pos = pos_init
        hits = []
        while True:
            pos = body.find(sig, pos + 2, loop_end)
            if pos < 0:
                break
            if pos % 2 == 0:
                hits.append(pos)
        if len(hits) != 1:
            raise PatchError("%s: expected 1 match in loop, found %d" % (what, len(hits)))
        edits.append((start + hits[0], sig, NOP))

    return sorted(edits)


def make_ips(edits) -> bytes:
    out = bytearray(b"PATCH")
    for offset, _old, new in edits:
        out += offset.to_bytes(3, "big") + len(new).to_bytes(2, "big") + new
    out += b"EOF"
    return bytes(out)


def rom_label(rom: bytes, filename: str):
    code = rom[0xAC:0xB0].decode("ascii", "replace")
    rev = rom[0xBC]
    name = GAME_NAMES.get(code)
    if name is None:
        return None
    return code, rev, name


def iter_roms(directory):
    for fname in sorted(os.listdir(directory)):
        if fname.lower().endswith(".gba"):
            path = os.path.join(directory, fname)
            with open(path, "rb") as f:
                rom = f.read()
            yield fname, rom


def run(mode: str, roms_dir: str, out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    failures = 0
    for fname, rom in iter_roms(roms_dir):
        label = rom_label(rom, fname)
        if label is None or len(rom) != ROM_SIZE:
            print("SKIP  %s (not a supported Gen 3 ROM)" % fname)
            continue
        code, rev, name = label
        stem = os.path.splitext(fname)[0]
        try:
            edits = compute_edits(rom)
        except PatchError as exc:
            print("FAIL  %s: %s" % (fname, exc))
            failures += 1
            continue
        if mode == "build":
            target = os.path.join(out_dir, "%s - Multi EXP.ips" % stem)
            with open(target, "wb") as f:
                f.write(make_ips(edits))
        else:
            patched = bytearray(rom)
            for offset, _old, new in edits:
                patched[offset:offset + len(new)] = new
            target = os.path.join(out_dir, "%s (Multi EXP).gba" % stem)
            with open(target, "wb") as f:
                f.write(patched)
        print("OK    %s [%s r%d, %s] -> %s" % (fname, code, rev, name, os.path.basename(target)))
        for offset, old, new in edits:
            print("        0x%06X  %s -> %s" % (offset, old.hex(), new.hex()))
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["build", "apply"])
    parser.add_argument("roms_dir")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    out = args.out or ("patches" if args.mode == "build" else "patched")
    sys.exit(run(args.mode, args.roms_dir, out))


if __name__ == "__main__":
    main()
