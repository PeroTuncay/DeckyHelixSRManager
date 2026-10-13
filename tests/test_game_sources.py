"""Games from other stores (non-Steam): where they're read from, how they're combined, and which folders the plugin
may change. Run: npm test (or python3 -m unittest discover -s tests)."""
import asyncio
import json
import os
import sqlite3
import struct
import unittest

from support import HOME, FakeHomeTest, binary_kv, enable_stores, game, main, shortcuts_vdf, write


def run(coro):
    return asyncio.run(coro)


class BinaryVdfTest(unittest.TestCase):
    def test_reads_strings_ints_and_nested_maps(self):
        data = binary_kv({"shortcuts": {"0": {"AppName": "Hades", "appid": -1000, "LastPlayTime": 7}}})
        self.assertEqual(main.read_binary_vdf(data),
                         {"shortcuts": {"0": {"AppName": "Hades", "appid": -1000, "LastPlayTime": 7}}})

    def test_reads_uint64(self):
        data = b"\x07big\0" + struct.pack("<Q", 2 ** 40) + b"\x08"
        self.assertEqual(main.read_binary_vdf(data), {"big": 2 ** 40})

    def test_unknown_type_is_an_error(self):
        with self.assertRaises(ValueError):
            main.read_binary_vdf(b"\x05odd\0")


class SteamShortcutsTest(FakeHomeTest):
    def test_fields_unquoted_and_appid_unsigned(self):
        shortcuts_vdf([{"appid": -1000, "AppName": "Hades", "Exe": '"/g/Hades.exe"', "StartDir": '"/g/"',
                        "LaunchOptions": "-dx12", "LastPlayTime": 1760000000}])
        (s,) = main.steam_shortcuts()
        self.assertEqual(s, {"appid": 0xFFFFFFFF - 999, "name": "Hades", "exe": "/g/Hades.exe", "startdir": "/g/",
                             "launch": "-dx12", "last_played": 1760000000})

    def test_lowercase_keys_and_several_users(self):
        shortcuts_vdf([{"appid": 1, "appname": "A", "exe": "/a.exe", "startdir": "/"}], user="1")
        shortcuts_vdf([{"appid": 2, "AppName": "B", "Exe": "/b.exe", "StartDir": "/"}], user="2")
        self.assertEqual(sorted(s["name"] for s in main.steam_shortcuts()), ["A", "B"])

    def test_oversized_or_broken_file_is_skipped(self):
        f = shortcuts_vdf([{"appid": 1, "AppName": "A", "Exe": "/a.exe", "StartDir": "/"}])
        f.write_bytes(b"\x05broken")
        self.assertEqual(main.steam_shortcuts(), [])
        f.write_bytes(b"\0" * (main.MAX_VDF + 1))
        self.assertEqual(main.steam_shortcuts(), [])


