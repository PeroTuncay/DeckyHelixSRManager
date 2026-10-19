"""How the plugin deals with HelixSR's releases: which zip it downloads, how it runs the setup, which settings and
defaults an installed DLL has, and installs made by other HelixSR tools. Run: npm test."""
import asyncio
import json
import struct
import unittest
from pathlib import Path

from support import HOME, FakeHomeTest, game, main, write


def fake_dll(path, version, settings=()):
    """A stand-in HelixSR DLL: the version string HelixSR carries, and the setting names it reads (UTF-16)."""
    data = b"MZ" + b"\0" * 64 + b"\0HelixSR " + version.encode() + b"\0"
    for s in settings:
        data += s.encode("utf-16-le") + b"\0\0"
    return write(path, data)


class ReleaseZipTest(unittest.TestCase):
    def test_picks_helixsrs_own_zip_among_several(self):
        assets = [{"name": "HelixSR-Scaler-1.0.0.zip"}, {"name": "HelixSR-Desktop_1.0.0_amd64.AppImage"},
                  {"name": "SHA256SUMS.txt"}, {"name": "HelixSR-1.9.0.zip"}]
        self.assertEqual(main.release_zip(assets)["name"], "HelixSR-1.9.0.zip")

    def test_replaced_zip_names_and_fallbacks(self):
        self.assertEqual(main.release_zip([{"name": "HelixSR-1.9.0.2.zip"}])["name"], "HelixSR-1.9.0.2.zip")
        self.assertEqual(main.release_zip([{"name": "HelixSR-Scaler-1.0.0.zip"}, {"name": "helix.zip"}])["name"],
                         "helix.zip")
        self.assertIsNone(main.release_zip([{"name": "HelixSR-Scaler-1.0.0.zip"}, {"name": "notes.txt"}]))


class SetupCommandTest(FakeHomeTest):
    def script(self, text):
        return write(HOME / "HelixSR/v/helixsr-setup.sh", text)

    def test_freeware_setup_runs_unmodified_without_frame_generation(self):
        s = self.script("# HelixSR Freeware License\n--rebuild\n--no-fg) ;;\n# --- games ---\n")
        cmd = main.setup_command(s, s.parent, True)
        self.assertEqual([Path(cmd[1]).name, *cmd[2:]], ["helixsr-setup.sh", "--rebuild", "--no-fg"])

    def test_freeware_setup_without_the_switch(self):
        s = self.script("# HelixSR Freeware License\n--rebuild\n# --- games ---\n")
        self.assertEqual(main.setup_command(s, s.parent, False)[2:], [])


class DllSettingsTest(FakeHomeTest):
    def test_pre_release_190_sharpens_by_default_and_reads_int8(self):
        d = HOME / "Games/A/HelixSR"
        fake_dll(d / "amd_fidelityfx_dx12.dll", "1.9.0", ["Int8", "Sharpener", "Sharpness"])
        v = main.helix_ini_values(d)
        self.assertEqual((v["sharpener_default"], v["sharpness_default"], v["int8_supported"]), ("nvidia", "0.1", True))

    def test_released_190_no_sharpening_by_default_and_no_int8(self):
        d = HOME / "Games/B/HelixSR"
        fake_dll(d / "amd_fidelityfx_dx12.dll", "1.9.0", ["Sharpener", "Sharpness", "WaveSize"])
        v = main.helix_ini_values(d)
        self.assertEqual((v["sharpener_default"], v["sharpness_default"], v["int8_supported"]), ("off", "0.1", False))

    def test_193_reads_int8_again_but_doesnt_sharpen_by_default(self):
        d = HOME / "Games/D/HelixSR"
        fake_dll(d / "amd_fidelityfx_dx12.dll", "1.9.3", ["Int8", "Sharpener", "Sharpness", "WaveSize"])
        v = main.helix_ini_values(d)
        self.assertEqual((v["sharpener_default"], v["sharpness_default"], v["int8_supported"]), ("off", "0.1", True))

    def test_181_defaults(self):
        d = HOME / "Games/C/HelixSR"
        fake_dll(d / "amd_fidelityfx_dx12.dll", "1.8.1", ["Sharpener", "Sharpness"])
        v = main.helix_ini_values(d)
        self.assertEqual((v["sharpener_default"], v["sharpness_default"], v["int8_supported"]), ("off", "0.5", False))

    def test_off_is_kept_as_a_setting_where_off_isnt_the_default(self):
        d = HOME / "Games/A/HelixSR"
        fake_dll(d / "amd_fidelityfx_dx12.dll", "1.9.0", ["Int8"])
        off = main.ini_set("", "Sharpening", "Sharpener", "off")
        self.assertFalse(main.ini_holds_only_defaults(off, main.ini_defaults(d)))
        d2 = HOME / "Games/B/HelixSR"
        fake_dll(d2 / "amd_fidelityfx_dx12.dll", "1.9.0", ["Sharpener"])
        self.assertTrue(main.ini_holds_only_defaults(off, main.ini_defaults(d2)))

    def test_real_190_dlls_if_present(self):
        """The two real 1.9.0 DLLs (pre-release and release), when HELIXSR_REAL_DLLS points at a folder holding them
        as pre.dll and final.dll; skipped otherwise (HelixSR's files aren't part of this repo)."""
        import os
        folder = os.environ.get("HELIXSR_REAL_DLLS")
        if not folder:
            self.skipTest("HELIXSR_REAL_DLLS not set")
        self.assertIn("Int8", main.dll_setting_keys(Path(folder) / "pre.dll"))
        self.assertNotIn("Int8", main.dll_setting_keys(Path(folder) / "final.dll"))


