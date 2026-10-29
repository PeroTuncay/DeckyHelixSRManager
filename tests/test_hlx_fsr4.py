"""HelixSR 3.0: HLX FSR 4 (AMD's FSR 4 network on HelixSR's pipeline) is the FSR drop-in. Its shaders are built by the
setup from AMD's FSR 4 driver file, which the setup downloads only after a yes on a terminal, so the plugin builds it in
a second step. Run: npm test."""
import asyncio
import hashlib
import json
import os
import stat
import struct
import time
from pathlib import Path

from support import HOME, FakeHomeTest, main, write
from test_helixsr_releases import fake_dll


def fake_hlx(path, built=False):
    """A stand-in HLX FSR 4 DLL; built: with the shaders the setup appends (data, tag, size, 8 more bytes)."""
    data = b"MZ" + b"\0" * 64 + b"HLX FSR 4 (4.1.2)\0"
    if built:
        payload = b"S" * 32
        data += payload + main.HLX_DATA_MAGIC + struct.pack("<Q", len(payload)) + b"\0" * 8
    return write(path, data)


def release(built=False):
    d = HOME / "HelixSR/v3.0.0"
    fake_hlx(d / "HLX-FSR4/amd_fidelityfx_upscaler_dx12.dll", built)
    fake_dll(d / "HelixSR/helixsr.dll", "3.0.0", ["Int8", "Sharpener", "Sharpness"])
    write(d / "HelixSR/helixsr.ini", "[Sharpening]\nSharpener = off\n")
    write(d / "setup/hlxfsr4/hlx/amd.py", "")
    write(d / "setup/helixsr_setup.py", "")
    return d


class Release300Test(FakeHomeTest):
    def test_hlx_fsr4_is_the_release_dll(self):
        d = release()
        dll = main.release_dll(d)
        self.assertEqual(dll, d / "HLX-FSR4/amd_fidelityfx_upscaler_dx12.dll")
        self.assertTrue(main.is_helixsr(dll))
        self.assertEqual(main.upscaler_name(dll), "HLX FSR 4")
        self.assertEqual(main.release_version(d), "3.0.0")
        self.assertEqual(main.dll_kind(dll), "ffx")

    def test_built_means_hlx_fsr4_shaders_appended(self):
        self.assertFalse(main.has_network(main.release_dll(release(built=False))))
        self.assertTrue(main.has_network(main.release_dll(release(built=True))))

    def test_listed_with_its_version(self):
        release(built=True)
        main.save_settings({"helix_dir": str(HOME / "HelixSR")})
        v = next(v for v in main.local_versions() if v["tag"] == "v3.0.0")
        self.assertEqual((v["version"], v["built"], v["upscaler"]), ("3.0.0", True, "HLX FSR 4"))

    def test_amd_download_until_the_release_ships_amds_sdk_dll(self):
        # 3.0/3.1: HLX FSR 4 is built from AMD's driver package (downloaded); 3.2.0 ships it built plus AMD's FSR SDK
        # DLL, named by SDK_SHA256 in amd.py, which a rebuild uses instead
        d = release()
        self.assertTrue(main.hlx_amd_download(d))
        sdk = write(d / "helixsr-scaler/OptiScaler/amd_fidelityfx_upscaler_dx12.amd.dll", b"MZ sdk")
        self.assertTrue(main.hlx_amd_download(d))   # amd.py doesn't name the SDK DLL (3.1.0)
        write(d / "setup/hlxfsr4/hlx/amd.py", f"SDK_SHA256 = '{hashlib.sha256(b'MZ sdk').hexdigest()}'\n")
        self.assertFalse(main.hlx_amd_download(d))
        write(sdk, b"MZ other")
        self.assertTrue(main.hlx_amd_download(d))   # another file under that name
        self.assertFalse(main.hlx_amd_download(HOME / "HelixSR/v2.0.0"))

    def test_second_step_only_for_releases_with_hlx_fsr4(self):
        self.assertIsNotNone(main.hlx_step_script(release()))
        d = HOME / "HelixSR/v2.0.0"
        write(d / "setup/helixsr_setup.py", "")
        self.assertIsNone(main.hlx_step_script(d))

    def test_second_step_never_starts_the_game_installer(self):
        s = main.hlx_step_script(release())
        self.assertIn("--fg-only", s)
        self.assertNotIn("helixsr-setup.sh", s)
        self.assertNotIn("helixsr_install", s)