class UnifideckTest(FakeHomeTest):
    def test_games_named_after_their_shortcut(self):
        hl2 = game(HOME / "Games/GOG/HL2", "hl2.exe")
        write(main.UNIFIDECK_MAP, f"gog:70={hl2}/hl2.exe\t{hl2}\t-123\n")
        shortcuts = [{"appid": -123 & 0xFFFFFFFF, "name": "Half-Life 2", "exe": "", "startdir": "",
                      "last_played": 99}]
        (g,) = main.unifideck_games(shortcuts)
        self.assertEqual((g["appid"], g["name"], g["path"], g["source"], g["last_played"]),
                         ("unifideck:gog:70", "Half-Life 2", str(hl2), "unifideck", 99))

    def test_missing_work_dir_uses_the_exe_folder_and_missing_folders_are_skipped(self):
        spire = game(HOME / "Games/Spire", "Spire.exe")
        write(main.UNIFIDECK_MAP, f"gog:55={spire}/Spire.exe\t\tnotanumber\nepic:x=/nope/x.exe\t/nope\t1\nno equals\n")
        (g,) = main.unifideck_games([])
        self.assertEqual((g["path"], g["name"], g["shortcut_appid"]), (str(spire), "Spire", None))

    def test_older_pipe_format_with_appids_from_the_registry_and_cloud_entries_skipped(self):
        # as found on a Deck (April 2026 Unifideck): "store:id|exe|work dir", cloud games "store:id|xcloud|url"
        crown = game(HOME / ".local/share/unifideck/prefixes/ubisoft/u1/pfx/drive_c/Games/Crown", "Crown.exe")
        write(main.UNIFIDECK_MAP, "microsoft:9ABC|xcloud|https://www.xbox.com/play/launch/9ABC\n"
                                  f"ubisoft:u1|{crown}/Crown.exe|{crown}/\n")
        write(main.UNIFIDECK_REGISTRY, json.dumps({
            "ubisoft:u1": {"appid": -1383214098, "appid_unsigned": 2911753198, "title": "Crown"},
            "microsoft:9ABC": {"appid": -5, "title": "Cloud Game"}}))
        shortcuts = [{"appid": 2911753198, "name": "The Crown™", "exe": "", "startdir": "", "last_played": 7}]
        (g,) = main.unifideck_games(shortcuts)
        self.assertEqual((g["appid"], g["name"], g["path"], g["shortcut_appid"], g["last_played"]),
                         ("unifideck:ubisoft:u1", "The Crown™", str(crown), 2911753198, 7))

    def test_broken_registry_still_lists_the_games(self):
        crown = game(HOME / "Games/Crown", "Crown.exe")
        write(main.UNIFIDECK_MAP, f"ubisoft:u1|{crown}/Crown.exe|{crown}\n")
        write(main.UNIFIDECK_REGISTRY, "{not json")
        (g,) = main.unifideck_games([])
        self.assertEqual((g["name"], g["shortcut_appid"]), ("Crown", None))


class HeroicLegendaryTest(FakeHomeTest):
    def test_gog_amazon_epic_native_and_flatpak(self):
        w3, rings, fn = (game(HOME / f"Games/{n}", "a.exe") for n in ("Witcher3", "Rings", "Fortnite"))
        write(HOME / ".config/heroic/gog_store/installed.json",
              json.dumps({"installed": [{"installPath": str(w3), "title": "The Witcher 3"}]}))
        write(HOME / ".var/app/com.heroicgameslauncher.hgl/config/heroic/nile_config/installed.json",
              json.dumps({"installed": [{"install_path": str(rings), "title": "Rings"}]}))
        write(HOME / ".config/heroic/legendaryConfig/legendary/installed.json",
              json.dumps({"fn": {"install_path": str(fn), "title": "Fortnite"}}))
        got = {(g["name"], g["store"]) for g in main.heroic_games()}
        self.assertEqual(got, {("The Witcher 3", "GOG"), ("Rings", "Amazon"), ("Fortnite", "Epic")})

    def test_missing_folders_broken_and_oversized_files_are_skipped(self):
        write(HOME / ".config/heroic/gog_store/installed.json",
              json.dumps({"installed": [{"installPath": "/nope", "title": "Gone"}, "junk"]}))
        write(HOME / ".config/heroic/nile_config/installed.json", "{broken")
        write(HOME / ".config/heroic/legendaryConfig/legendary/installed.json", " " * (main.MAX_JSON + 1))
        self.assertEqual(main.heroic_games(), [])

    def test_standalone_legendary(self):
        ctl = game(HOME / "Games/Control", "Control.exe")
        write(HOME / ".config/legendary/installed.json", json.dumps({"c": {"install_path": str(ctl), "title": "Control"}}))
        (g,) = main.legendary_games()
        self.assertEqual((g["name"], g["source"], g["store"]), ("Control", "legendary", "Epic"))

    def test_ids_are_stable_per_folder(self):
        a = main.store_game("heroic", "GOG", HOME / "Games/X", "X")
        b = main.store_game("heroic", "GOG", str(HOME / "Games/X") + "/", "Other title")
        self.assertEqual(a["appid"], b["appid"])


