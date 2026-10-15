"""What the game list shows: games HelixSR can use (FSR 3.1, OptiScaler) and games that only need OptiScaler first
(DLSS, XeSS, FSR 2), with a plain hint instead of being hidden. Run: npm test."""
import asyncio

from support import HOME, FakeHomeTest, game, main, pe_exe, write


def run(coro):
    return asyncio.run(coro)


class UpscalerInputsTest(FakeHomeTest):
    def add(self, folder):
        r = run(main.Plugin().add_custom_game(str(folder)))
        self.assertTrue(r["ok"], r)
        return r["appid"]

    def listed(self, appid):
        return next(g for g in run(main.Plugin().list_games()) if g["appid"] == appid)

    def test_dlss_and_xess_game_is_listed_with_its_inputs(self):
        g = game(HOME / "Games/DeathStranding", "ds.exe", "nvngx_dlss.dll")
        write(g / "bin/libxess.dll", b"x")
        appid = self.add(g)
        entry = self.listed(appid)
        self.assertEqual((entry["inputs"], entry["fsr"], entry["optiscaler"]), (["DLSS", "XeSS"], False, False))
        detail = run(main.Plugin().get_game(appid))
        self.assertEqual((detail["inputs"], detail["inputs_dx11"], detail["direct"], detail["optiscaler"]),
                         (["DLSS", "XeSS"], None, [], []))

    def test_dlss_next_to_a_directx_11_exe_is_flagged(self):
        g = HOME / "Games/OldGame"
        pe_exe(g / "OldGame.exe", ["kernel32.dll", "d3d11.dll"])
        write(g / "nvngx_dlss.dll", b"x")
        detail = run(main.Plugin().get_game(self.add(g)))
        self.assertEqual(detail["inputs_dx11"], "OldGame.exe")

    def test_dlss_next_to_a_directx_12_exe_is_not_flagged(self):
        g = HOME / "Games/NewGame"
        pe_exe(g / "NewGame.exe", ["kernel32.dll", "d3d12.dll"])
        write(g / "nvngx_dlss.dll", b"x")
        self.assertIsNone(run(main.Plugin().get_game(self.add(g)))["inputs_dx11"])

    def test_fsr2_and_nothing_at_all(self):
        fsr2 = game(HOME / "Games/Fsr2", "a.exe", "ffx_fsr2_api_dx12_x64.dll")
        plain = game(HOME / "Games/Plain", "b.exe")
        self.assertEqual(self.listed(self.add(fsr2))["inputs"], ["FSR 2"])
        self.assertEqual(self.listed(self.add(plain))["inputs"], [])

    def test_pe_helper_is_read_like_a_real_exe(self):
        exe = pe_exe(HOME / "x/Game.exe", ["kernel32.dll", "d3d11.dll"])
        self.assertEqual(main.pe_imports(exe), {"kernel32.dll", "d3d11.dll"})
        self.assertEqual(main.exe_dx(exe), "dx11")