class HeroicAmazonTest(FakeHomeTest):
    def test_amazon_list_in_either_place(self):
        a, b = game(HOME / "Games/A", "a.exe"), game(HOME / "Games/B", "b.exe")
        write(HOME / ".config/heroic/nile_config/nile/installed.json",
              json.dumps({"installed": [{"install_path": str(a), "title": "A"}]}))
        write(HOME / ".config/heroic/nile_config/installed.json",
              json.dumps({"installed": [{"install_path": str(b), "title": "B"}]}))
        self.assertEqual(sorted((g["name"], g["store"]) for g in main.heroic_games()), [("A", "Amazon"), ("B", "Amazon")])


class ScalerInstallTest(FakeHomeTest):
    """HelixSR Scaler (from HelixSR Desktop): OptiScaler with HelixSR built in, a [HelixSR] section in OptiScaler.ini
    and HelixSR in a HelixSR folder next to it, the same folder name the plugin uses."""

    def setUp(self):
        super().setUp()
        self.g = game(HOME / "Games/Scaled", "game.exe")
        write(self.g / "OptiScaler.ini", "[Upscalers]\nDx12Upscaler=auto\n\n[HelixSR]\nGpuMode=auto\n")
        fake_dll(self.g / "HelixSR/amd_fidelityfx_dx12.dll", "1.9.0", ["Sharpener"])

    def test_shown_as_scaler_and_configured(self):
        st = main.opti_state(self.g, self.g)
        self.assertEqual((st["installed_kind"], st["configured"], st["helix_version"]), ("scaler", True, "1.9.0"))

    def test_left_alone(self):
        with self.assertRaises(RuntimeError) as e:
            main.refuse_official(self.g)
        self.assertIn("HelixSR Scaler", str(e.exception))

    def test_recognized_by_its_file_list_too(self):
        g = game(HOME / "Games/Listed", "game.exe")
        write(g / "OptiScaler.ini", "[Upscalers]\nDx12Upscaler=auto\n")
        write(g / "HelixSR-Scaler.files", "dxgi.dll\nOptiScaler.ini\n")
        self.assertTrue(main.is_scaler(g))

    def test_plain_optiscaler_is_not_scaler(self):
        g = game(HOME / "Games/Plain", "game.exe")
        write(g / "OptiScaler.ini", "[Upscalers]\nDx12Upscaler=auto\n")
        self.assertFalse(main.is_scaler(g))


if __name__ == "__main__":
    unittest.main()


class Release200Test(FakeHomeTest):
    """HelixSR 2.0: the DLL and its helixsr.ini in HelixSR-fsrfg, Sharpness 0.5 by default, and a setup whose --yes
    would also answer its game installer (install into every game), so the plugin must never pass it."""

    def release(self):
        d = HOME / "HelixSR/v2.0.0"
        fake_dll(d / "HelixSR-fsrfg/amd_fidelityfx_dx12.dll", "2.0.0", ["Int8", "Sharpener", "Sharpness"])
        write(d / "HelixSR-fsrfg/helixsr.ini", "[Sharpening]\nSharpener = off\nSharpness = 0.5\n")
        write(d / "setup/helixsr_setup.py",
              "DLSS_URL = 'https://raw.githubusercontent.com/NVIDIA/DLSS/v310.7.0/lib/Windows_x86_64/rel/nvngx_dlss.dll'\n"
              "DLSS_SHA256 = '" + "ab" * 32 + "'\n")
        return d

    def test_dll_and_ini_found_in_helixsr_fsrfg(self):
        d = self.release()
        self.assertEqual(main.release_dll(d), d / "HelixSR-fsrfg/amd_fidelityfx_dx12.dll")
        self.assertEqual(main.release_ini(d), d / "HelixSR-fsrfg/helixsr.ini")

    def test_200_defaults(self):
        d = HOME / "Games/E/HelixSR"
        fake_dll(d / "amd_fidelityfx_dx12.dll", "2.0.0", ["Int8", "Sharpener", "Sharpness"])
        v = main.helix_ini_values(d)
        self.assertEqual((v["sharpener_default"], v["sharpness_default"], v["int8_supported"]), ("off", "0.5", True))

    def test_nvidia_download_read_from_the_release(self):
        self.assertEqual(main.dlss_download(self.release()),
                         ("https://raw.githubusercontent.com/NVIDIA/DLSS/v310.7.0/lib/Windows_x86_64/rel/nvngx_dlss.dll",
                          "ab" * 32))

    def test_a_download_from_elsewhere_is_refused(self):
        d = self.release()
        write(d / "setup/helixsr_setup.py", "DLSS_URL = 'https://example.com/nvngx_dlss.dll'\nDLSS_SHA256 = '" + "ab" * 32 + "'\n")
        self.assertIsNone(main.dlss_download(d))

    def test_freeware_setup_never_gets_yes(self):
        s = write(HOME / "HelixSR/v/helixsr-setup.sh",
                  "# HelixSR Freeware License\n--rebuild\n--no-fg) ;;\n--yes|-y) ASSUME_YES=1; INST+=(--yes) ;;\n")
        cmd = main.setup_command(s, s.parent, False, Path("/tmp/nvngx_dlss.dll"))
        self.assertNotIn("--yes", cmd)
        self.assertEqual(cmd[2:], ["--no-fg", "--dlss", "/tmp/nvngx_dlss.dll"])

    def test_built_network_in_helixsr_fsrfg_counts(self):
        d = self.release()
        dll = d / "HelixSR-fsrfg/amd_fidelityfx_dx12.dll"
        dll.write_bytes(dll.read_bytes() + b"W" * 8 + b"P" * 8 + main.EMBED_MAGIC + struct.pack("<QQQ", 8, 8, 1))
        self.assertTrue(main.has_network(main.release_dll(d)))