class LutrisTest(FakeHomeTest):
    def db(self, *rows):
        p = HOME / ".local/share/lutris/pga.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(p)
        con.execute("create table games (name, directory, configpath, installed, runner)")
        con.executemany("insert into games values (?, ?, ?, ?, ?)", rows)
        con.commit()
        con.close()

    def test_installed_wine_games_from_the_database_with_prefix_relative_exe(self):
        prefix = HOME / "Games/Lutris/Diablo"
        game(prefix / "drive_c/Diablo", "Diablo.exe")
        old = game(HOME / "Games/Lutris/Old", "old.exe")
        native = game(HOME / "Games/Lutris/Native", "native.exe")
        self.db(("Diablo", str(prefix), "diablo-1", 1, "wine"), ("Old", str(old), "old-2", 0, "wine"),
                ("Native", str(native), "native-3", 1, "linux"))
        write(HOME / ".config/lutris/games/diablo-1.yml", f"game:\n  exe: drive_c/Diablo/Diablo.exe\n  prefix: {prefix}\n")
        write(HOME / ".config/lutris/games/old-2.yml", f"game:\n  exe: {old}/old.exe\n")
        write(HOME / ".config/lutris/games/native-3.yml", f"game:\n  exe: {native}/native.exe\n")
        (g,) = main.lutris_games()
        self.assertEqual((g["name"], g["path"], g["source"]), ("Diablo", str(prefix / "drive_c/Diablo"), "lutris"))

    def test_without_a_database_the_configs_are_used(self):
        g1 = game(HOME / "Games/Lutris/Solo", "solo.exe")
        write(HOME / ".config/lutris/games/solo.yml", f"name: Solo\ngame:\n  exe: '{g1}/solo.exe'\n")
        write(HOME / ".config/lutris/games/script.yml", "game:\n  exe: /usr/bin/run.sh\n")
        (g,) = main.lutris_games()
        self.assertEqual((g["name"], g["path"]), ("Solo", str(g1)))


class ShortcutGamesTest(FakeHomeTest):
    def sc(self, **kw):
        return {"appid": 5, "name": "Game", "exe": "", "startdir": "", "launch": "", "last_played": None, **kw}

    def test_exe_start_folder_fallback_and_unresolved_launchers(self):
        hades = game(HOME / "Games/Hades", "Hades.exe")
        celeste = game(HOME / "Games/Celeste", "Celeste.exe")
        unresolved = []
        got = main.shortcut_games([
            self.sc(name="Hades", exe=f"{hades}/Hades.exe", startdir=f"{hades}/"),
            self.sc(appid=6, name="Celeste", exe="/usr/bin/env", startdir=str(celeste)),
            self.sc(appid=7, name="Mystery", exe="flatpak", startdir=str(HOME),
                    launch='run com.heroicgameslauncher.hgl --no-gui "heroic://launch/legendary/Abc"'),
        ], unresolved)
        self.assertEqual([(g["name"], g["path"]) for g in got], [("Hades", str(hades)), ("Celeste", str(celeste))])
        self.assertEqual(unresolved, ["Mystery"])

    def test_store_clients_are_never_listed_with_their_own_folder(self):
        # as found on a Deck (NonSteamLaunchers): the client itself, and a game started through it
        bnet = game(HOME / "pfx/drive_c/Program Files (x86)/Battle.net", "Battle.net.exe", "Battle.net Launcher.exe")
        nsl = 'STEAM_COMPAT_DATA_PATH="/x/compatdata/NonSteamLaunchers/" %command%'
        unresolved = []
        got = main.shortcut_games([
            self.sc(name="Battle.net", exe=f"{bnet}/Battle.net Launcher.exe", startdir=str(bnet), launch=nsl),
            self.sc(appid=6, name="Diablo", exe=f"{bnet}/Battle.net.exe", startdir=str(bnet),
                    launch=nsl + ' --exec="launch OSI"'),
            self.sc(appid=7, name="Client folder", exe="/usr/bin/env", startdir=str(bnet)),
        ], unresolved)
        self.assertEqual(got, [])
        self.assertEqual(unresolved, ["Diablo"])

    def test_apps_emulators_unifideck_and_launchers_themselves_get_no_note(self):
        unresolved = []
        main.shortcut_games([
            self.sc(name="Discord", exe="/usr/bin/flatpak", launch='"run" "com.discordapp.Discord"'),
            self.sc(name="Metroid", exe="/emu/Ryujinx.sh", launch='"/roms/switch/Metroid.xci"'),
            self.sc(name="Cloud Game", exe=f"{HOME}/homebrew/plugins/Unifideck/bin/unifideck-launcher"),
            self.sc(name="Heroic Games Launcher", exe="flatpak",
                    launch='"run" "--command=heroic-run" "com.heroicgameslauncher.hgl"'),
            self.sc(name="NonSteamLaunchers", exe="", launch='STEAM_COMPAT_DATA_PATH="/x/NonSteamLaunchers/" %command%'),
        ], unresolved)
        self.assertEqual(unresolved, [])


