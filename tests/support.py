"""Shared test setup: a throwaway home folder for main.py, and helpers to fill it with stand-in game installs.

main.py derives its paths (HOME, the stores' files) from `decky` when it's imported, so the folder is created once,
before the import; FakeHomeTest empties it again before every test."""
import os
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = tempfile.mkdtemp(prefix="helixsr-tests-")
os.environ["HELIXSR_TEST_ROOT"] = ROOT
for d in ("home", "homebrew", "plugin", "settings", "runtime", "logs"):
    os.makedirs(os.path.join(ROOT, d), exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the repo, for main.py
import main  # noqa: E402

HOME = main.HOME


class FakeHomeTest(unittest.TestCase):
    """Starts every test with an empty home folder and no plugin settings."""

    def setUp(self):
        for d in ("home", "settings", "runtime"):
            p = os.path.join(ROOT, d)
            shutil.rmtree(p, ignore_errors=True)
            os.makedirs(p)


def game(folder, *exes):
    """A stand-in game folder with (fake) .exe files; returns its path."""
    p = Path(folder)
    p.mkdir(parents=True, exist_ok=True)
    for e in exes:
        (p / e).write_bytes(b"MZ")
    return p


def write(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data)
    return p


def binary_kv(d):
    """Steam's binary KeyValues (as in shortcuts.vdf) for a dict of dicts, strings and ints."""
    out = b""
    for k, v in d.items():
        if isinstance(v, dict):
            out += b"\x00" + k.encode() + b"\0" + binary_kv(v)
        elif isinstance(v, int):
            out += b"\x02" + k.encode() + b"\0" + struct.pack("<i", v)
        else:
            out += b"\x01" + k.encode() + b"\0" + v.encode() + b"\0"
    return out + b"\x08"


def pe_exe(path, imports=()):
    """A minimal 64-bit Windows executable whose import table names the given DLLs (e.g. "d3d11.dll"), for the
    DirectX checks. One section at file offset 0x400 / RVA 0x1000 holds the import descriptors and the names."""
    import struct as st
    dos = bytearray(0x40)
    dos[0:2] = b"MZ"
    st.pack_into("<I", dos, 0x3C, 0x40)
    opt = bytearray(240)
    st.pack_into("<H", opt, 0, 0x20B)                      # PE32+
    st.pack_into("<Q", opt, 24, 0x140000000)               # ImageBase
    st.pack_into("<I", opt, 108, 16)                       # NumberOfRvaAndSizes
    names_at = 0x100
    st.pack_into("<II", opt, 112 + 8, 0x1000, 20 * (len(imports) + 1))   # directory 1: imports
    coff = b"PE\0\0" + st.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, len(opt), 0x22)
    sec = bytearray(40)
    sec[0:6] = b".idata"
    st.pack_into("<IIII", sec, 8, 0x400, 0x1000, 0x400, 0x400)
    body = bytearray(0x400)
    for i, name in enumerate(imports):
        st.pack_into("<I", body, i * 20 + 12, 0x1000 + names_at + i * 32)
        body[names_at + i * 32:names_at + i * 32 + len(name)] = name.encode()
    head = bytes(dos) + coff + bytes(opt) + bytes(sec)
    return write(path, head.ljust(0x400, b"\0") + bytes(body))


def enable_stores(*ids):
    """Switches other stores on, as the "Other Stores" toggles do (all are off by default)."""
    s = main.load_settings()
    s["stores"] = {i: True for i in ids}
    main.save_settings(s)


def shortcuts_vdf(entries, user="123"):
    """Writes Steam's shortcuts.vdf for one user. entries: dicts with appid, AppName, Exe, StartDir, ..."""
    data = binary_kv({"shortcuts": {str(i): e for i, e in enumerate(entries)}}) + b"\x08"
    return write(HOME / f".local/share/Steam/userdata/{user}/config/shortcuts.vdf", data)
