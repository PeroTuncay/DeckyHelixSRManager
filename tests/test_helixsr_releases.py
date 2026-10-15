"""How the plugin deals with HelixSR's releases: which zip it downloads, how it runs the setup, which settings and
defaults an installed DLL has, and installs made by other HelixSR tools. Run: npm test."""
import json
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
        self.assertEqual([Path(cmd[1]).name, *cmd[2:]], ["helixsr-setup.sh", "--yes", "--rebuild", "--no-fg"])

    def test_freeware_setup_without_the_switch(self):
        s = self.script("# HelixSR Freeware License\n--rebuild\n# --- games ---\n")
        self.assertEqual(main.setup_command(s, s.parent, False)[2:], ["--yes"])


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

    def test_plain_optiscaler_is_not_scaler(self):
        g = game(HOME / "Games/Plain", "game.exe")
        write(g / "OptiScaler.ini", "[Upscalers]\nDx12Upscaler=auto\n")
        self.assertFalse(main.is_scaler(g))


if __name__ == "__main__":
    unittest.main()
