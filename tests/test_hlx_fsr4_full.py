"""HelixSR 3.2.1+: HLX FSR 4 Full (AMD's full FSR 4 network), which HelixSR ships for HelixSR Scaler's list only. The
plugin puts it into a game's own OptiScaler like HLX FSR 4, with AMD's FSR SDK DLL from the release next to it.
Run: npm test."""
import asyncio
import struct

from support import HOME, FakeHomeTest, main, write
from test_hlx_fsr4 import OPTI_INI, OptiScalerInstallTest, built_20, release


def fake_full(path, built=True, one_file=False):
    """A stand-in HLX FSR 4 Full DLL: its start-up log line in the code, its data behind HLXFULL2. Up to 3.3.0 it names
    AMD's FSR SDK DLL it runs on; from 3.4.0 (one_file) it names none."""
    data = b"MZ" + b"\0" * 64 + (b"HLX FSR 4: reuse=%d dir=%s\0" if one_file else
                                b"HLX FSR 4: full=%d reuse=%d dir=%s\0%s\\amd_fidelityfx_upscaler_dx12.amd.dll\0")
    if built:
        payload = b"F" * 32
        data += payload + main.HLX_FULL_MAGIC + struct.pack("<Q", len(payload)) + b"\0" * 8
    return write(path, data)


def release_with_full(built=True, sdk=True, one_file=False):
    d = release(built=True)
    ffx = d / main.RELEASE_FULL_DIR
    fake_full(ffx / "amd_fidelityfx_upscaler_dx12.dll", built, one_file)
    write(ffx / main.HLX_FULL_INI, "[HLX]\nDeepReuse = exact\n")
    if sdk:
        write(d / main.RELEASE_SDK_DLL, b"MZ AMD FSR SDK 2.4.0 upscaler")
    return d


class ReleaseTest(FakeHomeTest):
    def test_recognized_but_not_the_release_dll(self):
        d = release_with_full()
        full = main.release_full_dll(d)
        self.assertEqual(full, d / main.RELEASE_FULL_DIR / "amd_fidelityfx_upscaler_dx12.dll")
        self.assertTrue(main.is_helixsr(full) and main.is_hlx(full) and main.is_hlx_full(full))
        self.assertTrue(main.has_network(full))
        self.assertEqual(main.upscaler_name(full), "HLX FSR 4 Full")
        self.assertEqual(main.hlx_release_dir(full), d)
        # HLX FSR 4 stays what the release puts into games
        self.assertEqual(main.upscaler_name(main.release_dll(d)), "HLX FSR 4")
        self.assertFalse(main.is_hlx_full(main.release_dll(d)))

    def test_only_with_its_data_and_amds_sdk_dll(self):
        self.assertIsNone(main.release_full_dll(release()))   # 3.0 - 3.2.0: none
        self.assertIsNone(main.release_full_dll(release_with_full(built=False)))
        d = release_with_full()
        (d / main.RELEASE_SDK_DLL).unlink()
        self.assertIsNone(main.release_full_dll(d))

    def test_340_one_file_needs_no_amd_dll(self):
        d = release_with_full(sdk=False, one_file=True)
        full = main.release_full_dll(d)
        self.assertEqual(main.upscaler_name(full), "HLX FSR 4 Full")
        self.assertFalse(main.full_needs_amd(full))
        self.assertEqual(main.hlx_release_dir(full), d)

    def test_listed(self):
        release_with_full()
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        v = next(v for v in main.local_versions() if v["tag"] == "v3.0.0")
        self.assertTrue(v["full"])
        self.assertTrue(main.helix_state()["full"])