class DirectInstallTest(FakeHomeTest):
    def game_dll(self, name="amd_fidelityfx_upscaler_dx12.dll"):
        return write(HOME / "Games/G/bin" / name, b"MZ AMD FidelityFX upscaler")

    def test_install_keeps_the_games_fsr_as_original_and_writes_the_marker(self):
        d = release(built=True)
        t = self.game_dll()
        main.install_direct(t, main.release_dll(d), main.release_ini(d))
        self.assertTrue(main.is_hlx(t))
        self.assertEqual(main.original_of(t).read_bytes(), b"MZ AMD FidelityFX upscaler")
        rec = json.loads((t.parent / main.INSTALL_MARKER).read_text())
        self.assertEqual(rec, {"helixsr": "3.0.0", "upscaler": "HLX FSR 4", "files": [t.name], "route": "direct"})
        self.assertFalse((t.parent / "helixsr.ini").exists())   # HLX FSR 4 has no settings file
        self.assertEqual(main.helix_version(t), "3.0.0")

    def test_update_from_20_drops_an_unchanged_helixsr_ini(self):
        d = release(built=True)
        t = self.game_dll("amd_fidelityfx_dx12.dll")
        main.install_direct(t, fake_dll(HOME / "old/amd_fidelityfx_dx12.dll", "2.0.0"), Path("/nonexistent"))
        write(t.parent / "helixsr.ini", "[Sharpening]\nSharpener = off\nSharpness = 0.5\n")
        main.install_direct(t, main.release_dll(d), main.release_ini(d))
        self.assertTrue(main.is_hlx(t))
        self.assertFalse((t.parent / "helixsr.ini").exists())

    def test_disable_enable_and_uninstall(self):
        d = release(built=True)
        t = self.game_dll()
        main.install_direct(t, main.release_dll(d), main.release_ini(d))
        write(t.parent / main.HLX_LOG, "x")
        main.disable_direct(t)
        self.assertFalse(main.is_hlx(t))
        main.enable_direct(t)
        self.assertTrue(main.is_hlx(t))
        main.uninstall_direct(t, main.release_ini(d))
        self.assertEqual(t.read_bytes(), b"MZ AMD FidelityFX upscaler")
        self.assertFalse((t.parent / main.HLX_LOG).exists())
        self.assertFalse((t.parent / main.INSTALL_MARKER).exists())

    def test_settings_refused(self):
        d = release(built=True)
        t = self.game_dll()
        main.install_direct(t, main.release_dll(d), main.release_ini(d))
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        orig = main.inside_library
        main.inside_library = lambda p: True
        try:
            r = asyncio.run(main.Plugin().set_helix_option(str(t.parent), "sharpener", "rcas"))
        finally:
            main.inside_library = orig
        self.assertFalse(r["ok"])
        self.assertIn("no settings", r["error"])


OPTI_INI = """[Upscalers]
; fsr21, fsr22, fsr31, ffx, xess, dlss
Dx12Upscaler = auto
[Libraries]
FfxDx12Path = auto
FfxDx12SRPath = auto
"""


