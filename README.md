# HelixSR Manager (Decky plugin)

A Decky Loader plugin for the Steam Deck that installs [HelixSR](https://github.com/lonewolf0622/HelixSR) into your
games, per game, and checks that it actually runs. HelixSR runs NVIDIA's DLSS upscaling network on AMD GPUs like the
Deck's. This plugin contains no HelixSR files and no NVIDIA files: it downloads the official HelixSR release from
GitHub and runs HelixSR's own setup, which builds the network locally on your Deck.

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
  example from Decky Framegen), keeping your current FSR 4 selectable for comparison.
- **Safe changes:** refuses while the game is running or Steam is still updating it, warns about anti-cheat (online
  bans) and asks you to confirm, keeps the game's original files, and puts everything back on removal. Disable keeps
  HelixSR's files for a quick switch back.
- **Plain status per game:** one line saying whether HelixSR is installed and actually upscaled in the current or last
  game session ("✓ Working: 853x533 → 1280x800"), or what to select in the game if not. Numbered steps (download,
  build, install) show what's next, with a progress bar for the download and the build.
- **Did it apply?** Reads HelixSR's log (network running, render and output size, whether the log is from the last
  game session), shows OptiScaler settings that commonly get in the way (DLSS input off, Steam Input blocked, menu key),
  and has a network on/off switch to prove HelixSR is doing the upscaling.
- **Settings per game** where the release supports them (sharpening in 1.8, network resolution up to 1.4).
- **Less scrolling:** HelixSR Installation, OptiScaler and "In place of the game's FSR 3.1" fold away (tap the
  header); a closed section shows a one-line summary, including warnings inside. Installation starts open.
- **Technical details on demand:** logs, paths and OptiScaler settings stay behind **Show technical details**; rarely
  needed buttons (download again, delete, clean up, diagnostics, debug report) behind **More options**.
- **Clean up (optional):** remove every downloaded release and the setup's downloads in one go. Not needed for updates.

> **HelixSR has changed its approach a few times.** Up to 1.4 and again **from 1.7** (tested up to 1.8.1), it replaces
> FSR 3.1 (`amd_fidelityfx_dx12.dll`): through OptiScaler for DLSS games (select DLSS in the game), or in place of a
> game's own FSR 3.1. 1.5 and 1.6 instead replaced DLSS (`nvngx.dll`) through OptiScaler and needed a Steam launch
> option; those releases were withdrawn upstream, but the plugin still supports a 1.5 you already downloaded.
>
> From 1.7, HelixSR's own setup also installs its own OptiScaler into your games when run in a terminal. The plugin
> runs only the build part of that setup, so HelixSR's own game installer never starts; it then installs per game
> itself, into the OptiScaler the game already has. Games already set up by HelixSR's own setup are shown, but left to
> that setup, including 1.8.1's experimental "DLSS without OptiScaler" route (HelixSR's loader as `dxgi.dll` and
> HelixSR as `nvngx.dll` next to the game's exe), which the plugin doesn't offer itself. A setup whose layout the plugin
> doesn't recognize isn't run.

## Installation

### 1. Install the plugin

1. In Decky Loader, open **Settings → General** and turn on **Developer mode**.
2. Open **Settings → Developer → Install plugin from URL** and paste the link to `HelixSR-Manager.zip` from the
   [latest release](https://github.com/PeroTuncay/DeckyHelixSRManager/releases/latest) (on the release page: right-click
   or long-press the zip → copy link).
   Alternatively, download the zip, copy it to the Deck and use **Install plugin from ZIP file**.
3. Open the Quick Access menu (`···` button) → Decky → **HelixSR Manager**.

Updating works the same way: install the newer zip over the old one.

### 2. Download and build HelixSR (once per release)

The **HelixSR Installation** section shows three numbered steps and only the button for the next one.

1. Pick a version under **Version** (the newest is marked *latest*).
2. Press **Download HelixSR …**. A progress bar shows the download; the zip is checked against GitHub's SHA256 checksum
   before it's used.
3. Press **Build HelixSR …** and confirm. HelixSR's setup downloads NVIDIA's DLSS 310.7.0 DLL, a portable
   Python with numpy and Microsoft's shader compiler, builds HelixSR's network (into HelixSR's DLL from 1.8, as two
   separate files before) and deletes NVIDIA's DLL again. From 1.7 on, only the build part of HelixSR's setup runs:
   its own game installer never starts, and the plugin installs per game in the next step.
4. Wait for it to finish: **about 7-10 minutes on a Steam Deck OLED** (the first run includes the one-time downloads;
   later releases reuse Python and the compiler). Keep the Deck plugged in and don't let it sleep, since sleep pauses
   the setup. You can close the menu meanwhile; the progress bar picks up where it is when you reopen it.
5. Steps 1 and 2 show a ✓ and the version shows **✓ ready**.

