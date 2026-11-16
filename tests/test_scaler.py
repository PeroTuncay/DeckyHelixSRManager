"""HelixSR 3.x: HelixSR Scaler (HelixSR's own OptiScaler package) into a game without OptiScaler, through HelixSR's
own installer (setup/helixsr_bridge.py, HelixSR Desktop's backend, run unmodified). A stand-in bridge here records how
it was called and installs / removes stand-in Scaler files, answering in JSON like the real one. Run: npm test."""
import asyncio
import json

from support import HOME, FakeHomeTest, main, write
from test_helixsr_releases import fake_dll
from test_hlx_fsr4 import release

FAKE_BRIDGE = r'''
import json, sys
from pathlib import Path
rel, cmd, args = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
a = dict(zip(args[::2], args[1::2]))
with open(Path(__file__).with_name("calls.json"), "a") as f:
    f.write(json.dumps([cmd] + args) + "\n")
fail = Path(__file__).with_name("fail.txt")
if fail.exists():
    print(json.dumps({"protocol": 1, "ok": False, "error": fail.read_text(), "messages": []}))
    sys.exit(1)
game = Path(a["--game"]) / "bin"
name = Path(__file__).with_name("name.txt")
name = name.read_text() if name.exists() else "dxgi.dll"
if cmd == "install":
    game.mkdir(parents=True, exist_ok=True)
    (game / "OptiScaler.ini").write_text("[HelixSR]\nWaveSize=auto\n")
    (game / "HelixSR-Scaler.files").write_text("# HelixSR Scaler\n# version=2.3.0\nname=%s\n%s\n" % (name, name))
    (game / "HelixSR").mkdir(exist_ok=True)
    (game / "HelixSR" / "helixsr.dll").write_bytes((rel / "HelixSR" / "helixsr.dll").read_bytes())
    (game / name).write_bytes(b"MZ OptiScaler")
    opts = None if name == "dxgi.dll" else 'WINEDLLOVERRIDES="%s=n,b" %%command%%' % Path(name).stem
    print(json.dumps({"protocol": 1, "ok": True, "game": {"installed": "scaler", "launch_options": opts},
                      "messages": []}))
elif cmd == "remove":
    for p in ("OptiScaler.ini", "HelixSR-Scaler.files", "HelixSR/helixsr.dll", name):
        (game / p).unlink()
    print(json.dumps({"protocol": 1, "ok": True, "game": {"installed": None}, "messages": []}))
'''


def scaler_release(built=True):
    """A 3.x release with HelixSR Scaler and the stand-in bridge; built: HLX DLSS's network next to its DLL."""
    d = release(built=True)
    write(d / main.BRIDGE, FAKE_BRIDGE)
    write(d / main.SCALER_PKG / "OptiScaler.dll", b"MZ OptiScaler")
    if built:
        for n in main.SEPARATE_FILES:
            write(d / "HelixSR" / n, b"net")
    return d