class OptiScalerInstallTest(FakeHomeTest):
    def opti(self):
        o = HOME / "Games/O"
        write(o / "OptiScaler.ini", OPTI_INI)
        write(o / "amd_fidelityfx_upscaler_dx12.dll", b"MZ AMD FSR 4 upscaler")
        write(o / "amd_fidelityfx_dx12.dll", b"MZ AMD FidelityFX")
        return o

    def test_hlx_fsr4_is_the_fsr_upscaler_with_amds_listed_after_it(self):
        d = release(built=True)
        o = self.opti()
        msg = main.install_optiscaler(o, main.release_dll(d), main.release_ini(d), False)
        sub = o / main.OPTI_SUBDIR
        self.assertIn("HLX FSR 4", msg)
        self.assertTrue(main.is_hlx(sub / "amd_fidelityfx_upscaler_dx12.dll"))
        self.assertEqual((sub / main.FSR4_COPY_NAME).read_bytes(), b"MZ AMD FSR 4 upscaler")
        self.assertFalse((sub / "amd_fidelityfx_dx12.dll").exists())
        text = (o / "OptiScaler.ini").read_text()
        self.assertEqual(main.ini_get(text, "Libraries", "FfxDx12Path"), "auto")   # the game's FidelityFX DLL stays
        self.assertEqual(main.ini_get(text, "Upscalers", "Dx12Upscaler"), "ffx")
        st = main.opti_state(o, o)
        self.assertTrue(st["configured"])
        self.assertEqual((st["helix_version"], st["upscaler"]), ("3.0.0", "HLX FSR 4"))
        main.uninstall_optiscaler(o)
        self.assertEqual((o / "OptiScaler.ini").read_text(), OPTI_INI)

    def test_switch_from_20_puts_ffxdx12path_back(self):
        o = self.opti()
        old = fake_dll(HOME / "old/amd_fidelityfx_dx12.dll", "2.0.0")
        main.install_optiscaler(o, old, Path("/nonexistent"), False)
        self.assertNotEqual(main.ini_get((o / "OptiScaler.ini").read_text(), "Libraries", "FfxDx12Path"), "auto")
        d = release(built=True)
        main.install_optiscaler(o, main.release_dll(d), main.release_ini(d), True)
        text = (o / "OptiScaler.ini").read_text()
        self.assertEqual(main.ini_get(text, "Libraries", "FfxDx12Path"), "auto")
        self.assertFalse((o / main.OPTI_SUBDIR / "amd_fidelityfx_dx12.dll").exists())
        main.uninstall_optiscaler(o)
        self.assertEqual((o / "OptiScaler.ini").read_text(), OPTI_INI)


class LogTest(FakeHomeTest):
    def folder(self, log):
        f = HOME / "Games/L"
        fake_hlx(f / "amd_fidelityfx_upscaler_dx12.dll", True)
        write(f / main.HLX_LOG, log)
        return f

    def test_running(self):
        c = main.helix_log_check(self.folder(
            "[10:00:00.000000] [I] HLX-FSR-4 GPU: AMD Custom GPU 0405 (PCI 1002:1435)\n"
            "[10:00:01.000000] [I] HLX-FSR-4 own runtime active: wave32 (tier 2), output 1280x800, max render 1280x800, flags 0x1\n"))
        self.assertEqual((c["status"], c["log"]), ("running", main.HLX_LOG))

    def test_not_built(self):
        c = main.helix_log_check(self.folder(
            "[10:00:00.000000] [I] HLX-FSR-4 HLX FSR 4's shaders are not built yet: run the HelixSR setup (AMD's FSR runs meanwhile)\n"))
        self.assertEqual(c["status"], "error")

    def test_amds_fsr_takes_over(self):
        c = main.helix_log_check(self.folder(
            "[10:00:00.000000] [I] HLX-FSR-4 create: HLX FSR 4 does not cover this (see the line above): AMD's original instead\n"))
        self.assertEqual(c["status"], "fallback")


class SetupProgressTest(FakeHomeTest):
    def test_second_step_progress(self):
        lines = ["[helixsr-setup] done: /x/HelixSR/helixsr.dll now carries the network (72 shaders, 7.5 MB, checked on disk)",
                 main.HLX_STEP_LINE + " (from AMD's FSR 4 file)",
                 "[helixsr-setup] [##########----------]  50%  0:30  HLX FSR 4 shaders"]
        pct, label = main.phase_of(lines)
        self.assertEqual(pct, 60 + 19)
        self.assertIn("HLX FSR 4 shaders", label)
        pct, label = main.phase_of(lines + ["[helixsr-setup] done: HLX FSR 4 built (812 shaders, checked) into /x"])
        self.assertEqual((pct, label), (100, "Finished"))


