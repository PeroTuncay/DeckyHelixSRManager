"""What the game list shows: games HelixSR can use (FSR 3.1, OptiScaler) and games that only need OptiScaler first
(DLSS, XeSS, FSR 2), with a plain hint instead of being hidden. Run: npm test."""
import asyncio
import time

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


class LastSessionStartTest(FakeHomeTest):
    """Steam's LastPlayed is written again when a game quits; the session's start comes from gameprocess_log.txt."""

    LOG = HOME / ".local/share/Steam/logs/gameprocess_log.txt"

    @staticmethod
    def at(stamp):
        return time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))

    def test_first_process_of_the_last_session(self):
        write(self.LOG, "\n".join([
            "[2026-10-28 14:20:00] AppID 292030 adding PID 100 as a tracked process \"x\"",
            "[2026-10-28 14:28:24] Remove 292030 from running list",
            "[2026-10-28 14:41:03] AppID 292030 adding PID 8860 as a tracked process \"x\"",
            "[2026-10-28 14:41:09] AppID 292030 adding PID 9046 as a tracked process",
            "[2026-10-28 14:42:00] AppID 2920300 adding PID 9100 as a tracked process",
            "[2026-10-28 14:46:21] AppID 292030 no longer tracking PID 8860, exit code 0",
            "[2026-10-28 14:46:21] Remove 292030 from running list",
            "[2026-10-28 14:50:00] Remove 2920300 from running list", ""]))
        self.assertEqual(main.last_session_start(292030), self.at("2026-10-28 14:41:03"))
        self.assertEqual(main.last_session_start("2920300"), self.at("2026-10-28 14:42:00"))

    def test_a_running_session_and_no_log(self):
        self.assertIsNone(main.last_session_start(292030))
        write(self.LOG, "[2026-10-28 15:00:00] AppID 292030 adding PID 1 as a tracked process\n")
        self.assertEqual(main.last_session_start(292030), self.at("2026-10-28 15:00:00"))
        self.assertIsNone(main.last_session_start(1))

    def test_only_the_end_of_a_big_log_is_read(self):
        old = main.GAMEPROCESS_TAIL
        main.GAMEPROCESS_TAIL = 100
        try:
            write(self.LOG, "[2026-10-01 10:00:00] AppID 7 adding PID 1 as a tracked process\n" + "x" * 200 + "\n"
                  "[2026-10-02 10:00:00] AppID 8 adding PID 2 as a tracked process\n")
            self.assertIsNone(main.last_session_start(7))
            self.assertEqual(main.last_session_start(8), self.at("2026-10-02 10:00:00"))
        finally:
            main.GAMEPROCESS_TAIL = old