class SetupWrapperTest(FakeHomeTest):
    """The plugin's real start_setup for a 1.9+ setup: NVIDIA's DLL is downloaded and verified first, the setup gets
    --dlss and --no-fg but never --yes, no input, and the DLL is deleted afterwards. The download is pointed at a local
    file; the stand-in setup records how it was started."""

    def test_wrapper_downloads_verifies_runs_and_cleans_up(self):
        import hashlib
        import os
        import time
        d = HOME / "HelixSR/v2.0.0"
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v2.0.0"})
        nvidia = write(HOME / "nvidia/nvngx_dlss.dll", b"NVIDIA DLL")
        record = HOME / "record.txt"
        write(d / "helixsr-setup.sh",
              "# HelixSR Freeware License\n# --rebuild --no-fg\n"
              f'{{ echo "args: $*"; dl="${{@: -1}}"; [ -f "$dl" ] && echo "dll there"; '
              f'read -r x && echo "got input" || echo "no input"; }} > "{record}"\n')
        write(d / "setup/helixsr_setup.py", "")
        url, sha = nvidia.as_uri(), hashlib.sha256(b"NVIDIA DLL").hexdigest()
        orig = main.dlss_download
        main.dlss_download = lambda release: (url, sha)
        try:
            async def go():
                r = await main.Plugin().start_setup("v2.0.0")
                self.assertTrue(r["ok"], r)
                for _ in range(100):
                    if main.SETUP_RC.exists():
                        break
                    await asyncio.sleep(0.05)
            asyncio.run(go())
        finally:
            main.dlss_download = orig
        time.sleep(0.1)
        self.assertTrue(record.exists(), main.SETUP_LOG.read_text())
        rec = record.read_text()
        self.assertIn("--no-fg --dlss", rec)
        self.assertNotIn("--yes", rec)
        self.assertIn("dll there", rec)
        self.assertIn("no input", rec)
        self.assertEqual(main.SETUP_RC.read_text().strip(), "0")
        self.assertFalse((main.SETUP_TMP / "nvngx_dlss.dll").exists())
        self.assertIn("downloading nvngx_dlss.dll from NVIDIA", main.SETUP_LOG.read_text())

    def test_a_wrong_checksum_stops_before_the_setup(self):
        d = HOME / "HelixSR/v2.0.0"
        main.save_settings({"helix_dir": str(HOME / "HelixSR"), "active": "v2.0.0"})
        nvidia = write(HOME / "nvidia/nvngx_dlss.dll", b"something else")
        record = HOME / "record.txt"
        write(d / "helixsr-setup.sh", f'# HelixSR Freeware License\necho ran > "{record}"\n')
        write(d / "setup/helixsr_setup.py", "")
        orig = main.dlss_download
        main.dlss_download = lambda release: (nvidia.as_uri(), "00" * 32)
        try:
            async def go():
                await main.Plugin().start_setup("v2.0.0")
                for _ in range(100):
                    if main.SETUP_RC.exists():
                        break
                    await asyncio.sleep(0.05)
            asyncio.run(go())
        finally:
            main.dlss_download = orig
        self.assertFalse(record.exists())
        self.assertNotEqual(main.SETUP_RC.read_text().strip(), "0")
        self.assertIn("could not be downloaded or verified", main.SETUP_LOG.read_text())