class SetupWrapper300Test(FakeHomeTest):
    """The real start_setup for a 3.0 release with stand-ins: the setup builds the network and stops at AMD's download
    (exit 1, as 3.0's does without a terminal); the second step then runs the release's helixsr_setup.py with
    --fg-only --yes through the setup's Python, compiler and Wine, and the setup itself never gets --yes."""

    def test_two_steps(self):
        d = release(built=False)
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        setup_rec, step_rec = HOME / "setup.txt", HOME / "step.txt"
        py = write(HOME / "fakepy/python3",
                   "#!/bin/bash\n"
                   f'if [ "$3" = --status ]; then [ -f "{step_rec}" ] && echo "network=1 fg=1 hlx=1" '
                   '|| echo "network=1 fg=1 hlx=0"; exit 0; fi\n'
                   f'echo "$*" > "{step_rec}"\n'
                   'echo "[helixsr-setup] done: HLX FSR 4 built (812 shaders, checked) into x"\n')
        os.chmod(py, os.stat(py).st_mode | stat.S_IEXEC)
        data = HOME / ".local/share/HelixSR"
        write(data / "dxc-wine.sh", f'WINEPREFIX="{data}/wineprefix" WINEDEBUG=-all exec "/opt/proton/bin/wine" '
                                    f'"{data}/dxc-win/bin/x64/dxc.exe" "${{args[@]}}"\n')
        write(data / "dxc-win-2609/bin/x64/dxc.exe", b"")
        write(d / "helixsr-setup.sh",
              "# HelixSR Freeware License\n# --rebuild --no-fg\n"
              f'echo "$*" > "{setup_rec}"\n'
              f'echo "[helixsr-setup] python: {py}"\n'
              "echo \"AMD's file is needed for HLX FSR 4\" >&2\n"
              'echo "[helixsr-setup] error: the setup stopped (exit 1)" >&2\nexit 1\n')
        orig = main.dlss_download
        nv = write(HOME / "nv.dll", b"N")
        main.dlss_download = lambda r: (nv.as_uri(), hashlib.sha256(b"N").hexdigest())
        try:
            async def go():
                r = await main.Plugin().start_setup("v3.0.0")
                self.assertTrue(r["ok"], r)
                for _ in range(200):
                    if main.SETUP_RC.exists():
                        break
                    await asyncio.sleep(0.05)
            asyncio.run(go())
        finally:
            main.dlss_download = orig
        time.sleep(0.1)
        log = main.SETUP_LOG.read_text()
        self.assertTrue(step_rec.exists(), log)
        self.assertNotIn("--yes", setup_rec.read_text())
        step = step_rec.read_text()
        for a in ("--fg-only", "--no-fg", "--yes", "--wine /opt/proton/bin/wine",
                  f"--dxc2609-dir {data}/dxc-win-2609/bin/x64", f"--dxc {data}/dxc-wine.sh"):
            self.assertIn(a, step)
        self.assertEqual(main.SETUP_RC.read_text().strip(), "0", log)
        st = main.setup_status()
        self.assertEqual(st["errors"], [])
        self.assertEqual(st["phase"], "Finished")


def built_ngx(path, version="3.1.0"):
    """A stand-in HLX DLSS (HelixSR/helixsr.dll) with the network the setup appends (weights, pak, footer)."""
    dll = fake_dll(path, version, ["Int8", "Sharpener", "Sharpness", "WaveSize"])
    dll.write_bytes(dll.read_bytes() + b"W" * 8 + b"P" * 8 + main.EMBED_MAGIC + struct.pack("<QQQ", 8, 8, 1))
    return dll