class AllGamesTest(FakeHomeTest):
    def test_first_source_wins_for_a_shared_folder_and_listed_names_get_no_note(self):
        w3 = game(HOME / "Games/Witcher3", "witcher3.exe")
        write(main.UNIFIDECK_MAP, f"gog:1={w3}/witcher3.exe\t{w3}\t\n")
        write(HOME / ".config/heroic/gog_store/installed.json",
              json.dumps({"installed": [{"installPath": str(w3), "title": "The Witcher 3"}]}))
        heroic = 'run com.heroicgameslauncher.hgl --no-gui "heroic://launch/gog/1"'
        shortcuts_vdf([{"appid": 1, "AppName": "Witcher3", "Exe": "flatpak", "StartDir": str(HOME), "LaunchOptions": heroic},
                       {"appid": 2, "AppName": "Unknown Launcher Game", "Exe": "flatpak", "StartDir": str(HOME),
                        "LaunchOptions": heroic}])
        enable_stores("unifideck", "heroic", "shortcuts")
        notes = []
        games = main.all_games(notes)
        self.assertEqual([(g["source"], g["path"]) for g in games.values()], [("unifideck", str(w3))])
        self.assertEqual(notes, ["Unknown Launcher Game"])

    def test_unsafe_folders_are_never_listed(self):
        game(HOME, "stray.exe")
        shortcuts_vdf([{"appid": 1, "AppName": "Home", "Exe": "/usr/bin/x", "StartDir": str(HOME)}])
        enable_stores("shortcuts")
        self.assertEqual(main.all_games(), {})


class SafetyTest(FakeHomeTest):
    def test_safe_game_folder(self):
        self.assertTrue(main.safe_game_folder(HOME / "Games/X"))
        for unsafe in ("/", "/run", str(HOME), "/run/media/deck/SD"):
            self.assertFalse(main.safe_game_folder(unsafe), unsafe)

    def test_only_listed_game_folders_may_be_changed(self):
        ctl = game(HOME / "Games/Control", "Control.exe")
        write(HOME / ".config/legendary/installed.json", json.dumps({"c": {"install_path": str(ctl), "title": "Control"}}))
        enable_stores("legendary")
        self.assertTrue(main.inside_library(ctl / "OptiScaler.ini"))
        self.assertTrue(main.inside_library(ctl / "sub/helixsr.ini"))
        self.assertFalse(main.inside_library(ctl.parent / "Other/OptiScaler.ini"))
        self.assertFalse(main.inside_library(HOME / ".bashrc"))

    def test_steam_only_lookups(self):
        self.assertEqual(main.steam_appid({"appid": "292030", "source": "steam"}), "292030")
        self.assertEqual(main.steam_appid({"appid": "292030"}), "292030")
        self.assertIsNone(main.steam_appid({"appid": "heroic:abc", "source": "heroic"}))
        self.assertEqual(main.game_last_played({"appid": "shortcut:5", "source": "shortcut", "last_played": 42}), 42)