class InstallTest(FakeHomeTest):
    def setUp(self):
        super().setUp()
        self.d = release_with_full()
        built_20()
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v3.0.0"})
        self.o = OptiScalerInstallTest.opti(self)
        self.sub = self.o / main.OPTI_SUBDIR
        self._inside = main.inside_library
        main.inside_library = lambda p: True

    def tearDown(self):
        main.inside_library = self._inside

    def install(self, full=False, tag=None):
        r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, False, tag, full))
        self.assertTrue(r["ok"], r)
        return main.opti_state(self.o, self.o)

    def test_full_runs_on_the_releases_sdk_dll_with_its_settings(self):
        st = self.install(full=True)
        self.assertEqual((st["configured"], st["helix_version"], st["upscaler"]), (True, "3.0.0", "HLX FSR 4 Full"))
        self.assertTrue(main.is_hlx_full(self.sub / "amd_fidelityfx_upscaler_dx12.dll"))
        self.assertEqual((self.sub / main.FSR4_COPY_NAME).read_bytes(), b"MZ AMD FSR SDK 2.4.0 upscaler")
        self.assertEqual((self.sub / main.HLX_FULL_INI).read_text(), "[HLX]\nDeepReuse = exact\n")
        text = (self.o / "OptiScaler.ini").read_text()
        self.assertEqual(main.ini_get(text, "Libraries", "FfxDx12SRPath"),
                         main.win_path(self.sub / "amd_fidelityfx_upscaler_dx12.dll"))
        self.assertEqual(main.ini_get(text, "Libraries", "FfxDx12Path"), "auto")
        main.uninstall_optiscaler(self.o)
        self.assertEqual((self.o / "OptiScaler.ini").read_text(), OPTI_INI)
        self.assertFalse(self.sub.exists())

    def test_switch_between_hlx_fsr4_full_and_20_keeps_edited_settings(self):
        self.assertEqual(self.install()["upscaler"], "HLX FSR 4")
        self.assertEqual(self.install(full=True)["upscaler"], "HLX FSR 4 Full")
        write(self.sub / main.HLX_FULL_INI, "[HLX]\nDeepReuse = 1:2\n")
        write(self.sub / main.HLX_FULL_LOG, "HLX FSR 4: full=1 reuse=0 dir=x\n")
        self.assertEqual(self.install()["upscaler"], "HLX FSR 4")
        self.assertFalse((self.sub / main.HLX_FULL_LOG).exists())
        self.assertEqual(self.install(tag="v2.0.0")["upscaler"], None)
        self.assertEqual(self.install(full=True)["upscaler"], "HLX FSR 4 Full")
        self.assertEqual((self.sub / main.HLX_FULL_INI).read_text(), "[HLX]\nDeepReuse = 1:2\n")
        main.uninstall_optiscaler(self.o)
        self.assertEqual((self.o / "OptiScaler.ini").read_text(), OPTI_INI)

    def test_340_one_file_gets_no_amd_dll_and_keeps_the_games_fsr4(self):
        fake_full(self.d / main.RELEASE_FULL_DIR / "amd_fidelityfx_upscaler_dx12.dll", one_file=True)
        (self.d / main.RELEASE_SDK_DLL).unlink()
        self.assertEqual(self.install(full=True)["upscaler"], "HLX FSR 4 Full")
        self.assertFalse((self.sub / main.FSR4_COPY_NAME).exists())
        write(self.sub / main.FSR4_COPY_NAME, b"MZ the game's FSR 4")   # from an HLX FSR 4 install before
        self.install(full=True)
        self.assertEqual((self.sub / main.FSR4_COPY_NAME).read_bytes(), b"MZ the game's FSR 4")

    def test_refused_when_the_release_has_none(self):
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v2.0.0"})
        r = asyncio.run(main.Plugin().install_optiscaler(str(self.o), True, True, False, None, True))
        self.assertFalse(r["ok"])
        self.assertIn("no HLX FSR 4 Full", r["error"])


class LogTest(FakeHomeTest):
    def check(self, log):
        f = HOME / "Games/L"
        fake_full(f / "amd_fidelityfx_upscaler_dx12.dll")
        fake_hlx_log = f / main.HLX_LOG   # an older HLX FSR 4 log next to it isn't the one read
        write(fake_hlx_log, "own runtime active: wave32\n")
        write(f / main.HLX_FULL_LOG, log)
        return main.helix_log_check(f)

    def test_running_with_the_render_size(self):
        c = self.check("HLX FSR 4: full=1 reuse=0 dir=Z:\\g\n"
                       "create: max render 1280x800 output 1280x800 flags 0x1 own kernels=1\n"
                       "own runtime: family 2 inv 0 ae 1, output 1280x800 max render 1280x800 flags 0x1\n"
                       "frame 120 psos 9 render 853x533 out 1280x800 fmt c10 o10 mv16 mvscale 1.000,1.000 flags 0x1\n")
        self.assertEqual((c["status"], c["log"]), ("running", main.HLX_FULL_LOG))
        u = c["last_upscale"]
        self.assertEqual((u["render"], u["output"], u["mode"], u["per_frame"]), ("853x533", "1280x800", "Quality", True))

    def test_loaded_only(self):
        self.assertEqual(self.check("HLX FSR 4: full=1 reuse=0 dir=Z:\\g\n")["status"], "loaded")

    def test_amds_fsr_missing(self):
        self.assertEqual(self.check("HLX FSR 4: full=1 reuse=0 dir=Z:\\g\ncannot load AMD's FSR (126)\n")["status"], "error")

    def test_340_start_and_pipeline_error(self):
        self.assertEqual(self.check("HLX FSR 4: reuse=0 dir=Z:\\g\n")["status"], "loaded")
        self.assertEqual(self.check("create: max render 1280x800 output 1280x800 flags 0x1 own kernels=1\n"
                                    "runtime: pipeline 0123456789ab failed\n")["status"], "error")

    def test_settings_not_covered(self):
        c = self.check("create: max render 1280x800 output 1280x800 flags 0x1 own kernels=1\n"
                       "settings not covered by the own runtime: not created\n")
        self.assertEqual(c["status"], "fallback")