class HlxDlssTest(FakeHomeTest):
    """3.0+: HLX DLSS (HelixSR's DLSS network, made for HelixSR Scaler) in the game's own OptiScaler as its DLSS
    (NvngxPath, as 1.5's nvngx.dll), next to HLX FSR 4 as its FSR; either can replace the other."""

    def setUp(self):
        super().setUp()
        self.rel = release(built=True)
        built_ngx(self.rel / main.RELEASE_NGX_DLL)
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        self.o = OptiScalerInstallTest.opti(self)
        self._inside = main.inside_library
        main.inside_library = lambda p: True

    def tearDown(self):
        main.inside_library = self._inside

    def install(self, dlss):
        r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, dlss))
        self.assertTrue(r["ok"], r)
        return r["message"]

    def test_release_offers_hlx_dlss(self):
        self.assertEqual(main.release_ngx_dll(self.rel), self.rel / main.RELEASE_NGX_DLL)
        self.assertEqual(main.upscaler_name(self.rel / main.RELEASE_NGX_DLL), "HLX DLSS")
        self.assertEqual(main.release_ini(self.rel), self.rel / "HelixSR/helixsr.ini")
        v = next(v for v in main.local_versions() if v["tag"] == "v3.0.0")
        self.assertTrue(v["dlss_built"])
        self.assertTrue(main.helix_state()["dlss_built"])

    def test_not_built_is_refused(self):
        fake_dll(self.rel / main.RELEASE_NGX_DLL, "3.1.0")
        r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, True))
        self.assertFalse(r["ok"])
        self.assertIn("isn't built", r["error"])

    def test_install_as_optiscalers_dlss_with_settings(self):
        self.assertIn("as DLSS", self.install(True))
        sub = self.o / main.OPTI_SUBDIR
        text = (self.o / "OptiScaler.ini").read_text()
        self.assertEqual(main.ini_get(text, "Upscalers", "Dx12Upscaler"), "dlss")
        self.assertEqual(main.ini_get(text, "Libraries", "NvngxPath"), main.win_path(sub / "nvngx.dll"))
        st = main.opti_state(self.o, self.o)
        self.assertEqual((st["installed_kind"], st["configured"], st["upscaler"], st["helix_version"]),
                         ("ngx", True, "HLX DLSS", "3.1.0"))
        self.assertTrue(main.helix_ini_values(sub)["int8_supported"])   # HLX DLSS reads helixsr.ini

    def test_switch_between_both_and_remove(self):
        self.install(True)
        self.install(False)   # HLX FSR 4 in place of HLX DLSS
        st = main.opti_state(self.o, self.o)
        self.assertEqual((st["installed_kind"], st["upscaler"]), ("ffx", "HLX FSR 4"))
        self.assertFalse((self.o / main.OPTI_SUBDIR / "nvngx.dll").exists())
        text = (self.o / "OptiScaler.ini").read_text()
        self.assertEqual(main.ini_get(text, "Libraries", "NvngxPath"), "auto")
        self.install(True)    # and back
        self.assertEqual(main.opti_state(self.o, self.o)["upscaler"], "HLX DLSS")
        self.assertFalse((self.o / main.OPTI_SUBDIR / "amd_fidelityfx_upscaler_dx12.dll").exists())
        main.uninstall_optiscaler(self.o)
        text = (self.o / "OptiScaler.ini").read_text()   # (1.5's route writes NvngxPath = auto, OptiScaler's default)
        for s, k in (("Upscalers", "Dx12Upscaler"), ("Libraries", "FfxDx12Path"), ("Libraries", "FfxDx12SRPath"),
                     ("Libraries", "NvngxPath")):
            self.assertEqual(main.ini_get(text, s, k), "auto", k)
        self.assertFalse((self.o / main.OPTI_SUBDIR).exists())


class OptiHlxLogTest(FakeHomeTest):
    """Inside OptiScaler, HLX FSR 4 logs to OptiScaler.log, not HLX_FSR.log; its start-up lines come early."""

    def test_lines_found_in_optiscaler_log(self):
        d = release(built=True)
        o = OptiScalerInstallTest.opti(self)
        main.install_optiscaler(o, main.release_dll(d), main.release_ini(d), True)
        noise = "".join(f"[10:00:02.000] [D] frame {n}: FFX dispatch\n" for n in range(20000))
        write(o / "OptiScaler.log",
              "[10:00:00.000] [I] HLX-FSR-4 GPU: AMD Custom GPU 0405 (PCI 1002:1435)\n"
              "[10:00:01.000] [I] HLX-FSR-4 own runtime active: wave32 (tier 2), output 1280x800, max render 1280x800, flags 0x1\n"
              + noise)
        c = main.opti_hlx_check(o)
        self.assertEqual((c["status"], c["log"]), ("running", "OptiScaler.log"))

    def test_nothing_logged(self):
        d = release(built=True)
        o = OptiScalerInstallTest.opti(self)
        main.install_optiscaler(o, main.release_dll(d), main.release_ini(d), True)
        write(o / "OptiScaler.log", "[10:00:00.000] [I] OptiScaler started\n")
        self.assertFalse(main.opti_hlx_check(o)["exists"])