def calls(d):
    p = d / "setup" / "calls.json"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class ScalerTest(FakeHomeTest):
    def setUp(self):
        super().setUp()
        self.rel = scaler_release()
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        self.game = HOME / ".local/share/Steam/steamapps/common/Game"
        write(self.game / "bin/game.exe", b"MZ")
        write(self.game / "bin/nvngx_dlss.dll", b"MZ dlss")
        self._inside = main.inside_library
        main.inside_library = lambda p: True

    def tearDown(self):
        main.inside_library = self._inside

    def install(self):
        return asyncio.run(main.Plugin().install_scaler(str(self.game)))

    def opti(self):
        return main.opti_state(self.game / "bin", self.game)

    def test_release_offers_scaler_with_hlx_dlss_built(self):
        v = next(v for v in main.local_versions() if v["tag"] == "v3.0.0")
        self.assertTrue(v["scaler"] and v["dlss_built"])
        self.assertTrue(main.helix_state()["scaler"])
        (self.rel / main.BRIDGE).unlink()
        self.assertFalse(main.release_scaler(self.rel))

    def test_install_runs_helixsrs_installer_for_this_game_only(self):
        r = self.install()
        self.assertTrue(r["ok"], r)
        self.assertEqual(calls(self.rel), [["install", "--game", str(self.game), "--way", "scaler",
                                           "--scaler", str(self.rel / main.SCALER_PKG)]])
        self.assertNotIn("--yes", calls(self.rel)[0])
        st = self.opti()
        self.assertEqual((st["installed_kind"], st["helix_version"], st["upscaler"]), ("scaler", "3.0.0", "HLX DLSS"))
        self.assertEqual((st["scaler_version"], st["scaler_launch"]), ("2.3.0", None))   # dxgi.dll: no launch option

    def test_another_dll_name_needs_a_launch_option(self):
        write(self.rel / "setup/name.txt", "winmm.dll")
        r = self.install()
        self.assertIn("launch option", r["message"])
        self.assertEqual(self.opti()["scaler_launch"], 'WINEDLLOVERRIDES="winmm=n,b"')

    def test_remove_runs_the_installers_remove(self):
        self.install()
        r = asyncio.run(main.Plugin().uninstall_scaler(str(self.game)))
        self.assertTrue(r["ok"], r)
        self.assertEqual(calls(self.rel)[-1], ["remove", "--game", str(self.game)])
        self.assertFalse((self.game / "bin/OptiScaler.ini").exists())

    def test_not_built_or_no_scaler_is_refused_before_the_installer(self):
        for n in main.SEPARATE_FILES:
            (self.rel / "HelixSR" / n).unlink()
        r = self.install()
        self.assertFalse(r["ok"])
        self.assertIn("Build HelixSR 3.0.0 first", r["error"])
        self.assertEqual(calls(self.rel), [])

    def test_refused_next_to_another_optiscaler_or_helixsr_in_place_of_fsr(self):
        write(self.game / "bin/OptiScaler.ini", "[Upscalers]\nDx12Upscaler=auto\n")
        r = self.install()
        self.assertFalse(r["ok"])
        self.assertIn("already has an OptiScaler", r["error"])
        (self.game / "bin/OptiScaler.ini").unlink()
        fake_dll(self.game / "bin/amd_fidelityfx_dx12.dll", "2.0.0")
        r = self.install()
        self.assertFalse(r["ok"])
        self.assertIn("in place of the game's FSR", r["error"])
        self.assertEqual(calls(self.rel), [])

    def test_installer_error_is_shown_plainly(self):
        write(self.rel / "setup/fail.txt", "the network is not built yet")
        r = self.install()
        self.assertFalse(r["ok"])
        self.assertIn("isn't built for this release yet", r["error"])

    def test_scalers_own_folders_are_not_the_games_fsr(self):
        self.install()
        write(self.game / "bin/OptiScaler/amd_fidelityfx_upscaler_dx12.dll", b"MZ HLX FSR 4 (4.1.2)")
        write(self.game / "bin/HelixSR-Scaler-backup/amd_fidelityfx_upscaler_dx12.dll", b"MZ game")
        dlls, opti = main.scan_folder(self.game)
        self.assertEqual((dlls, opti), ([], [self.game / "bin"]))


class ScalerCheckTest(FakeHomeTest):
    def test_the_newest_log_names_the_upscaler_used(self):
        o = HOME / "g/bin"
        write(o / "HelixSR/helixsr.log", "model-e: network running (16-bit)\n")
        c = main.scaler_check(o)
        self.assertEqual((c["status"], c["upscaler"]), ("running", "HLX DLSS"))
        full = o / "OptiScaler/custom/HLX FSR 4 Full/ffx"
        from test_hlx_fsr4_full import fake_full
        fake_full(full / "amd_fidelityfx_upscaler_dx12.dll", one_file=True)
        log = write(full / main.HLX_FULL_LOG, "create: max render 1280x800 output 1280x800 flags 0x1 own kernels=1\n")
        import os, time
        later = time.time() + 5
        os.utime(log, (later, later))
        c = main.scaler_check(o)
        self.assertEqual((c["status"], c["upscaler"]), ("running", "HLX FSR 4 Full"))

    def test_no_log_yet(self):
        c = main.scaler_check(HOME / "g/bin")
        self.assertEqual((c["exists"], c["status"]), (False, "none"))