class OptInTest(FakeHomeTest):
    """Other stores are off by default: nothing listed, nothing allowed, until their switch is on."""

    def setUp(self):
        super().setUp()
        self.ctl = game(HOME / "Games/Control", "Control.exe")
        write(HOME / ".config/legendary/installed.json",
              json.dumps({"c": {"install_path": str(self.ctl), "title": "Control"}}))

    def test_off_by_default_not_listed_and_not_allowed(self):
        self.assertEqual(main.all_games(), {})
        self.assertFalse(main.inside_library(self.ctl / "OptiScaler.ini"))

    def test_switching_a_store_on_and_off(self):
        p = main.Plugin()
        self.assertTrue(run(p.set_store("legendary", True))["ok"])
        self.assertEqual([g["name"] for g in main.all_games().values()], ["Control"])
        run(p.set_store("legendary", False))
        self.assertEqual(main.all_games(), {})

    def test_only_the_switched_on_store_is_read(self):
        w3 = game(HOME / "Games/Witcher3", "witcher3.exe")
        write(HOME / ".config/heroic/gog_store/installed.json",
              json.dumps({"installed": [{"installPath": str(w3), "title": "The Witcher 3"}]}))
        enable_stores("heroic")
        self.assertEqual([g["name"] for g in main.all_games().values()], ["The Witcher 3"])

    def test_store_list_reports_found_and_counts(self):
        stores = {s["id"]: s for s in run(main.Plugin().get_stores())}
        self.assertEqual(list(stores), ["unifideck", "heroic", "legendary", "lutris", "shortcuts"])
        self.assertEqual((stores["legendary"]["found"], stores["legendary"]["count"], stores["legendary"]["enabled"]),
                         (True, 1, False))
        self.assertEqual((stores["heroic"]["found"], stores["heroic"]["count"]), (False, 0))

    def test_unknown_store_is_refused(self):
        self.assertFalse(run(main.Plugin().set_store("origin", True))["ok"])

    def test_added_folders_need_no_switch(self):
        cel = game(HOME / "Games/Celeste", "Celeste.exe")
        r = run(main.Plugin().add_custom_game(str(cel)))
        self.assertIn(r["appid"], main.all_games())


class CustomGamesTest(FakeHomeTest):
    def test_add_list_and_remove_a_folder(self):
        cel = game(HOME / "Games/Celeste", "Celeste.exe")
        r = run(main.Plugin().add_custom_game(str(cel)))
        self.assertTrue(r["ok"], r)
        self.assertIn(r["appid"], main.all_games())
        self.assertTrue(main.inside_library(cel / "OptiScaler.ini"))
        run(main.Plugin().add_custom_game(str(cel)))   # twice: listed once
        self.assertEqual(main.load_settings()["custom_games"], [os.path.realpath(cel)])
        run(main.Plugin().remove_custom_game(r["appid"]))
        self.assertNotIn(r["appid"], main.all_games())
        self.assertTrue((cel / "Celeste.exe").exists())   # files stay

    def test_exe_one_level_down_is_enough(self):
        g = game(HOME / "Games/Deep/bin", "deep.exe").parent
        self.assertTrue(run(main.Plugin().add_custom_game(str(g)))["ok"])

    def test_refused_folders(self):
        game(HOME / "Games/Empty")
        for path, why in ((str(HOME), "not a whole drive"), ("/", "not a whole drive"),
                          (str(HOME / "Games/Empty"), "No Windows game"), (str(HOME / "Nope"), "doesn't exist")):
            r = run(main.Plugin().add_custom_game(path))
            self.assertFalse(r["ok"], path)
            self.assertIn(why, r["error"])


if __name__ == "__main__":
    unittest.main()