def built_20(version="2.0.0"):
    """A downloaded, built HelixSR 2.0 release: its own network in HelixSR-fsrfg/amd_fidelityfx_dx12.dll."""
    d = HOME / f"HelixSR/v{version}"
    dll = fake_dll(d / main.RELEASE_DLL_DIR / main.DLL_FFX, version, ["Int8", "Sharpener", "Sharpness"])
    dll.write_bytes(dll.read_bytes() + b"W" * 8 + b"P" * 8 + main.EMBED_MAGIC + struct.pack("<QQQ", 8, 8, 1))
    write(d / main.RELEASE_DLL_DIR / "helixsr.ini", "[Sharpening]\nSharpener = off\nSharpness = 0.5\n")
    return d


class OwnNetworkNextToHlxTest(FakeHomeTest):
    """3.x selected: HelixSR's own (DLSS) network comes from 2.0.0 in the same OptiScaler section, since HLX DLSS
    needs HelixSR Scaler (stock OptiScaler 0.10 never counts the Deck's GPU as DLSS-capable)."""

    def setUp(self):
        super().setUp()
        release(built=True)
        built_20()
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        self.o = OptiScalerInstallTest.opti(self)
        self._inside = main.inside_library
        main.inside_library = lambda p: True

    def tearDown(self):
        main.inside_library = self._inside

    def install(self, tag=None):
        r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, False, tag))
        self.assertTrue(r["ok"], r)
        return main.opti_state(self.o, self.o)

    def test_from_hlx_fsr4_to_20_and_back(self):
        self.assertEqual(self.install()["upscaler"], "HLX FSR 4")
        st = self.install("v2.0.0")
        self.assertEqual((st["helix_version"], st["upscaler"], st["installed_kind"]), ("2.0.0", None, "ffx"))
        sub = self.o / main.OPTI_SUBDIR
        text = (self.o / "OptiScaler.ini").read_text()
        self.assertEqual(main.ini_get(text, "Libraries", "FfxDx12Path"), main.win_path(sub / main.DLL_FFX))
        # AMD's FSR that HLX FSR 4 kept stays selectable after HelixSR 2.0.0
        self.assertEqual(main.ini_get((sub / "helixsr.ini").read_text(), "Forwarding", "UpscalerDll"),
                         main.FSR4_COPY_NAME)
        self.assertEqual((sub / main.FSR4_COPY_NAME).read_bytes(), b"MZ AMD FSR 4 upscaler")
        self.assertEqual(self.install()["upscaler"], "HLX FSR 4")
        self.assertFalse((sub / main.DLL_FFX).exists())
        main.uninstall_optiscaler(self.o)
        self.assertEqual((self.o / "OptiScaler.ini").read_text(), OPTI_INI)

    def test_removing_20_after_hlx_fsr4_restores_the_ini(self):
        self.install()
        self.install("v2.0.0")
        main.uninstall_optiscaler(self.o)
        self.assertEqual((self.o / "OptiScaler.ini").read_text(), OPTI_INI)

    def test_only_a_built_release_with_its_own_network(self):
        for tag in ("v3.0.0", "v1.9.9", "../x"):
            r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, False, tag))
            self.assertFalse(r["ok"], tag)
        fake_dll(HOME / "HelixSR/v2.0.0" / main.RELEASE_DLL_DIR / main.DLL_FFX, "2.0.0")   # not built
        r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, False, "v2.0.0"))
        self.assertFalse(r["ok"])
        self.assertIn("no network", r["error"])