**Updating later:** pick the newer version, download and build it, then press **Switch to HelixSR …** in each game. It
replaces the old version in that game; no cleanup is needed first.

### 3. Install HelixSR into a game

Pick the game under **Game Configuration** (the list shows games with an FSR 3.1 DLL or OptiScaler; turn off the filter to see all).
Close the game first: the plugin refuses to change its files while it runs or while Steam is still installing or
updating it. If the game ships anti-cheat (EasyAntiCheat, BattlEye, …), the plugin warns that online play could get
your account banned and only installs after you turn on **I understand the risk** for that game.

- **Game with OptiScaler (HelixSR 1.7, 1.8 or 1.4):** in the **OptiScaler** section press **Install HelixSR …
  via OptiScaler**. Leave **Keep current FSR selectable** on to keep your FSR 4 available for comparison. In the game,
  select DLSS: it gives HelixSR the best input. XeSS or FSR also work in games without DLSS, but can shimmer more. Then
  open OptiScaler's menu and pick **FSR HelixSR (3.1.5)** under Upscalers → FFX Upscaler. OptiScaler's menu opens with
  Insert by default, which the Deck doesn't have: map it to a back button in the game's controller layout (the plugin
  shows the key the game's `OptiScaler.ini` uses).
  `Dx12Upscaler` is set to what the game's OptiScaler expects (`fsr31` on OptiScaler 0.9.4).
- **Game that ships FSR 3.1 itself (HelixSR 1.4, 1.7 or 1.8):** in **In place of the game's FSR 3.1** press **Install
  HelixSR … here**, then select AMD FSR as the upscaler in the game's settings. This needs no OptiScaler. A game that
  offers both sections works either way (HelixSR 1.8's own setup prefers this one).
- **HelixSR 1.5.x (withdrawn upstream; only if you still have it):** in the **OptiScaler** section press **Install HelixSR
  … via OptiScaler (as DLSS)**, then **Add launch option**: it adds `PROTON_FORCE_NVAPI=1 DXVK_NVAPI_GPU_ARCH=AD100` in
  front of the game's existing launch options (e.g. Decky Framegen's stay as they are). In the game, select **DLSS**.

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

**Show technical details** adds what HelixSR logged, the log's time and session, and OptiScaler's log lines.

**To prove HelixSR (and not FSR) is doing the upscaling**, turn on **Show technical details**, then turn off **DLSS
network (Model E)** for that game and
restart it. HelixSR then falls back to a simple, blurry placeholder upscale: if the picture changes, HelixSR is the
active upscaler; if it looks the same, a different upscaler is selected. Turn the network back on afterwards. The switch
only takes effect when the game starts (from 1.5 on it's undocumented upstream, so treat it as experimental). For a
live side-by-side comparison, switch between "FSR HelixSR (3.1.5)" and FSR 3.1.5 / FSR 4 in OptiScaler's menu
(Upscalers → FFX Upscaler); an entry named just "FSR 3.1.5" is AMD's FSR 3.1, not HelixSR.

### 5. Settings, disable and undo

- **Sharpening:** from 1.8, optional and off by default, as DLSS: **Sharpening** (NVIDIA's Image Sharpening or AMD's
  RCAS) and **Sharpness** (0.5 = NVIDIA's default). Up to 1.4: the release's sharpening mode and network resolution.
  Changes take effect after restarting the game.
- **Disable** switches the game back to its own FSR (or OptiScaler's previous upscaler) and keeps HelixSR's files;
  **Enable HelixSR again** switches back without downloading or building anything.
- **Undo completely:** **Revert OptiScaler to previous upscaler** or **Restore the game's FSR** (plus **Remove HelixSR
  launch option** for 1.5.x). The game's original files and settings come back as they were.

## What it does

1. **HelixSR release**: a dropdown of every release on
   [HelixSR's release page](https://github.com/lonewolf0622/HelixSR/releases), read live from GitHub's API (the last
   list is cached for offline use), so new releases show up without a plugin update. The selected release is the one
   the install buttons use. Each release is downloaded to its own folder (`~/HelixSR/v1.4.1`, …; the base folder can
   be changed) and needs its one-time setup (`helixsr-setup.sh --yes`, about 7-10 minutes on a Steam Deck OLED; downloads NVIDIA's DLSS
   310.7.0 DLL after you confirm, builds the network, deletes NVIDIA's DLL). Several releases can sit side by side;
   switching a game to another one is one button. Releases before 1.4.0 keep the network in
   `helixsr_weights.bin`/`helixsr_kernels.pak`, which are copied along with the DLL.
2. **Game list**: every installed Steam game from all libraries (SD card too), optionally filtered to games that ship
   an FSR 3.1 DLL or have OptiScaler.
3. **Replace FSR 3.1 directly**: renames the game's `amd_fidelityfx_upscaler_dx12.dll` (or `amd_fidelityfx_dx12.dll`)
   to `*.original.dll` and puts HelixSR in its place, plus `helixsr.ini`. Same files and `helixsr-install.json` marker
   as the official `helixsr-install.sh`, so either tool can undo the other's install.
4. **OptiScaler**: creates a `HelixSR` folder next to `OptiScaler.ini` with HelixSR as both
   `amd_fidelityfx_dx12.dll` and `amd_fidelityfx_upscaler_dx12.dll`, and sets in `OptiScaler.ini`:
   `Dx12Upscaler` (`ffx` on OptiScaler 0.9+, `fsr31` on older versions), `FfxDx12Path`, `FfxDx12SRPath` (as `Z:\…`
   paths) and `[FSR] UpscalerIndex=0`. The old values are remembered and restored on revert; a full copy is kept as
   `OptiScaler.ini.helixsr-backup`. A frame generation DLL (the game's current one, else AMD's from the release) is put
next to HelixSR, since HelixSR has none of its own; OptiScaler's own frame generation setting is left alone. With
**Keep current FSR selectable**, the FSR 4 DLL OptiScaler used so far is copied
   in as `amd_fidelityfx_upscaler_dx12.amd.dll` and set as HelixSR's `[Forwarding] UpscalerDll`, so FSR 4 stays in
   OptiScaler's FFX Upscaler list for comparison. The previous `amd_fidelityfx_dx12.dll` is copied in as
   `amd_fidelityfx_dx12.original.dll` so frame generation keeps working.
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
   if enabled, OptiScaler.log lines about HelixSR/FFX.
8. **Settings**: the DLSS network on/off test switch, `NetworkResolution` and sharpening per install. The
   `NetworkResolution` choices come from the installed release's own `helixsr.ini`, since they differ between
   releases (1.4.3 is HelixSR 1.3.0 again: auto/fast/full; 1.4.0-1.4.2: auto/full/QSSM/PRSM). 1.5+ has no settings
   file; only the experimental network switch is offered there.
9. **Safety checks**: no change to a game's files while it runs (detected through Steam's process environment or a
   Windows program inside the game folder) or while Steam is still installing/updating it (`StateFlags`, download
   folder). Games with anti-cheat files (EasyAntiCheat, BattlEye, …) need an explicit "I understand the risk" before
   installing; removing is always allowed.
10. **Disable / Enable**: a direct install parks HelixSR's DLL as `*.helixsr-disabled.dll` and puts the game's file
    back; an OptiScaler install restores the previous `OptiScaler.ini` values and keeps the `HelixSR` folder. Enable
    switches back without downloading or building anything.

## Build

```
npm install
npm run package     # -> out/HelixSR-Manager.zip
```

## Notes

- Runs as the `deck` user (no root).
- Setup time: about 7-10 minutes on a Steam Deck OLED (HelixSR quotes 4-5 minutes for a desktop CPU). Don't let the
  Deck sleep during the setup (sleep pauses it).
- If the setup fails in Gaming Mode, run it once from Konsole in Desktop Mode, e.g.
  `~/HelixSR/v1.4.1/helixsr-setup.sh`; the plugin picks up the built DLL afterwards.
- Direct3D 12 only. Vulkan games aren't supported by HelixSR.
- Close the game before installing or reverting.

## Known game issues

These are fixes outside the plugin: it doesn't change game files beyond installing HelixSR. Apply them at your own
risk and only for offline play.

### DirectX 11 games (e.g. Nioh 2)

HelixSR only works in DirectX 12 games. The plugin reads the game's .exe, and for a DirectX 11 game it shows "Not
supported: this game uses DirectX 11" instead of an install button. If a game has a DirectX 12 mode, switch to it
(often a launch option or a setting) and press **Check again**.

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

Then select DLSS in the game and HelixSR 3.1.5 in OptiScaler's menu (FSR 3.X/4). A game update or Steam's "Verify
integrity of game files" restores the original exe, so repeat it after either. To undo: `mv witcher3.exe.orig witcher3.exe`.

With Wine hidden, the game also changes how it uses DirectX 12, so it depends on the device and Proton version:

| Device | Works with |
|---|---|
| Steam Deck OLED (SteamOS) | Proton 11.0-2e |
| ROG Ally Z1 Extreme (Bazzite, Mesa 25.2) | Proton Experimental 11.0-20261001 plus `VKD3D_CONFIG=nodxr` in the launch options (turns off the game's ray tracing). On 11.0-2e it crashes at startup. |

If the game doesn't start after the fix, restore the original exe and try another Proton version. proton-cachyos
"Wineland" 11.0-20260930 or newer hides Wine for this game by itself, without changing the exe.

## License

Public domain ([The Unlicense](LICENSE)): copy, change and use it however you like. The install logic follows
HelixSR's Apache-2.0 installer script; see [LICENSE](LICENSE) for the notes on HelixSR and NVIDIA's files.
