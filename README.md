# HelixSR Manager (Decky plugin)

A Decky Loader plugin for the Steam Deck that installs [HelixSR](https://github.com/lonewolf0622/HelixSR) into your
games, per game, and checks that it actually runs. HelixSR runs NVIDIA's DLSS upscaling network on AMD GPUs like the
Deck's. From 3.0, HelixSR's releases put **HLX FSR 4** (AMD's FSR 4 network on HelixSR's pipeline) into games instead;
the plugin installs that and offers HelixSR 2.0.0's DLSS network next to it. This plugin contains no HelixSR, NVIDIA or
AMD files: it downloads the official HelixSR release from GitHub and runs HelixSR's own setup, which builds everything
locally on your Deck.

HelixSR is developed by [lonewolf0622](https://github.com/lonewolf0622/HelixSR). This plugin is an independent
integration, not affiliated with HelixSR, NVIDIA, AMD, OptiScaler or Decky.

[Download the latest release](https://github.com/PeroTuncay/DeckyHelixSRManager/releases/latest) ·
[Installation](#installation) · [Check that it runs](#4-check-that-it-runs) ·
[Report a problem](https://github.com/PeroTuncay/DeckyHelixSRManager/issues/new)

Tested on a Steam Deck OLED (SteamOS) and an ASUS ROG Ally Z1 Extreme (Bazzite) with The Witcher 3 (DirectX 12) through
OptiScaler.

## Features

- **Any HelixSR release:** pick a release from GitHub, download it (verified against GitHub's SHA256 checksum, with a
  notice if the author later replaces the zip) and build it with a progress bar. Several releases can sit side by side.
- **Per game, two routes:** in place of a game's own FSR 3.1, or through the OptiScaler the game already has (for
  example from Decky Framegen), keeping your current FSR 4 selectable for comparison. With HelixSR 3.x, the OptiScaler
  section offers HLX FSR 4 and HelixSR 2.0.0's DLSS network; one button swaps one for the other.
- **Games from other stores (opt-in):** Unifideck, Heroic (GOG, Amazon, Epic), Legendary, Lutris and games added to
  Steam by hand, each switched on in **Other Stores**, plus **Add game folder** for anything else. Only the folders the
  stores name are read, so the game list stays fast.
- **Safe changes:** refuses while the game is running or Steam is still updating it, warns about anti-cheat (online
  bans) and asks you to confirm, keeps the game's original files, and puts everything back on removal. Disable keeps
  HelixSR's files for a quick switch back.
- **Plain status per game:** one line saying whether HelixSR is installed and actually upscaled in the current or last
  game session ("✓ Working: 853x533 → 1280x800"), or what to select in the game if not. Numbered steps (download,
  build, install) show what's next, with a progress bar for the download and the build.
- **Did it apply?** Reads HelixSR's log (network running, render and output size, whether the log is from the last
  game session), shows OptiScaler settings that commonly get in the way (DLSS input off, Steam Input blocked, menu key),
  and has a network on/off switch to prove HelixSR is doing the upscaling.
- **Settings per game** where the release supports them (sharpening from 1.8, network resolution up to 1.4).
- **Less scrolling:** HelixSR Installation, Other Stores, OptiScaler and "In place of the game's FSR 3.1" fold away (tap the
  header); a closed section shows a one-line summary, including warnings inside. Installation starts open.
- **Plugin updates from the panel:** a newer release shows up at the top with an **Update** button; Decky installs it
  after you confirm.
- **Technical details on demand:** logs, paths and OptiScaler settings stay behind **Show technical details**; rarely
  needed buttons (download again, delete, clean up, diagnostics, debug report) behind **More options**.
- **Clean up (optional):** remove every downloaded release and the setup's downloads in one go. Not needed for updates.

> **HelixSR has changed its approach a few times.** Up to 1.4 and again **from 1.7** (tested up to 2.0.0), it replaces
> FSR 3.1 (`amd_fidelityfx_dx12.dll`): through OptiScaler for DLSS games (select DLSS in the game), or in place of a
> game's own FSR 3.1. 1.5 and 1.6 instead replaced DLSS (`nvngx.dll`) through OptiScaler and needed a Steam launch
> option; those releases were withdrawn upstream, but the plugin still supports a 1.5 you already downloaded.
>
> From 1.7, HelixSR's own setup also installs its own OptiScaler into your games when run in a terminal. Up to 1.8.1
> the plugin runs only the build part of that setup, so HelixSR's own game installer never starts. From 1.9 (HelixSR's
> setup may no longer be modified) the setup runs as published: after the build its game installer starts, gets no
> answer and ends without changing any game. The plugin never passes `--yes` to these setups (from 2.0 it would also
> answer the game installer and install into every game): it downloads NVIDIA's DLSS DLL itself from NVIDIA's GitHub,
> checked against the checksum HelixSR's setup names, and hands it over with `--dlss`, so the setup has nothing to ask.
> Either way the plugin then installs per game itself, into the OptiScaler the game already has. From 2.0 HelixSR's DLL
> sits in the release's `HelixSR-fsrfg` folder. 1.9.0's setup can also build frame generation for HelixSR Scaler (about 400 MB of NVIDIA
> downloads); the plugin skips that (`--no-fg`), since it doesn't install HelixSR Scaler. Games set up with HelixSR
> Desktop's HelixSR Scaler (OptiScaler with HelixSR built in) are shown with the check, but left to HelixSR Desktop. Games already set up by HelixSR's own setup are shown, but left to
> that setup, including 1.8.1's experimental "DLSS without OptiScaler" route (HelixSR's loader as `dxgi.dll` and
> HelixSR as `nvngx.dll` next to the game's exe), which the plugin doesn't offer itself. A setup whose layout the plugin
> doesn't recognize isn't run.
>
> **From 3.0** (tested with 3.1.0; 3.2.0 checked), the DLL a release puts into games is **HLX FSR 4**: AMD's FSR 4 network on
> HelixSR's pipeline, as `HLX-FSR4/amd_fidelityfx_upscaler_dx12.dll`. Its setup builds HLX FSR 4's shaders from AMD's
> FSR 4 driver file, but downloads that file only after a yes on a terminal. So the plugin runs the setup as before
> (still never with `--yes`), then a second step: the release's `helixsr_setup.py --fg-only --no-fg --yes`, which only
> downloads and builds and never starts the game installer. **From 3.2.0** the zip ships HLX FSR 4 built, so the
> release is ready right after the download and the second step has nothing to do. HelixSR 3.x's own DLSS network (HLX DLSS,
> `HelixSR/helixsr.dll`) is made for HelixSR Scaler. In a game's own OptiScaler (0.10) it doesn't run: OptiScaler
> decides once, early, that the Deck's GPU can't do DLSS and quietly uses its FSR 2.1.2 instead. So the plugin doesn't
> offer HLX DLSS; it offers HelixSR 2.0.0's network next to HLX FSR 4 instead.

## Installation

### 1. Install the plugin

1. In Decky Loader, open **Settings → General** and turn on **Developer mode**.
2. Open **Settings → Developer → Install plugin from URL** and paste the link to `HelixSR-Manager.zip` from the
   [latest release](https://github.com/PeroTuncay/DeckyHelixSRManager/releases/latest) (on the release page: right-click
   or long-press the zip → copy link).
   Alternatively, download the zip, copy it to the Deck and use **Install plugin from ZIP file**.
3. Open the Quick Access menu (`···` button) → Decky → **HelixSR Manager**.

**Updating the plugin:** from 0.9.2 on, the plugin checks GitHub for a newer release when you open it (at most every
few hours). When there is one, a **Plugin update** section appears at the top: press **Update to …**, confirm Decky's
prompt, and Decky downloads the release, checks its SHA256 and reloads the plugin. **About this plugin** at the bottom
shows the installed version and has **Check for plugin updates**. Versions before 0.9.2 update once by hand: install the
newer zip over the old one, as above.

### 2. Download and build HelixSR (once per release)

The **HelixSR Installation** section shows three numbered steps and only the button for the next one.

1. Pick a version under **Version** (the newest is marked *latest*).
2. Press **Download HelixSR …**. A progress bar shows the download; the zip is checked against GitHub's SHA256 checksum
   before it's used.
3. Press **Build HelixSR …** and confirm. HelixSR's setup downloads NVIDIA's DLSS 310.7.0 DLL, a portable
   Python with numpy and Microsoft's shader compiler, builds HelixSR's network (into HelixSR's DLL from 1.8, as two
   separate files before) and deletes NVIDIA's DLL again. From 1.7 on, only the build part of HelixSR's setup runs:
   its own game installer never starts, and the plugin installs per game in the next step. From 3.0, a second step
   then builds HLX FSR 4: it downloads about 420 MB of AMD's driver package from AMD, reads only its FSR 4 file and
   installs nothing. This adds several minutes. From 3.2.0, HLX FSR 4 comes built: the release shows **✓ ready**
   after the download and needs no build (a rebuild makes it from AMD's FSR SDK file in the zip, no AMD download).
4. Wait for it to finish: **about 7-10 minutes on a Steam Deck OLED** (the first run includes the one-time downloads;
   later releases reuse Python and the compiler). Keep the Deck plugged in and don't let it sleep, since sleep pauses
   the setup. You can close the menu meanwhile; the progress bar picks up where it is when you reopen it.
5. Steps 1 and 2 show a ✓ and the version shows **✓ ready**.

**Updating later:** pick the newer version, download and build it, then press **Switch to HelixSR …** in each game. It
replaces the old version in that game; no cleanup is needed first.

**HelixSR 3.x and 2.0.0 side by side:** to have HelixSR's DLSS network next to HLX FSR 4, also download and build
2.0.0 (pick it under **Version**), then pick the 3.x release again. Games then get either one from the same section.

### 3. Install HelixSR into a game

Pick the game under **Game Configuration** (the list shows games HelixSR can use: with an FSR 3.1 DLL or OptiScaler,
and DLSS / XeSS / FSR 2 games, tagged "needs OptiScaler"; turn off the filter to see all). A DLSS or XeSS game without
OptiScaler says what to do: install OptiScaler into it first (for example with the Decky Framegen plugin), then the
OptiScaler section appears with the install button.
Games from other stores appear there once their store is switched on in **Other Stores** (see
[Games from other stores](#games-from-other-stores)).
Close the game first: the plugin refuses to change its files while it runs or while Steam is still installing or
updating it. If the game ships anti-cheat (EasyAntiCheat, BattlEye, …), the plugin warns that online play could get
your account banned and only installs after you turn on **I understand the risk** for that game.

- **Game with OptiScaler (HelixSR 1.4 or 1.7 to 2.0):** in the **OptiScaler** section press **Install HelixSR …
  via OptiScaler**. Leave **Keep current FSR selectable** on to keep your FSR 4 available for comparison. In the game,
  select DLSS: it gives HelixSR the best input. XeSS or FSR also work in games without DLSS, but can shimmer more. Then
  open OptiScaler's menu and pick **FSR HelixSR (3.1.5)** under Upscalers → FFX Upscaler. OptiScaler's menu opens with
  Insert by default, which the Deck doesn't have: map it to a back button in the game's controller layout (the plugin
  shows the key the game's `OptiScaler.ini` uses).
  `Dx12Upscaler` is set to what the game's OptiScaler expects (`fsr31` on OptiScaler 0.9.4).
- **Game with OptiScaler (HelixSR 3.x):** the **OptiScaler** section has two buttons:
  - **Install HLX FSR 4 … via OptiScaler**. OptiScaler's menu then lists "HLX FSR 4" first under Upscalers → FFX
    Upscaler, with AMD's own FSR after it, for comparing. HLX FSR 4 hands AMD's FSR anything it doesn't cover itself.
  - **Install HelixSR 2.0.0 (DLSS network) via OptiScaler**, once 2.0.0 is downloaded and built (otherwise the section
    says how to get it).

  Either one replaces the other with **Use … instead**. In the game, select DLSS (XeSS or FSR also work).
- **Game that ships FSR 3.1 itself (HelixSR 1.4, 1.7 or later):** in **In place of the game's FSR 3.1** press **Install
  HelixSR … here**, then select AMD FSR as the upscaler in the game's settings. This needs no OptiScaler. A game that
  offers both sections works either way (HelixSR 1.8's own setup prefers this one). With 3.x this installs HLX FSR 4;
  the game's own FSR stays next to it, and HLX FSR 4 hands it anything it doesn't cover.
- **HelixSR 1.5.x (withdrawn upstream; only if you still have it):** in the **OptiScaler** section press **Install HelixSR
  … via OptiScaler (as DLSS)**, then **Add launch option**: it adds
  `PROTON_FORCE_NVAPI=1 DXVK_NVAPI_GPU_ARCH=AD100 DXVK_NVAPI_ALLOW_OTHER_DRIVERS=1` in front of the game's existing
  launch options (e.g. Decky Framegen's stay as they are). In the game, select **DLSS**. The last variable lets NVIDIA's
  API layer start on the Deck's AMD GPU; without it, OptiScaler 0.10 decides the GPU can't do DLSS and quietly uses
  FSR 2.1.2 instead (an option added by an older version of the plugin is offered again).

Switching a game between releases is one button; the plugin undoes the other setup first. Under the OptiScaler section
the plugin also points out settings that commonly get in the way (DLSS input off, GPU spoofing off, an overlay setting
that blocks Steam Input).

### 4. Check that it runs

After playing for a moment, press **Check again** in the plugin. The status line under the game's name says it in
plain words:

- **✓ Working**: HelixSR upscaled in the current or last game session, e.g. "853x533 → 1280x800 (Quality)".
- **Installed, not used yet** / **waiting for the game** / **not used last time**: HelixSR didn't upscale; the line says
  what to select in the game (DLSS through OptiScaler, AMD FSR for a game's own FSR 3.1).
- **Installed, but HelixSR can't upscale** (red, also a red frame in the game): that copy has no built network.
- With HLX FSR 4: **Installed, AMD's FSR stepped in** (HLX FSR 4 handed some upscaling to AMD's own FSR) or
  **Installed, but HLX FSR 4 can't upscale** (AMD's own FSR runs instead, for example because the shaders aren't
  built). HLX FSR 4 shows no red frame. It logs to `HLX_FSR.log` next to it, or to `OptiScaler.log` when it runs
  inside OptiScaler; the plugin reads either.

**Show technical details** adds what HelixSR logged, the log's time and session, and OptiScaler's log lines.

**To prove HelixSR (and not FSR) is doing the upscaling**, turn on **Show technical details**, then turn off **DLSS
network (Model E)** for that game and
restart it. HelixSR then falls back to a simple, blurry placeholder upscale: if the picture changes, HelixSR is the
active upscaler; if it looks the same, a different upscaler is selected. Turn the network back on afterwards. The switch
only takes effect when the game starts (from 1.5 on it's undocumented upstream, so treat it as experimental). For a
live side-by-side comparison, switch between "FSR HelixSR (3.1.5)" and FSR 3.1.5 / FSR 4 in OptiScaler's menu
(Upscalers → FFX Upscaler); an entry named just "FSR 3.1.5" is AMD's FSR 3.1, not HelixSR. HLX FSR 4 has no network
switch: compare it with AMD's FSR in that same list.

### 5. Settings, disable and undo

- **Sharpening:** **Sharpening** (NVIDIA's Image Sharpening or AMD's RCAS) and **Sharpness**. Off by default, as DLSS
  (1.9.0's pre-release sharpened lightly by default; the plugin reads which one a game has). Sharpness defaults to 0.1
  in 1.9.x and 0.5 from 2.0.
- **Int8 network (Speed Boost):** Auto, On or Off where the release reads it (1.9.0's pre-release, 1.9.3 and newer);
  the 1.9.0 release picks it automatically. Up to 1.4: the release's sharpening mode and network resolution.
  Changes take effect after restarting the game. HLX FSR 4 has no settings.
- **Disable** switches the game back to its own FSR (or OptiScaler's previous upscaler) and keeps HelixSR's files;
  **Enable HelixSR again** switches back without downloading or building anything.
- **Undo completely:** **Revert OptiScaler to previous upscaler** or **Restore the game's FSR** (plus **Remove HelixSR
  launch option** for 1.5.x). The game's original files and settings come back as they were.

## Games from other stores

Steam games are always listed. Games from other stores are **opt-in**: open **Other Stores** (between HelixSR
Installation and Game Configuration) and switch on the stores you use. Each toggle shows how many games it found, or
"Not found on this device". A store that is off isn't read at all.

| Store | Where the plugin finds the games |
|---|---|
| **Unifideck** (GOG, Epic, Amazon, Ubisoft, …) | Unifideck's list of installed games (`~/.local/share/unifideck/games.map`), named after their Steam shortcuts |
| **Heroic Games Launcher** (GOG, Amazon, Epic; native and Flatpak) | Heroic's `installed.json` files |
| **Legendary** (Epic) | Legendary's `installed.json` |
| **Lutris** | Lutris' game configs and its database (read-only; installed Windows games only). Not tested on a real device yet. |
| **Non-Steam games in Steam** | Steam's shortcuts that start a game's `.exe` directly (Steam → "Add a non-Steam game") |

In the game list, each of these games carries its source ("· Heroic (GOG)", "· Unifideck", …). Shortcuts that start a
game through a launcher can't name the game's folder; the section lists them and suggests **Add game folder**, which
adds any game by picking its install folder (and **Remove from the list** takes it out again; the game's files stay).

The plugin only reads the folders the stores name; it never crawls whole drives. It only ever changes files inside a
listed game's own folder: never `/`, your home folder, a whole drive or SD card, and nothing of a store that is off.
The running-game check works for these games too (by the game's `.exe` inside its folder); "Steam is updating it" only
applies to Steam games.

## What it does

1. **HelixSR release**: a dropdown of every release on
   [HelixSR's release page](https://github.com/lonewolf0622/HelixSR/releases), read live from GitHub's API (the last
   list is cached for offline use), so new releases show up without a plugin update. The selected release is the one
   the install buttons use. Each release is downloaded to its own folder (`~/HelixSR/v1.4.1`, …; the base folder can
   be changed) and needs its one-time setup (`helixsr-setup.sh --yes`, about 7-10 minutes on a Steam Deck OLED; downloads NVIDIA's DLSS
   310.7.0 DLL after you confirm, builds the network, deletes NVIDIA's DLL). Several releases can sit side by side;
   switching a game to another one is one button. Releases before 1.4.0 keep the network in
   `helixsr_weights.bin`/`helixsr_kernels.pak`, which are copied along with the DLL. From 3.0, a second step builds
   HLX FSR 4's shaders into its DLL (`helixsr_setup.py --fg-only --no-fg --yes`, after the setup's own run).
2. **Game list**: every installed Steam game from all libraries (SD card too), optionally filtered to games that ship
   an FSR 3.1 DLL or have OptiScaler.
3. **Replace FSR 3.1 directly**: renames the game's `amd_fidelityfx_upscaler_dx12.dll` (or `amd_fidelityfx_dx12.dll`)
   to `*.original.dll` and puts HelixSR in its place, plus `helixsr.ini`. Same files and `helixsr-install.json` marker
   as the official `helixsr-install.sh`, so either tool can undo the other's install. HLX FSR 4 (3.x) goes in the same
   way, without `helixsr.ini`, and lists the game's kept FSR after itself.
4. **OptiScaler**: creates a `HelixSR` folder next to `OptiScaler.ini` with HelixSR as both
   `amd_fidelityfx_dx12.dll` and `amd_fidelityfx_upscaler_dx12.dll`, and sets in `OptiScaler.ini`:
   `Dx12Upscaler` (`ffx` on OptiScaler 0.9+, `fsr31` on older versions), `FfxDx12Path`, `FfxDx12SRPath` (as `Z:\…`
   paths) and `[FSR] UpscalerIndex=0`. The old values are remembered and restored on revert; a full copy is kept as
   `OptiScaler.ini.helixsr-backup`. A frame generation DLL (the game's current one, else AMD's from the release) is put
next to HelixSR, since HelixSR has none of its own; OptiScaler's own frame generation setting is left alone. With
**Keep current FSR selectable**, the FSR 4 DLL OptiScaler used so far is copied
   in as `amd_fidelityfx_upscaler_dx12.amd.dll` and set as HelixSR's `[Forwarding] UpscalerDll`, so FSR 4 stays in
   OptiScaler's FFX Upscaler list for comparison. The previous `amd_fidelityfx_dx12.dll` is copied in as
   `amd_fidelityfx_dx12.original.dll` so frame generation keeps working. HLX FSR 4 (3.x) is only an upscaler: it
   goes in as `amd_fidelityfx_upscaler_dx12.dll` (`FfxDx12SRPath`), `FfxDx12Path` stays the game's, and AMD's FSR is
   always copied in as `amd_fidelityfx_upscaler_dx12.amd.dll`, which HLX FSR 4 lists after itself. HelixSR 2.0.0 next
   to a 3.x release is installed exactly like 2.0.0 on its own.
5. **Setup progress**: while the setup runs, a progress bar with the current step (in step 5 the compiled shaders,
   e.g. 41/72), the elapsed time, whether it is actually working (CPU use of its processes) and what runs right now.
   HelixSR's steps print nothing while they work, so the log alone can stay unchanged for minutes. The setup keeps
   running when the menu is closed or Decky restarts the plugin, and its exit code is recorded either way. If it
   fails: the error lines, **Show full log**, **Run diagnostics** (Proton, Python/numpy, free space, GitHub, …) and
   **Save debug report** (`~/HelixSR/helixsr-manager-debug.txt`).
6. **Clean up downloads** (under More options, optional): removes every downloaded release, the setup's Python, shader compiler and Wine data
   (`~/.local/share/HelixSR`) and temporary files. Games keep their installed copy. Only files recognizably
   HelixSR's are removed from the HelixSR folder.
7. **Check**: reads `helixsr.log` (network running / not running / loaded but idle, wave size, network resolution) and,
   if enabled, OptiScaler.log lines about HelixSR/FFX. For HLX FSR 4 it reads `HLX_FSR.log`, or its lines in
   `OptiScaler.log`. Whether a log is from the last game session is judged by the session's start in Steam's
   `logs/gameprocess_log.txt` (Steam's `LastPlayed` is written again when the game quits).
8. **Settings**: the DLSS network on/off test switch, `NetworkResolution` and sharpening per install. The
   `NetworkResolution` choices come from the installed release's own `helixsr.ini`, since they differ between
   releases (1.4.3 is HelixSR 1.3.0 again: auto/fast/full; 1.4.0-1.4.2: auto/full/QSSM/PRSM). 1.5+ has no settings
   file; only the experimental network switch is offered there.
9. **Safety checks**: no change to a game's files while it runs (detected through Steam's process environment or a
   Windows program inside the game folder; for games from other stores by the folder alone) or while Steam is still installing/updating it (`StateFlags`, download
   folder). Games with anti-cheat files (EasyAntiCheat, BattlEye, …) need an explicit "I understand the risk" before
   installing; removing is always allowed.
10. **Disable / Enable**: a direct install parks HelixSR's DLL as `*.helixsr-disabled.dll` and puts the game's file
    back; an OptiScaler install restores the previous `OptiScaler.ini` values and keeps the `HelixSR` folder. Enable
    switches back without downloading or building anything.
11. **Other stores** (opt-in): reads the install lists of Unifideck, Heroic, Legendary and Lutris and Steam's
    `shortcuts.vdf` (each file size-capped, the Lutris database read-only), plus folders added by hand. Each listed
    game's folder becomes the only place the plugin may change files for that game.

## Build

```
npm install
npm run package     # -> out/HelixSR-Manager.zip
npm test            # unit tests (Python's unittest, no extra packages)
```

## Notes

- Runs as the `deck` user (no root).
- Setup time: about 7-10 minutes on a Steam Deck OLED (HelixSR quotes 4-5 minutes for a desktop CPU). Don't let the
  Deck sleep during the setup (sleep pauses it).
- If the setup fails in Gaming Mode, run it once from Konsole in Desktop Mode, e.g.
  `~/HelixSR/v1.4.1/helixsr-setup.sh`; the plugin picks up the built DLL afterwards.
- Direct3D 12 only. Vulkan games aren't supported by HelixSR.
- **Frame generation:** HelixSR 2.0's own frame generation (it runs NVIDIA's DLSS frame generation in games that have
  DLSS Frame Generation) needs HelixSR Scaler, which HelixSR Desktop or HelixSR's setup installs; the plugin doesn't,
  and skips building it (`--no-fg`, saving about 400 MB of NVIDIA downloads). OptiScaler's own frame generation (AMD
  FSR or XeSS frame generation, e.g. from Decky Framegen) keeps working next to the plugin's HelixSR install: the
  plugin keeps the FSR frame generation DLL available next to HelixSR.
- Close the game before installing or reverting.
- Where other stores keep their install lists (and their formats) was learned from
  [HelixSR-Decky](https://github.com/dawoodtogoo2020-code/HelixSR-Decky) (MIT) and from
  [Unifideck](https://github.com/mubaraknumann/unifideck)'s source; the code here is our own.

## Known game issues

These are fixes outside the plugin: it doesn't change game files beyond installing HelixSR. Apply them at your own
risk and only for offline play.

### DirectX 11 games (e.g. Nioh 2)

HelixSR only works in DirectX 12 games. The plugin reads the game's .exe (its imports, including delay-loaded ones),
and when it looks DirectX 11 only it shows "Not supported" instead of an install button. If a game has a DirectX 12
mode, switch to it (often a launch option or a setting) and press **Check again**. The check can be wrong; if you're
sure the game runs on DirectX 12, use **Install anyway**.

### The Witcher 3: "DLSS not supported" under Proton

The game (5.0, DirectX 12) refuses DLSS when it detects Wine: it looks for `wine_get_version` and then never starts
NVIDIA Streamline. OptiScaler's GPU spoofing doesn't help. Without DLSS, select XeSS or FSR in the game; HelixSR works
through those too, but they can shimmer more.

The fix renames that text in `witcher3.exe` ([source](https://gist.github.com/gabrielmaialva33/33ebb2542f0513d55100b22aa2149ff5)).
With the game closed, in Desktop Mode (Konsole):

```sh
cd "$HOME/.local/share/Steam/steamapps/common/The Witcher 3/bin/x64_dx12"   # or the game's folder on another drive
grep -a -c wine_get_version witcher3.exe                       # 2 = needs the fix, 0 = already patched
cp -p witcher3.exe witcher3.exe.orig                           # backup
sed -i 's/wine_get_version/frog_get_version/' witcher3.exe
cmp -l witcher3.exe.orig witcher3.exe | wc -l                  # must print 8; otherwise restore the backup
```

Then select DLSS in the game and HelixSR 3.1.5 (or HLX FSR 4 with HelixSR 3.x) in OptiScaler's menu (FSR 3.X/4).
A game update or Steam's "Verify integrity of game files" restores the original exe, so repeat it after either. To
undo: `mv witcher3.exe.orig witcher3.exe`.

With Wine hidden, the game also changes how it uses DirectX 12, so it depends on the device and Proton version:

| Device | Works with |
|---|---|
| Steam Deck OLED (SteamOS) | Proton 11.0-2e |
| ROG Ally Z1 Extreme (Bazzite, Mesa 25.2) | Proton Experimental 11.0-20261001 plus `VKD3D_CONFIG=nodxr` in the launch options (turns off the game's ray tracing). On 11.0-2e it crashes at startup. |

If the game doesn't start after the fix, restore the original exe and try another Proton version. proton-cachyos
"Wineland" 11.0-20260930 or newer hides Wine for this game by itself, without changing the exe.

## License

Public domain ([The Unlicense](LICENSE)): copy, change and use it however you like. The install logic follows
HelixSR's Apache-2.0 installer script (up to 1.8.1). HelixSR itself isn't included: the plugin downloads official
releases unmodified, and from 1.9 (HelixSR Freeware License) runs HelixSR's setup exactly as published. See
[LICENSE](LICENSE) for the notes on HelixSR and NVIDIA's files.
