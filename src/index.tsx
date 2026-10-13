import {
  ButtonItem,
  ConfirmModal,
  DropdownItem,
  Field,
  Focusable,
  ModalRoot,
  PanelSection,
  PanelSectionRow,
  ProgressBar,
  Spinner,
  TextField,
  ToggleField,
  showModal,
  staticClasses,
} from "@decky/ui";
import { addEventListener, callable, definePlugin, removeEventListener, toaster } from "@decky/api";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FaDna } from "react-icons/fa";

// --- backend types and calls -------------------------------------------------------------------------------------------

type Result = { ok: boolean; message?: string; error?: string };

type ReleaseKind = "ffx" | "ngx"; // up to 1.4: FSR 3.1 replacement; 1.5+: DLSS (NGX) replacement via OptiScaler

type LocalVersion = {
  tag: string;
  dir: string;
  version: string | null;
  kind: ReleaseKind;
  built: boolean;
  setup_script: boolean;
  verified?: boolean; // the download matched GitHub's SHA256
  replaced_upstream?: boolean; // the zip on GitHub changed since it was downloaded
};

type Release = {
  tag: string;
  name: string;
  url: string;
  size: number | null;
  published_at: string | null;
  prerelease: boolean;
};

type HelixState = {
  base: string;
  active: string | null;
  versions: LocalVersion[];
  dir: string | null;
  downloaded: boolean;
  version: string | null;
  built: boolean;
  setup_script: boolean;
  setup: SetupStatus;
  kind: ReleaseKind | null;
};

type SetupStatus = {
  state: "idle" | "running" | "succeeded" | "failed" | "cancelled" | "stopped";
  tag: string | null;
  adopted: boolean;
  rc: number | null;
  built: boolean;
  started: number | null;
  finished: number | null;
  now: number;
  progress: number;
  phase: string;
  log_age: number | null;
  cpu_seconds: number;
  processes: string[];
  errors: string[];
  tail: string[];
  log_path: string;
};

type Diagnostic = { name: string; ok: boolean; detail: string };

type Check = {
  exists: boolean;
  status: "running" | "error" | "loaded" | "none";
  mtime?: number;
  highlights: string[];
  tail: string[];
  // per_frame: from HelixSR's per-frame lines; otherwise only the maximum render size the upscaler was created with
  last_upscale?: { render: string; output: string; ratio: number; mode: string; network: string | null; per_frame: boolean } | null;
};

type IniValues = {
  exists: boolean;
  network_resolution: string;
  sharpening: string;
  upscaler_dll: string;
  model_e_enabled: boolean;
  network_resolutions: string[]; // what this install's own helixsr.ini documents (differs between releases)
  sharpener: string; // 1.8+: off / nvidia / rcas
  sharpness: string; // 1.8+: 0.0 - 1.0
};

type DirectTarget = {
  path: string;
  rel: string;
  state: "original" | "helixsr" | "helixsr_no_backup" | "conflict" | "disabled";
  helix_version: string | null;
  near_optiscaler: boolean;
  size: number;
  dx11: boolean; // the game exe next to it is DirectX 11 only: HelixSR can't run there
  check: Check;
  ini: IniValues;
};

type OptiTarget = {
  dir: string;
  rel: string;
  configured: boolean;
  installed_kind: ReleaseKind | "official" | null; // "official": set up by HelixSR 1.7+'s own setup
  nvngx_path: string;
  helix_folder_present: boolean;
  helix_version: string | null;
  dx12_upscaler: string;
  upscaler_index: string;
  ffx_path: string;
  ffx_sr_path: string;
  current_sr_dll: { path: string; size: number } | null;
  kept_fsr4: boolean;
  log_to_file: boolean;
  disabled: boolean; // HelixSR's files stay, OptiScaler uses its previous upscaler
  official_route: "optiscaler" | "dlss" | null; // how HelixSR's own setup installed it
  hints: { level: "warn" | "info"; text: string }[]; // OptiScaler settings worth knowing about
  dx11: boolean; // the game exe next to OptiScaler is DirectX 11 only: HelixSR can't run there
  check: Check;
  opti_log: { exists: boolean; path: string; mtime?: number; lines: string[]; not_nvidia: boolean };
  ini: IniValues;
  helix_folder: string;
};

type Active = { ready: boolean; tag: string | null; version: string | null; kind: ReleaseKind | null };

function versionAtLeast(v: string | null | undefined, major: number, minor: number) {
  const m = (v ?? "").match(/(\d+)\.(\d+)/);
  return !!m && (Number(m[1]) > major || (Number(m[1]) === major && Number(m[2]) >= minor));
}

// Only 1.5.x and 1.6.x were the DLSS (NGX) route; 1.7 went back to replacing FSR 3.1. Before a release is downloaded,
// its tag is all there is to go by.
function isNgxRelease(tag: string | null, local?: LocalVersion) {
  if (local) return local.kind === "ngx";
  return versionAtLeast(tag, 1, 5) && !versionAtLeast(tag, 1, 7);
}

// Settings differ per release: up to 1.4 the release's helixsr.ini (sharpening Mode, NetworkResolution); 1.5-1.7 none
// (1.7 ignores sharpening "whatever an old helixsr.ini says"); 1.8+ optional sharpening (Sharpener / Sharpness, off by
// default). The network test switch is offered everywhere, as an experiment from 1.5 on.
type SettingsStyle = "legacy" | "none" | "sharpener";

function settingsStyle(kind: string | null, version: string | null | undefined): SettingsStyle {
  if (versionAtLeast(version, 1, 8)) return "sharpener";
  if (kind === "ngx" || kind === "official" || versionAtLeast(version, 1, 5)) return "none";
  return "legacy";
}

const SHARPENERS = [
  { data: "off", label: "Off (as DLSS)" },
  { data: "nvidia", label: "NVIDIA (Image Sharpening)" },
  { data: "rcas", label: "AMD RCAS (FSR's)" },
];
const SHARPNESS = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0"];

type GameSummary = { appid: string; name: string; path: string; fsr: boolean; optiscaler: boolean; helixsr: boolean };
type GameDetail = Result & {
  appid: string;
  name: string;
  path: string;
  direct: DirectTarget[];
  optiscaler: OptiTarget[];
  running: string[]; // processes of the game, if it runs
  steam_busy: string | null; // Steam still installing/updating it
  anticheat: string[]; // anti-cheat files found in the game folder
  anticheat_ack: boolean;
  session: Session;
  // installs of HelixSR 1.8.1+'s experimental DLSS route made by its own setup (shown, not managed)
  official_dlss: { dir: string; rel: string; helix_version: string | null; check: Check }[];
};

// the current (running) or last game session, to tell whether a helixsr.log belongs to it
type Session = { running: boolean; started: number | null; last_played: number | null };

// Why installing / removing is blocked right now (the backend checks the same), or null
type Guard = { install: string | null; remove: string | null };

const getHelixState = callable<[], HelixState>("get_helix_state");
const setAnticheatAck = callable<[appid: string, on: boolean], Result>("set_anticheat_ack");
const setDisabled = callable<[path: string, disabled: boolean], Result>("set_disabled");
const setHelixDir = callable<[path: string], HelixState>("set_helix_dir");
const listReleases = callable<[], Result & { offline: boolean; releases: Release[] }>("list_releases");
const setActive = callable<[tag: string], Result>("set_active");
const downloadRelease = callable<[tag: string], Result>("download_release");
type DownloadStatus = { active: boolean; tag?: string; bytes?: number; total?: number | null; phase?: string };
const getDownloadStatus = callable<[], DownloadStatus>("get_download_status");
const deleteRelease = callable<[tag: string], Result>("delete_release");
const startSetup = callable<[tag: string], Result>("start_setup");
const cancelSetup = callable<[], boolean>("cancel_setup");
const getSetupLog = callable<[], { path: string; lines: string[] }>("get_setup_log");
const runDiagnostics = callable<[], Diagnostic[]>("run_diagnostics");
const saveDebugReport = callable<[], Result>("save_debug_report");
const cleanPreview = callable<[], { items: string[]; bytes: number }>("clean_preview");
const cleanAll = callable<[], Result>("clean");
const listGames = callable<[], GameSummary[]>("list_games");
const getGame = callable<[appid: string], GameDetail>("get_game");
const installDirect = callable<[path: string], Result>("install_direct");
const uninstallDirect = callable<[path: string], Result>("uninstall_direct");
const installOptiscaler = callable<[path: string, keepFsr4: boolean], Result>("install_optiscaler");
const uninstallOptiscaler = callable<[path: string], Result>("uninstall_optiscaler");
const setOptiLogging = callable<[path: string, on: boolean], Result>("set_opti_logging");
const setHelixOption = callable<[folder: string, option: string, value: string], Result>("set_helix_option");

const SHARPENING = ["off", "game", "override"];

// --- small UI helpers --------------------------------------------------------------------------------------------------

const small: React.CSSProperties = { fontSize: 12, lineHeight: 1.35, color: "#b8bcbf", wordBreak: "break-word" };
const mono: React.CSSProperties = {
  fontFamily: "monospace", fontSize: 10, lineHeight: 1.35, color: "#c9ced1", wordBreak: "break-all",
  whiteSpace: "pre-wrap", background: "rgba(0,0,0,0.25)", padding: 6, borderRadius: 3,
};
const STATUS: Record<Check["status"], { color: string; text: string }> = {
  running: { color: "#5ba32b", text: "HelixSR network running" },
  error: { color: "#d94126", text: "HelixSR loaded, but the network is NOT running" },
  loaded: { color: "#e5a50a", text: "HelixSR loaded, no upscaling yet" },
  none: { color: "#8b929a", text: "HelixSR not loaded yet" },
};

function toast(r: Result, title = "HelixSR") {
  toaster.toast({ title, body: r.ok ? r.message ?? "Done" : r.error ?? "Failed" });
}

function storage(key: string, fallback: string) {
  try {
    return localStorage.getItem(`helixsr-manager:${key}`) ?? fallback;
  } catch {
    return fallback;
  }
}
function store(key: string, value: string) {
  try {
    localStorage.setItem(`helixsr-manager:${key}`, value);
  } catch {
    /* ignore */
  }
}

function notReady(a: Active) {
  if (!a.tag) return "Select a HelixSR release first";
  return a.version ? `Run the setup for ${a.tag} first` : `Download ${a.tag} first`;
}

const GREEN = "#5ba32b";
const YELLOW = "#e5a50a";
const RED = "#d94126";
const GREY = "#8b929a";
const mb = (b: number) => (b / 1048576).toFixed(1);

// A switch whose state each viewer keeps (localStorage), e.g. "Show technical details".
function useStoredFlag(key: string, fallback = false): [boolean, (v: boolean) => void] {
  const [on, setOn] = useState(storage(key, fallback ? "1" : "0") === "1");
  return [
    on,
    (v: boolean) => {
      setOn(v);
      store(key, v ? "1" : "0");
    },
  ];
}

// A panel section that folds away: the header toggles it (A button or touch), the open state is kept per viewer, and a
// short summary shows while it's closed so nothing important is hidden without a trace.
function Accordion({
  id,
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  id: string;
  title: string;
  summary?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useStoredFlag(`open:${id}`, defaultOpen);
  const [focused, setFocused] = useState(false);
  const toggle = () => setOpen(!open);
  return (
    <PanelSection>
      <PanelSectionRow>
        <Focusable
          onActivate={toggle}
          onClick={toggle}
          onGamepadFocus={() => setFocused(true)}
          onGamepadBlur={() => setFocused(false)}
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, cursor: "pointer",
            padding: "6px 8px", margin: "0 -8px", borderRadius: 3,
            background: focused ? "rgba(255,255,255,0.12)" : "transparent",
          }}
        >
          <div className={staticClasses.PanelSectionTitle} style={{ margin: 0, padding: 0 }}>
            {title}
          </div>
          <span style={{ fontSize: 12, color: "#b8bcbf" }}>{open ? "▾" : "▸"}</span>
        </Focusable>
      </PanelSectionRow>
      {!open && summary && <Note>{summary}</Note>}
      {open && children}
    </PanelSection>
  );
}

// A progress bar with its text above, aligned with the other rows. (ProgressBarWithInfo is a full list item with its
// own padding; inside a PanelSectionRow it got indented twice and ran past the right edge.)
function Progress({ percent, indeterminate, text, right }: { percent: number; indeterminate: boolean; text: string; right?: string }) {
  return (
    <PanelSectionRow>
      <div style={{ width: "100%", boxSizing: "border-box" }}>
        <div style={{ ...small, display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
          <span>{text}</span>
          {right && <span style={{ flexShrink: 0 }}>{right}</span>}
        </div>
        <ProgressBar nProgress={percent} indeterminate={indeterminate} />
      </div>
    </PanelSectionRow>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <PanelSectionRow>
      <div style={small}>{children}</div>
    </PanelSectionRow>
  );
}

// --- HelixSR download + setup ------------------------------------------------------------------------------------------

function FolderModal({ initial, closeModal, onSave }: { initial: string; closeModal?: () => void; onSave: (v: string) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <ConfirmModal
      strTitle="HelixSR folder"
      strDescription="Each downloaded release gets its own subfolder here (v1.4.1, ...), built by its setup. Leave empty for ~/HelixSR."
      strOKButtonText="Save"
      closeModal={closeModal}
      onOK={() => onSave(value)}
    >
      <TextField value={value} onChange={(e) => setValue(e.target.value)} />
    </ConfirmModal>
  );
}

function duration(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
}

// A long text the controller can scroll through: one focusable block per chunk, so D-pad down moves through it.
function ScrollText({ lines }: { lines: string[] }) {
  const chunks: string[][] = [];
  for (let i = 0; i < lines.length; i += 20) chunks.push(lines.slice(i, i + 20));
  return (
    <div style={{ maxHeight: "60vh", overflowY: "auto" }}>
      {chunks.length === 0 && <div style={mono}>(empty)</div>}
      {chunks.map((c, i) => (
        <Focusable key={i} onActivate={() => {}} style={{ ...mono, borderRadius: 0, marginBottom: 1 }}>
          {c.join("\n")}
        </Focusable>
      ))}
    </div>
  );
}

function LogModal({ closeModal }: { closeModal?: () => void }) {
  const [log, setLog] = useState<{ path: string; lines: string[] } | null>(null);
  useEffect(() => {
    getSetupLog().then(setLog);
  }, []);
  return (
    <ModalRoot closeModal={closeModal}>
      <div className={staticClasses.Title} style={{ marginBottom: 4 }}>Setup log</div>
      <div style={{ ...small, marginBottom: 8 }}>{log?.path ?? "Loading…"}</div>
      {log && <ScrollText lines={log.lines} />}
    </ModalRoot>
  );
}

function DiagnosticsModal({ closeModal }: { closeModal?: () => void }) {
  const [items, setItems] = useState<Diagnostic[] | null>(null);
  useEffect(() => {
    runDiagnostics().then(setItems);
  }, []);
  return (
    <ModalRoot closeModal={closeModal}>
      <div className={staticClasses.Title} style={{ marginBottom: 8 }}>Setup diagnostics</div>
      {!items ? (
        <div style={{ display: "flex", gap: 8, alignItems: "center", ...small }}>
          <Spinner style={{ width: 20, height: 20 }} /> Checking…
        </div>
      ) : (
        <div style={{ maxHeight: "60vh", overflowY: "auto" }}>
          {items.map((d) => (
            <Focusable key={d.name} onActivate={() => {}} style={{ ...small, padding: "4px 0" }}>
              <span style={{ color: d.ok ? "#5ba32b" : "#d94126", fontWeight: 600 }}>
                {d.ok ? "✓" : "✗"} {d.name}
              </span>
              <div style={{ wordBreak: "break-all" }}>{d.detail}</div>
            </Focusable>
          ))}
        </div>
      )}
    </ModalRoot>
  );
}

function CleanModal({ closeModal, onDone }: { closeModal?: () => void; onDone: () => void }) {
  const [preview, setPreview] = useState<{ items: string[]; bytes: number } | null>(null);
  useEffect(() => {
    cleanPreview().then(setPreview);
  }, []);
  const empty = preview !== null && preview.items.length === 0;
  return (
    <ConfirmModal
      strTitle="Remove all downloaded files?"
      strDescription={
        empty
          ? "Nothing to remove."
          : "Deletes every downloaded HelixSR release with its built network, plus the setup's Python, shader " +
            "compiler and temporary files. Games that have HelixSR installed keep working (they have their own copy); " +
            "to use another release later, download it and run its setup again."
      }
      strOKButtonText={preview ? `Remove (${(preview.bytes / 1048576).toFixed(0)} MB)` : "Remove"}
      bOKDisabled={!preview || empty}
      closeModal={closeModal}
      onOK={async () => {
        toast(await cleanAll(), "Clean");
        onDone();
      }}
    >
      {preview && !empty && <ScrollText lines={preview.items} />}
    </ConfirmModal>
  );
}

function SetupPanel({ s, refresh }: { s: SetupStatus; refresh: () => void }) {
  // the backend's clock vs. ours, so the elapsed time ticks every second between polls
  const offset = useMemo(() => s.now - Date.now() / 1000, [s.now]);
  const [, tick] = useState(0);
  const cpuHistory = useRef<{ t: number; cpu: number }[]>([]);
  const running = s.state === "running";

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  useEffect(() => {
    const h = cpuHistory.current;
    h.push({ t: s.now, cpu: s.cpu_seconds });
    while (h.length > 2 && s.now - h[0].t > 90) h.shift();
  }, [s.now, s.cpu_seconds]);

  const now = Date.now() / 1000 + offset;
  const elapsed = s.started ? (s.finished ?? now) - s.started : null;
  const h = cpuHistory.current;
  const span = h.length > 1 ? h[h.length - 1].t - h[0].t : 0;
  const cpuRate = span >= 20 ? (h[h.length - 1].cpu - h[0].cpu) / span : null; // CPU seconds per second
  const busy = cpuRate !== null && cpuRate > 0.05;
  const stuck = running && cpuRate !== null && !busy && (s.log_age ?? 0) > 600;

  const tools = (
    <>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => showModal(<LogModal />)}>
          Show full log
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => showModal(<DiagnosticsModal />)}>
          Run diagnostics
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={async () => toast(await saveDebugReport(), "Debug report")}>
          Save debug report
        </ButtonItem>
      </PanelSectionRow>
    </>
  );

  if (running) {
    return (
      <>
        <PanelSectionRow>
          <div style={{ display: "flex", alignItems: "center", gap: 8, ...small, color: "#dcdedf", fontWeight: 600 }}>
            <Spinner style={{ width: 22, height: 22, flexShrink: 0 }} />
            <span>Setup {s.tag ?? ""} running{s.adopted ? " (started outside this plugin version)" : ""}</span>
          </div>
        </PanelSectionRow>
        <Progress
          percent={s.progress}
          indeterminate={s.progress === 0}
          text={s.phase}
          right={elapsed !== null ? `${duration(elapsed)} elapsed` : undefined}
        />
        <Note>
          <div>
            Activity:{" "}
            {cpuRate === null ? (
              "measuring…"
            ) : busy ? (
              <span style={{ color: "#5ba32b" }}>working (CPU {Math.round(cpuRate * 100)}%)</span>
            ) : (
              <span style={{ color: "#e5a50a" }}>idle (waiting, or downloading)</span>
            )}
            {" · "}CPU time {duration(s.cpu_seconds)}
          </div>
          {s.log_age !== null && <div>Last log line {duration(s.log_age)} ago</div>}
          {s.processes.length > 0 && <div>Running now: {s.processes.join(", ")}</div>}
          <div>Steps print nothing while they work, so the log can stay unchanged for minutes.</div>
        </Note>
        {stuck && (
          <Note>
            <span style={{ color: "#d94126" }}>
              No CPU activity and no log output for {duration(s.log_age ?? 0)}: the setup looks stuck. Check the full
              log and diagnostics, then cancel and retry (or run it once from Konsole in Desktop Mode).
            </span>
          </Note>
        )}
        {s.tail.length > 0 && (
          <PanelSectionRow>
            <div style={mono}>{s.tail.slice(-5).join("\n")}</div>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={async () => {
              await cancelSetup();
              refresh();
            }}
          >
            Cancel setup
          </ButtonItem>
        </PanelSectionRow>
        {tools}
      </>
    );
  }

  if (s.state === "idle") return null;
  const outcome: Record<Exclude<SetupStatus["state"], "idle" | "running">, { color: string; text: string }> = {
    succeeded: {
      color: "#5ba32b",
      text: `Setup of ${s.tag} finished${elapsed ? ` in ${duration(elapsed)}` : ""}: network built`,
    },
    failed: {
      color: "#d94126",
      text:
        s.rc === 0
          ? `Setup of ${s.tag} ended, but the DLL has no network`
          : `Setup of ${s.tag} failed (exit code ${s.rc})${elapsed ? ` after ${duration(elapsed)}` : ""}`,
    },
    cancelled: { color: "#e5a50a", text: `Setup of ${s.tag} was cancelled` },
    stopped: {
      color: "#e5a50a",
      text: `Setup of ${s.tag} stopped without finishing (the Deck restarted, or the process was killed). Run it again.`,
    },
  };
  const o = outcome[s.state as keyof typeof outcome];
  return (
    <>
      <Note>
        <span style={{ color: o.color, fontWeight: 600 }}>{o.text}</span>
      </Note>
      {s.state !== "succeeded" && (s.errors.length > 0 || s.tail.length > 0) && (
        <PanelSectionRow>
          <div style={mono}>{(s.errors.length > 0 ? s.errors : s.tail.slice(-5)).join("\n")}</div>
        </PanelSectionRow>
      )}
      {s.state !== "succeeded" && tools}
    </>
  );
}

function DownloadProgress({ tag }: { tag: string }) {
  const [d, setD] = useState<DownloadStatus | null>(null);
  useEffect(() => {
    const poll = () => getDownloadStatus().then(setD);
    poll();
    const id = setInterval(poll, 700);
    return () => clearInterval(id);
  }, []);
  const total = d?.total ?? 0;
  const bytes = d?.bytes ?? 0;
  const text =
    d?.phase === "verifying"
      ? "Checking the download (SHA256)…"
      : d?.phase === "extracting"
        ? "Unpacking…"
        : total
          ? `Downloading ${tag}: ${mb(bytes)} of ${mb(total)} MB`
          : `Downloading ${tag}${bytes ? `: ${mb(bytes)} MB` : "…"}`;
  return (
    <Progress
      percent={total && d?.phase === "downloading" ? Math.min(100, (bytes / total) * 100) : 0}
      indeterminate={!total || d?.phase !== "downloading"}
      text={text}
    />
  );
}

function Step({ n, done, current, children }: { n: number; done: boolean; current: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 6, marginTop: 3, color: done ? GREEN : current ? "#dcdedf" : GREY, fontWeight: current ? 600 : 400 }}>
      <span style={{ width: 14, flexShrink: 0, textAlign: "center" }}>{done ? "✓" : n}</span>
      <span>{children}</span>
    </div>
  );
}

function HelixSection({ state, refresh }: { state: HelixState | null; refresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [releases, setReleases] = useState<Release[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [more, setMore] = useStoredFlag("moreOptions");

  const loadReleases = useCallback(async () => {
    const r = await listReleases();
    setReleases(r.releases);
    setOffline(r.offline);
  }, []);

  useEffect(() => {
    loadReleases();
  }, [loadReleases]);

  const setupRunning = state?.setup.state === "running";
  useEffect(() => {
    if (!setupRunning) return;
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [setupRunning, refresh]);

  if (!state) return <PanelSection title="HelixSR Installation"><Note>Loading…</Note></PanelSection>;

  const latest = releases?.find((r) => !r.prerelease)?.tag;
  const local = new Map(state.versions.map((v) => [v.tag, v]));
  // every release on GitHub, plus downloaded ones GitHub no longer lists (or a hand-extracted one)
  const tags = [...(releases ?? []).map((r) => r.tag), ...state.versions.map((v) => v.tag)].filter(
    (t, i, all) => all.indexOf(t) === i,
  );
  if (state.active && !tags.includes(state.active)) tags.unshift(state.active);
  const label = (tag: string) => {
    const v = local.get(tag);
    const name = tag === "local" ? `${v?.version ?? "?"} (in ${state.base})` : tag;
    const parts = [name];
    if (tag === latest) parts.push("latest");
    if (releases?.find((r) => r.tag === tag)?.prerelease) parts.push("pre-release");
    if (isNgxRelease(tag, v)) parts.push("DLSS via OptiScaler");
    parts.push(v ? (v.built ? "✓ ready" : "needs building") : "not downloaded");
    return parts.join(" · ");
  };

  const tag = state.active;
  const rel = releases?.find((r) => r.tag === tag);
  const setupHere = setupRunning && state.setup.tag === tag;
  const version = state.version ?? tag;

  const choose = async (t: string) => {
    await setActive(t);
    refresh();
  };

  const download = async () => {
    if (!tag) return;
    setBusy(true);
    toast(await downloadRelease(tag));
    setBusy(false);
    refresh();
  };

  const remove = () =>
    tag &&
    showModal(
      <ConfirmModal
        strTitle={`Delete HelixSR ${tag}?`}
        strDescription={`Removes ${state.dir}, including its built network. Games that have this version installed keep working.`}
        strOKButtonText="Delete"
        onOK={async () => {
          toast(await deleteRelease(tag));
          refresh();
        }}
      />,
    );

  const setup = () =>
    tag &&
    showModal(
      <ConfirmModal
        strTitle={`Build HelixSR ${tag}`}
        strDescription={
          "Takes about 7-10 minutes on a Steam Deck. Keep it plugged in and awake (sleep pauses the build); you can " +
          "close this menu meanwhile, a notification tells you when it's done. HelixSR's setup downloads NVIDIA's " +
          "DLSS DLL from NVIDIA's GitHub (NVIDIA's license applies), a portable Python and Microsoft's shader " +
          "compiler, builds the network into the HelixSR DLL and deletes NVIDIA's DLL again. The result is for this " +
          "device only, don't share it."
        }
        strOKButtonText="Download and build"
        onOK={async () => {
          const r = await startSetup(tag);
          if (!r.ok) toast(r);
          refresh();
        }}
      />,
    );

  const step = !tag ? 0 : !state.downloaded ? 1 : !state.built ? 2 : 3;
  const summary = setupRunning
    ? `Building HelixSR ${state.setup.tag ?? ""}… ${Math.round(state.setup.progress)}%`
    : busy
      ? `Downloading HelixSR ${tag}…`
      : step === 0
        ? "No version selected"
        : step === 1
          ? `HelixSR ${tag}: download it next`
          : step === 2
            ? `HelixSR ${tag}: build it next`
            : `HelixSR ${version} ready to install`;

  return (
    <Accordion id="install" title="HelixSR Installation" defaultOpen summary={summary}>
      <PanelSectionRow>
        {releases === null && tags.length === 0 ? (
          <Field label="Loading releases from GitHub…" />
        ) : (
          <DropdownItem
            label="Version"
            rgOptions={tags.map((t) => ({ data: t, label: label(t) }))}
            selectedOption={tag ?? undefined}
            strDefaultLabel="Select a version"
            disabled={setupRunning || busy}
            onChange={(o) => choose(o.data)}
          />
        )}
      </PanelSectionRow>
      {tag && (
        <Note>
          <Step n={1} done={state.downloaded} current={step === 1}>
            Download HelixSR {tag}
          </Step>
          <Step n={2} done={state.built} current={step === 2}>
            Build it (setup, about 7-10 min on the Deck)
          </Step>
          <Step n={3} done={false} current={step === 3}>
            Install it into a game: pick the game below
          </Step>
          {step === 3 && (
            <div style={{ color: GREEN, marginTop: 4 }}>HelixSR {version} is ready to install.</div>
          )}
          {latest && tag !== latest && <div style={{ color: YELLOW, marginTop: 4 }}>Newer version available: {latest}</div>}
          {local.get(tag)?.replaced_upstream && (
            <div style={{ color: YELLOW, marginTop: 4 }}>
              The author replaced this version's files on GitHub since you downloaded it. Download it again (More
              options) and build it again to get the current files.
            </div>
          )}
          {offline && <div style={{ marginTop: 4 }}>GitHub not reachable: showing the last known versions.</div>}
        </Note>
      )}
      {busy && tag && <DownloadProgress tag={tag} />}
      {step === 1 && rel && !busy && !setupRunning && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={download}>
            Download HelixSR {tag}
          </ButtonItem>
        </PanelSectionRow>
      )}
      {step === 2 && state.setup_script && !setupRunning && !busy && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={setup}>
            Build HelixSR {tag}
          </ButtonItem>
        </PanelSectionRow>
      )}
      <SetupPanel s={state.setup} refresh={refresh} />
      <Note>
        Updating later: pick the newer version here, download and build it, then press "Switch to …" in each game. It
        replaces the old version, no cleanup needed.
      </Note>
      {!setupRunning && (
        <PanelSectionRow>
          <ToggleField label="More options" checked={more} onChange={setMore} />
        </PanelSectionRow>
      )}
      {more && !setupRunning && (
        <>
          <Note>
            {tag && local.get(tag)?.verified && <div>Download verified against GitHub's checksum (SHA256).</div>}
            {rel?.published_at && <div>Published {new Date(rel.published_at).toLocaleDateString()}</div>}
            {tag && versionAtLeast(local.get(tag)?.version ?? tag, 1, 7) && (
              <div>
                Since 1.7, HelixSR replaces FSR 3.1: through OptiScaler (select DLSS in the game) or in place of a
                game's own FSR 3.1 (select AMD FSR). The plugin only builds HelixSR and uses the OptiScaler you already
                have; HelixSR's own setup in Desktop Mode would also install its own OptiScaler.
              </div>
            )}
            {tag && isNgxRelease(tag, local.get(tag)) && (
              <div>
                1.5 and 1.6 run as DLSS, only through OptiScaler (0.9.4), and need a Steam launch option the plugin can
                set per game. These versions were withdrawn by the author.
              </div>
            )}
            <div>Stored in {state.base}</div>
          </Note>
          {tag && rel && state.downloaded && (
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy} onClick={download}>
                Download {tag} again
              </ButtonItem>
            </PanelSectionRow>
          )}
          {state.setup_script && state.built && (
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy} onClick={setup}>
                Build {tag} again
              </ButtonItem>
            </PanelSectionRow>
          )}
          {state.downloaded && tag !== "local" && !setupHere && (
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy} onClick={remove}>
                Delete {tag} from the Deck
              </ButtonItem>
            </PanelSectionRow>
          )}
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={loadReleases}>
              Check GitHub for new versions
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              description="Optional. Frees space on the Deck; games with HelixSR keep working."
              onClick={() => showModal(<CleanModal onDone={refresh} />)}
            >
              Clean up downloads
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => showModal(<LogModal />)}>
              Show setup log
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => showModal(<DiagnosticsModal />)}>
              Run diagnostics
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={async () => toast(await saveDebugReport(), "Debug report")}>
              Save debug report
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() =>
                showModal(
                  <FolderModal
                    initial={state.base}
                    onSave={async (v) => {
                      await setHelixDir(v);
                      refresh();
                    }}
                  />,
                )
              }
            >
              Change HelixSR folder
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </Accordion>
  );
}

// --- per-install pieces ------------------------------------------------------------------------------------------------

function sessionNote(check: Check, session?: Session): { color: string; text: string } | null {
  if (!session) return null;
  const date = (t: number) => new Date(t * 1000).toLocaleString();
  if (session.running) {
    if (!session.started) return null;
    return check.mtime && check.mtime >= session.started
      ? { color: "#5ba32b", text: "The log is from the current game session." }
      : { color: "#e5a50a", text: "Nothing logged in the current session yet: HelixSR hasn't been asked to upscale (select it in the game / OptiScaler)." };
  }
  if (!session.last_played) return null;
  if (!check.mtime) return { color: "#8b929a", text: `HelixSR wasn't loaded in the last session (${date(session.last_played)}).` };
  return check.mtime >= session.last_played - 60
    ? { color: "#8b929a", text: `The log is from the last game session (${date(session.last_played)}).` }
    : { color: "#e5a50a", text: `The log is older than the last game session (${date(session.last_played)}): HelixSR wasn't used then.` };
}

function CheckBlock({ check, ini, session, details }: { check: Check; ini: IniValues; session?: Session; details: boolean }) {
  const s = STATUS[check.status];
  const u = check.last_upscale;
  const fresh = sessionNote(check, session);
  return (
    <>
      {!ini.model_e_enabled && (
        <Note>
          <span style={{ color: "#e5a50a", fontWeight: 600 }}>
            Test mode: the DLSS network is switched off. After a game restart the picture should be HelixSR's simple,
            blurry placeholder upscale. If it looks unchanged, HelixSR isn't the active upscaler. Switch it back on
            when you're done.
          </span>
        </Note>
      )}
      {details && (
      <PanelSectionRow>
        <div style={small}>
          <span style={{ color: s.color, fontWeight: 600 }}>● {s.text}</span>
          {check.mtime && <div>helixsr.log written {new Date(check.mtime * 1000).toLocaleString()}</div>}
          {fresh && <div style={{ color: fresh.color }}>{fresh.text}</div>}
          {u && (
            <div>
              {u.per_frame ? `Last frame logged: ${u.render} → ${u.output} (${u.mode}, ${u.ratio}x)` : `Created for up to ${u.render} → ${u.output} (no frame logged yet)`}
              {u.network && <div>Network: {u.network}</div>}
            </div>
          )}
        </div>
      </PanelSectionRow>
      )}
      {details && check.highlights.length > 0 && (
        <PanelSectionRow>
          <div style={mono}>{check.highlights.join("\n")}</div>
        </PanelSectionRow>
      )}
    </>
  );
}

function IniControls({
  folder,
  ini,
  style,
  details,
  onChange,
}: {
  folder: string;
  ini: IniValues;
  style: SettingsStyle;
  details: boolean;
  onChange: () => void;
}) {
  const settingsFile = style === "legacy";
  const save = async (option: string, value: string) => {
    toast(await setHelixOption(folder, option, value));
    onChange();
  };
  return (
    <>
      {(details || !ini.model_e_enabled) && (
      <PanelSectionRow>
        <ToggleField
          label="DLSS network (Model E)"
          description={
            !settingsFile
              ? "Experimental for 1.5+: this release documents no settings but its DLL still contains this helixsr.ini switch. Turn off and restart the game; if the picture turns blurry, HelixSR is upscaling. If nothing changes, the switch may simply not apply."
              : "Turn off to prove HelixSR is upscaling: it then falls back to a simple, blurry upscale. Takes effect after restarting the game; for live comparisons switch upscalers in OptiScaler's menu."
          }
          checked={ini.model_e_enabled}
          onChange={(on) => save("model_e", on ? "true" : "false")}
        />
      </PanelSectionRow>
      )}
      {style === "sharpener" && (
        <>
          <PanelSectionRow>
            <DropdownItem
              label="Sharpening"
              description="Off by default, as DLSS. Restart the game after changing it."
              rgOptions={SHARPENERS}
              selectedOption={SHARPENERS.some((o) => o.data === ini.sharpener) ? ini.sharpener : "off"}
              onChange={(o) => save("sharpener", o.data)}
            />
          </PanelSectionRow>
          {ini.sharpener !== "off" && (
            <PanelSectionRow>
              <DropdownItem
                label="Sharpness"
                description="0.5 is NVIDIA's default."
                rgOptions={SHARPNESS.map((v) => ({ data: v, label: v }))}
                selectedOption={SHARPNESS.find((v) => Number(v) === Number(ini.sharpness)) ?? "0.5"}
                onChange={(o) => save("sharpness", o.data)}
              />
            </PanelSectionRow>
          )}
        </>
      )}
      {settingsFile && (
        <>
      {ini.network_resolutions.length > 0 && (
        <PanelSectionRow>
          <DropdownItem
            label="Network resolution"
            description={
              ini.network_resolutions.some((v) => v.startsWith("QSSM"))
                ? "QSSM: sharper, slower. PRSM: faster, softer."
                : ini.network_resolutions.includes("fast")
                  ? "fast: faster, a little softer (also in Performance mode). full: always the full output size."
                  : undefined
            }
            rgOptions={ini.network_resolutions.map((v) => ({ data: v, label: v }))}
            selectedOption={ini.network_resolution}
            onChange={(o) => save("network_resolution", o.data)}
          />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <DropdownItem
          label="Sharpening"
          rgOptions={SHARPENING.map((v) => ({ data: v, label: v }))}
          selectedOption={ini.sharpening}
          onChange={(o) => save("sharpening", o.data)}
        />
      </PanelSectionRow>
        </>
      )}
    </>
  );
}

function DirectSection({
  items,
  active,
  guard,
  session,
  details,
  reload,
}: {
  items: DirectTarget[];
  active: Active;
  guard: Guard;
  session: Session;
  details: boolean;
  reload: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  if (items.length === 0) return null;

  const run = async (path: string, fn: () => Promise<Result>) => {
    setBusy(path);
    toast(await fn());
    setBusy(null);
    reload();
  };

  const summary = items
    .map((t) =>
      t.state === "helixsr" || t.state === "helixsr_no_backup"
        ? `HelixSR ${t.helix_version ?? ""} installed`
        : t.dx11 && t.state === "original"
          ? "Not supported (DirectX 11 game)"
        : t.state === "disabled"
          ? "HelixSR disabled"
          : t.state === "conflict"
            ? "Needs attention (game updated?)"
            : "HelixSR not installed",
    )
    .filter((v, i, all) => all.indexOf(v) === i)
    .join(" · ");

  return (
    <Accordion id="direct" title="In place of the game's FSR 3.1" summary={summary}>
      {items.map((t) => {
        const installed = t.state === "helixsr";
        const differs = installed && !!active.version && t.helix_version !== active.version;
        return (
          <div key={t.path}>
            <Note>
              <div style={{ fontWeight: 600 }}>{t.rel}</div>
              <div>
                {t.state === "original" && "The game's own FSR 3.1. Installing HelixSR here means: select AMD FSR in the game."}
                {installed && `HelixSR ${t.helix_version ?? ""} installed`}
                {t.state === "helixsr_no_backup" && "HelixSR without a backup of the game's file"}
                {t.state === "conflict" && "A backup exists but this file is not HelixSR (game updated?)"}
                {t.state === "disabled" && `HelixSR ${t.helix_version ?? ""} disabled: the game's own FSR is active`}
              </div>
              {t.near_optiscaler && !installed && (
                <div style={{ color: "#e5a50a" }}>
                  This DLL sits next to OptiScaler and is probably OptiScaler's own FSR DLL. Use the OptiScaler section below instead.
                </div>
              )}
            </Note>
            {t.state === "original" && active.kind === "ngx" && (
              <Note>
                HelixSR {active.version} only works through OptiScaler (as DLSS). Pick a 1.4 release to replace this
                DLL directly.
              </Note>
            )}
            {t.state === "original" && t.dx11 && (
              <Note>
                <span style={{ color: YELLOW }}>This game uses DirectX 11. HelixSR only works in DirectX 12 games, so it can't be installed here.</span>
              </Note>
            )}
            {t.state === "original" && active.kind !== "ngx" && !t.dx11 && (
              <PanelSectionRow>
                <ButtonItem layout="below" disabled={!active.ready || busy !== null || !!guard.install} onClick={() => run(t.path, () => installDirect(t.path))}>
                  {active.ready ? `Install HelixSR ${active.version} here` : notReady(active)}
                </ButtonItem>
              </PanelSectionRow>
            )}
            {differs && active.ready && active.kind !== "ngx" && (
              <PanelSectionRow>
                <ButtonItem layout="below" disabled={busy !== null || !!guard.install} onClick={() => run(t.path, () => installDirect(t.path))}>
                  Switch to HelixSR {active.version}
                </ButtonItem>
              </PanelSectionRow>
            )}
            {t.state === "disabled" && (
              <PanelSectionRow>
                <ButtonItem layout="below" disabled={busy !== null || !!guard.install} onClick={() => run(t.path, () => setDisabled(t.path, false))}>
                  Enable HelixSR again
                </ButtonItem>
              </PanelSectionRow>
            )}
            {installed && (
              <PanelSectionRow>
                <ButtonItem layout="below" disabled={busy !== null || !!guard.remove} onClick={() => run(t.path, () => setDisabled(t.path, true))}>
                  Disable (keep HelixSR, use the game's FSR)
                </ButtonItem>
              </PanelSectionRow>
            )}
            {(installed || t.state === "conflict" || t.state === "disabled") && (
              <PanelSectionRow>
                <ButtonItem layout="below" disabled={busy !== null || !!guard.remove} onClick={() => run(t.path, () => uninstallDirect(t.path))}>
                  {t.state === "disabled" ? "Remove HelixSR" : "Restore the game's FSR"}
                </ButtonItem>
              </PanelSectionRow>
            )}
            {installed && (
              <>
                <CheckBlock check={t.check} ini={t.ini} session={session} details={details} />
                <IniControls
                  folder={t.path.replace(/\/[^/]+$/, "")}
                  ini={t.ini}
                  style={settingsStyle("ffx", t.helix_version)}
                  details={details}
                  onChange={reload}
                />
              </>
            )}
          </div>
        );
      })}
    </Accordion>
  );
}

// --- Steam launch options (HelixSR 1.5+ needs the GPU to look like an NVIDIA one) --------------------------------------

const NGX_LAUNCH_VARS = "PROTON_FORCE_NVAPI=1 DXVK_NVAPI_GPU_ARCH=AD100";

function readLaunchOptions(appId: number): Promise<string | null> {
  return new Promise((resolve) => {
    let done = false;
    let reg: { unregister(): void } | null = null;
    const finish = (value: string | null) => {
      if (done) return;
      done = true;
      setTimeout(() => reg?.unregister(), 0); // the callback can fire before RegisterForAppDetails returns
      resolve(value);
    };
    try {
      reg = SteamClient.Apps.RegisterForAppDetails(appId, (d) => finish(d?.strLaunchOptions ?? ""));
    } catch {
      finish(null);
    }
    setTimeout(() => finish(null), 3000);
  });
}

const hasNgxVars = (o: string) => /\bPROTON_FORCE_NVAPI=1\b/.test(o) && /\bDXVK_NVAPI_GPU_ARCH=\S+/.test(o);
const stripNgxVars = (o: string) =>
  o.replace(/\bPROTON_FORCE_NVAPI=\S*\s*/g, "").replace(/\bDXVK_NVAPI_GPU_ARCH=\S*\s*/g, "").trim();

// The variables go first; whatever was there (e.g. Decky Framegen's "~/fgmod/fgmod %command%") stays after them.
function withNgxVars(o: string) {
  const rest = stripNgxVars(o);
  if (!rest) return `${NGX_LAUNCH_VARS} %command%`;
  return `${NGX_LAUNCH_VARS} ${rest.includes("%command%") ? rest : `%command% ${rest}`}`;
}

function withoutNgxVars(o: string) {
  const rest = stripNgxVars(o);
  if (rest === "%command%") return "";
  // "%command% -dx12" means the same to Steam as "-dx12", the form a game with only arguments had before
  return rest.startsWith("%command% ") && !rest.slice(10).includes("%command%") ? rest.slice(10) : rest;
}

function LaunchOptionControl({ appid, needed }: { appid: string; needed: boolean }) {
  const id = Number(appid);
  const [opts, setOpts] = useState<string | null | undefined>(undefined);
  const load = useCallback(() => {
    readLaunchOptions(id).then(setOpts);
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);

  const apply = (value: string) => {
    try {
      SteamClient.Apps.SetAppLaunchOptions(id, value);
      toaster.toast({ title: "Launch options", body: value ? `Set to: ${value}` : "Cleared" });
    } catch (e) {
      toaster.toast({ title: "Launch options", body: `Couldn't set them: ${e}` });
    }
    setTimeout(load, 500);
  };

  if (opts === undefined) return needed ? <Note>Reading the game's launch options…</Note> : null;
  if (opts === null) {
    return needed ? (
      <Note>
        <span style={{ color: "#e5a50a" }}>
          Couldn't read this game's launch options. Add them in Steam (game → Properties → Launch Options):
        </span>
        <div style={mono}>{NGX_LAUNCH_VARS} %command%</div>
      </Note>
    ) : null;
  }
  const has = hasNgxVars(opts);
  if (!needed && !has) return null;
  return (
    <>
      <Note>
        {needed ? (
          has ? (
            <span style={{ color: "#5ba32b", fontWeight: 600 }}>✓ Launch option set (GPU shows up as NVIDIA for DLSS)</span>
          ) : (
            <span style={{ color: "#e5a50a", fontWeight: 600 }}>
              Launch option missing: without it OptiScaler doesn't offer DLSS, so HelixSR never runs.
            </span>
          )
        ) : (
          <span style={{ color: "#e5a50a" }}>
            The launch option for HelixSR 1.5+ is still set. It isn't needed without HelixSR 1.5+.
          </span>
        )}
        <div style={mono}>{opts || "(no launch options)"}</div>
      </Note>
      {needed && !has && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => apply(withNgxVars(opts))}>
            Add launch option
          </ButtonItem>
        </PanelSectionRow>
      )}
      {(!needed || has) && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => apply(withoutNgxVars(opts))}>
            Remove HelixSR launch option
          </ButtonItem>
        </PanelSectionRow>
      )}
    </>
  );
}

function OptiItem({
  o,
  active,
  appid,
  guard,
  session,
  details,
  reload,
}: {
  o: OptiTarget;
  active: Active;
  appid: string;
  guard: Guard;
  session: Session;
  details: boolean;
  reload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [keepFsr4, setKeepFsr4] = useState(true);

  const run = async (fn: () => Promise<Result>) => {
    setBusy(true);
    toast(await fn(), "OptiScaler");
    setBusy(false);
    reload();
  };

  const ngxActive = active.kind === "ngx";
  const installed = o.installed_kind;
  const official = installed === "official";
  const differs = installed !== null && !!active.version && o.helix_version !== active.version;
  const sizeMb = o.current_sr_dll ? (o.current_sr_dll.size / 1048576).toFixed(1) : null;

  return (
    <>
      <Note>
        <div style={{ fontWeight: 600 }}>{o.rel === "." ? "Game folder" : o.rel}</div>
        <div>
          {official
            ? o.official_route === "dlss"
              ? `HelixSR ${o.helix_version ?? ""} installed by HelixSR's own setup as the game's DLSS (experimental route, without OptiScaler)`
              : `HelixSR ${o.helix_version ?? ""} installed by HelixSR's own setup, together with its own OptiScaler`
            : o.disabled
            ? `HelixSR ${o.helix_version ?? ""} disabled: OptiScaler uses its previous upscaler`
            : o.configured
            ? installed === "ngx"
              ? `Uses HelixSR ${o.helix_version ?? ""} as DLSS`
              : `Uses HelixSR ${o.helix_version ?? ""}${o.kept_fsr4 ? " (FSR 4 selectable next to it)" : ""}`
            : installed
              ? "HelixSR folder present, but OptiScaler.ini no longer points to it (OptiScaler reinstalled?)"
              : "OptiScaler found. Installing HelixSR here means: select DLSS in the game, which gives HelixSR the best input. XeSS or FSR also work if DLSS isn't offered, but can shimmer more."}
        </div>
        {details && !o.configured && !installed && (
          <div>
            {ngxActive
              ? `Dx12Upscaler=${o.dx12_upscaler}, NvngxPath=${o.nvngx_path}`
              : `Dx12Upscaler=${o.dx12_upscaler}, FfxDx12SRPath=${o.ffx_sr_path}`}
          </div>
        )}
        {details && !o.configured && o.current_sr_dll && (
          <div>Current FSR upscaler DLL: {o.current_sr_dll.path.split("/").slice(-2).join("/")} ({sizeMb} MB)</div>
        )}
        {ngxActive && !o.configured && (
          <div>
            HelixSR {active.version} runs as DLSS through OptiScaler (0.9.4 needed). Your FSR setup stays selectable
            in OptiScaler's menu.
          </div>
        )}
      </Note>
      {!ngxActive && !o.configured && o.current_sr_dll && !(o.dx11 && !installed) && (
        <PanelSectionRow>
          <ToggleField
            label="Keep current FSR selectable"
            description="Your FSR 4 DLL stays in OptiScaler's FFX Upscaler list after HelixSR, for comparing."
            checked={keepFsr4}
            onChange={setKeepFsr4}
          />
        </PanelSectionRow>
      )}
      {o.disabled ? (
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy || !!guard.install} onClick={() => run(() => setDisabled(o.dir, false))}>
            Enable HelixSR again
          </ButtonItem>
        </PanelSectionRow>
      ) : official ? (
        <Note>
          The plugin leaves this install to HelixSR's setup. To update or remove it, run helixsr-setup.sh from HelixSR's
          folder in Desktop Mode (answer r for this game to remove). The check below still works.
        </Note>
      ) : o.dx11 && !installed ? (
        <Note>
          <span style={{ color: YELLOW }}>This game uses DirectX 11. HelixSR only works in DirectX 12 games, so it can't be installed here.</span>
        </Note>
      ) : !o.configured ? (
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={!active.ready || busy || !!guard.install}
            onClick={() => run(() => installOptiscaler(o.dir, keepFsr4 && !!o.current_sr_dll))}
          >
            {active.ready
              ? installed
                ? `Point OptiScaler at HelixSR ${active.version} again`
                : `Install HelixSR ${active.version} via OptiScaler${ngxActive ? " (as DLSS)" : ""}`
              : notReady(active)}
          </ButtonItem>
        </PanelSectionRow>
      ) : (
        active.ready &&
        differs && (
          <PanelSectionRow>
            <ButtonItem layout="below" disabled={busy || !!guard.install} onClick={() => run(() => installOptiscaler(o.dir, o.kept_fsr4))}>
              Switch to HelixSR {active.version}
              {ngxActive && installed === "ffx" ? " (as DLSS)" : ""}
            </ButtonItem>
          </PanelSectionRow>
        )
      )}
      {o.configured && !official && !o.disabled && (
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy || !!guard.remove} onClick={() => run(() => setDisabled(o.dir, true))}>
            Disable (keep HelixSR, use the previous upscaler)
          </ButtonItem>
        </PanelSectionRow>
      )}
      {installed && !official && (
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy || !!guard.remove} onClick={() => run(() => uninstallOptiscaler(o.dir))}>
            Revert OptiScaler to previous upscaler
          </ButtonItem>
        </PanelSectionRow>
      )}
      <LaunchOptionControl appid={appid} needed={installed === "ngx"} />
      {o.hints.some((h) => details || h.level === "warn") && (
        <Note>
          {o.hints.filter((h) => details || h.level === "warn").map((h) => (
            <div key={h.text} style={{ color: h.level === "warn" ? "#e5a50a" : undefined, marginTop: 2 }}>
              {h.level === "warn" ? "⚠ " : "ⓘ "}
              {h.text}
            </div>
          ))}
        </Note>
      )}
      {o.configured && (
        <>
          {installed === "ngx" && o.opti_log.not_nvidia && (
            <Note>
              <span style={{ color: "#d94126" }}>
                OptiScaler.log says "Not running on Nvidia, disabling DLSS": the launch option wasn't active when the
                game last started. Check it above, then restart the game.
              </span>
            </Note>
          )}
          <CheckBlock check={o.check} ini={o.ini} session={session} details={details} />
          <Note>
            {installed === "ngx"
              ? "To compare live: OptiScaler's menu shows DLSS as the upscaler (that's HelixSR); switch to FSR there and back."
              : 'To compare live: in OptiScaler\'s menu, Upscalers → FFX Upscaler reads "FSR HelixSR (3.1.5)" when HelixSR is used; switch to XeSS or FSR 4 there and back. A red frame around the picture means HelixSR has no network (build it again).'}
          </Note>
          {details && (
          <PanelSectionRow>
            <ToggleField
              label="OptiScaler log file"
              description="Writes OptiScaler.log so its lines about HelixSR show up below."
              checked={o.log_to_file}
              disabled={busy}
              onChange={(on) => run(() => setOptiLogging(o.dir, on))}
            />
          </PanelSectionRow>
          )}
          {details && o.opti_log.exists && (
            <PanelSectionRow>
              <div style={mono}>
                {o.opti_log.lines.length > 0
                  ? o.opti_log.lines.join("\n")
                  : "OptiScaler.log has no lines about HelixSR / DLSS / FFX yet."}
              </div>
            </PanelSectionRow>
          )}
          <IniControls
            folder={o.helix_folder}
            ini={o.ini}
            style={settingsStyle(installed, o.helix_version)}
            details={details}
            onChange={reload}
          />
        </>
      )}
    </>
  );
}

type Install = { how: "direct" | "opti" | "dlss"; version: string | null; check: Check };

// What the closed OptiScaler section says: HelixSR's state there, plus how many warnings it holds.
function optiSummary(items: OptiTarget[]) {
  const states = items
    .map((o) =>
      o.installed_kind === "official"
        ? `HelixSR ${o.helix_version ?? ""} (installed by HelixSR's setup)`
        : o.disabled
          ? "HelixSR disabled"
          : o.configured
            ? `HelixSR ${o.helix_version ?? ""} in use`
            : o.dx11 && !o.installed_kind
              ? "Not supported (DirectX 11 game)"
              : o.installed_kind
              ? "Needs attention (OptiScaler reinstalled?)"
              : "HelixSR not installed",
    )
    .filter((v, i, all) => all.indexOf(v) === i);
  const warnings = items.reduce((n, o) => n + o.hints.filter((h) => h.level === "warn").length, 0);
  return (
    <>
      {states.join(" · ")}
      {warnings > 0 && <span style={{ color: YELLOW }}> · ⚠ {warnings === 1 ? "1 warning" : `${warnings} warnings`} inside</span>}
    </>
  );
}

// Whether a helixsr.log belongs to the current/last game session ("unknown" without session data).
function freshness(check: Check, session: Session): "current" | "last" | "stale" | "unknown" {
  if (session.running && session.started) return check.mtime && check.mtime >= session.started ? "current" : "stale";
  if (!session.running && session.last_played) return check.mtime && check.mtime >= session.last_played - 60 ? "last" : "stale";
  return "unknown";
}

const SELECT_TEXT: Record<Install["how"], string> = {
  direct: "select AMD FSR as the upscaler in the game",
  opti: "select DLSS as the upscaler in the game: it gives HelixSR the best input (XeSS or FSR also work if the game doesn't offer DLSS, but can shimmer more)",
  dlss: "select DLSS as the upscaler in the game",
};

// One line per game: is HelixSR installed here, and did it actually upscale? Built from the install state, helixsr.log
// and the game's session times.
function gameStatus(game: GameDetail, active: Active): { color: string; title: string; detail: string; extra?: string } {
  const installs: Install[] = [
    ...game.direct
      .filter((t) => t.state === "helixsr" || t.state === "helixsr_no_backup")
      .map((t) => ({ how: "direct" as const, version: t.helix_version, check: t.check })),
    ...game.optiscaler
      .filter((o) => o.configured && !o.disabled)
      .map((o) => ({ how: "opti" as const, version: o.helix_version, check: o.check })),
    ...game.official_dlss.map((d) => ({ how: "dlss" as const, version: d.helix_version, check: d.check })),
  ];
  if (installs.length === 0) {
    if (game.direct.some((t) => t.state === "disabled") || game.optiscaler.some((o) => o.disabled)) {
      return { color: GREY, title: "HelixSR is disabled in this game", detail: 'The game uses its previous upscaler. "Enable HelixSR again" below switches back.' };
    }
    const targets = [...game.direct.filter((t) => t.state === "original"), ...game.optiscaler.filter((o) => !o.installed_kind)];
    if (targets.length > 0 && targets.every((t) => t.dx11)) {
      return {
        color: YELLOW,
        title: "Not supported: this game uses DirectX 11",
        detail: "HelixSR only works in DirectX 12 games. If the game has a DirectX 12 mode (often a launch option or a setting), switch to it and press Check again.",
      };
    }
    if (!active.ready) {
      return { color: GREY, title: "HelixSR isn't installed in this game", detail: "First download and build HelixSR (steps 1 and 2 above), then install it here." };
    }
    const where = game.optiscaler.length > 0
      ? `open the OptiScaler section and press "Install HelixSR ${active.version} via OptiScaler"`
      : `open "In place of the game's FSR 3.1" and press "Install HelixSR ${active.version} here"`;
    return { color: GREY, title: "HelixSR isn't installed in this game", detail: `To install it, ${where} below.` };
  }
  // the install the game used last (newest log), else the first
  const i = [...installs].sort((a, b) => (b.check.mtime ?? 0) - (a.check.mtime ?? 0))[0];
  const v = i.version ? `HelixSR ${i.version}` : "HelixSR";
  const pick = SELECT_TEXT[i.how];
  const extra =
    active.ready && active.version && i.version && i.version !== active.version
      ? `This game has ${v}; ${active.version} is selected above. "Switch to HelixSR ${active.version}" below replaces it, no cleanup needed.`
      : undefined;
  const fresh = freshness(i.check, game.session);
  const u = i.check.last_upscale;
  if (i.check.status === "error") {
    return { color: RED, title: "Installed, but HelixSR can't upscale", detail: `${v} here has no built network (red frame in the game). Build HelixSR above, then install it here again.`, extra };
  }
  if (i.check.status === "running" && fresh !== "stale") {
    const when = fresh === "current" ? "in the current game session" : fresh === "last" ? "in the last game session" : "";
    return { color: GREEN, title: "✓ Working", detail: `${v} upscaled ${when}${u?.per_frame ? `: ${u.render} → ${u.output} (${u.mode})` : ""}.`, extra };
  }
  if (i.check.status === "running") {
    return { color: YELLOW, title: "Installed, but not used last time", detail: `${v} worked before, but not in the last game session. In the game, ${pick}.`, extra };
  }
  if (i.check.status === "loaded") {
    return { color: YELLOW, title: "Installed, waiting for the game", detail: `${v} was loaded, but the game didn't ask it to upscale. In the game, ${pick}.`, extra };
  }
  return {
    color: "#dcdedf",
    title: `${v} installed, not used yet`,
    detail: `Start the game, ${pick}, play a few seconds, then come back and press "Check again".`,
    extra,
  };
}

function GameSection({ appid, active }: { appid: string; active: Active }) {
  const [game, setGame] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useStoredFlag("details");

  const reload = useCallback(async () => {
    setLoading(true);
    setGame(await getGame(appid));
    setLoading(false);
  }, [appid]);

  useEffect(() => {
    setGame(null);
    reload();
  }, [reload]);

  if (!game) return <PanelSection title="Game Configuration"><Note>Scanning…</Note></PanelSection>;
  if (!game.ok) return <PanelSection title="Game Configuration"><Note>{game.error}</Note></PanelSection>;

  const removeBlock = game.running.length > 0 ? "running" : game.steam_busy;
  const guard: Guard = {
    remove: removeBlock,
    install: removeBlock || (game.anticheat.length > 0 && !game.anticheat_ack ? "anticheat" : null),
  };
  const relevant = game.direct.length > 0 || game.optiscaler.length > 0 || game.official_dlss.length > 0;
  const status = relevant ? gameStatus(game, active) : null;

  return (
    <>
      {status && (
        <PanelSection title={game.name}>
          <PanelSectionRow>
            <div style={{ ...small, color: "#dcdedf" }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: status.color, marginBottom: 2 }}>{status.title}</div>
              <div>{status.detail}</div>
              {status.extra && <div style={{ color: YELLOW, marginTop: 4 }}>{status.extra}</div>}
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" disabled={loading} onClick={reload}>
              {loading ? "Checking…" : "Check again"}
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField
              label="Show technical details"
              description="Logs, paths and OptiScaler settings."
              checked={details}
              onChange={setDetails}
            />
          </PanelSectionRow>
          {game.running.length > 0 && (
            <Note>
              <span style={{ color: YELLOW }}>
                The game is running ({game.running.find((n) => n.toLowerCase().includes(".exe")) ?? game.running[0]}).
                Installing, switching or removing HelixSR works after you quit it; the status above still updates.
              </span>
            </Note>
          )}
          {game.steam_busy && (
            <Note>
              <span style={{ color: "#e5a50a", fontWeight: 600 }}>{game.steam_busy}</span>
            </Note>
          )}
          {game.anticheat.length > 0 && (
            <>
              <Note>
                <span style={{ color: "#d94126", fontWeight: 600 }}>
                  This game ships anti-cheat ({game.anticheat.slice(0, 2).join(", ")}). Anti-cheat can flag changed game
                  DLLs, and online play could get your account banned. Only use HelixSR here for offline or single-player
                  play, at your own risk.
                </span>
              </Note>
              <PanelSectionRow>
                <ToggleField
                  label="I understand the risk"
                  description="Allows installing HelixSR in this game."
                  checked={game.anticheat_ack}
                  onChange={async (on) => {
                    await setAnticheatAck(game.appid, on);
                    reload();
                  }}
                />
              </PanelSectionRow>
            </>
          )}
        </PanelSection>
      )}
      {!relevant && (
        <PanelSection title={game.name}>
          <Note>
            No FSR 3.1 DLL (amd_fidelityfx_upscaler_dx12.dll / amd_fidelityfx_dx12.dll) and no OptiScaler.ini found in
            this game. Install OptiScaler for it first to use HelixSR in DLSS/XeSS/FSR 2 games (DirectX 12 only).
          </Note>
        </PanelSection>
      )}
      {game.official_dlss.length > 0 && (
        <Accordion
          id="official"
          title="Installed by HelixSR's setup"
          summary={`HelixSR ${game.official_dlss[0].helix_version ?? ""} as the game's DLSS (managed by HelixSR's setup)`}
        >
          {game.official_dlss.map((d) => (
            <div key={d.dir}>
              <Note>
                <div style={{ fontWeight: 600 }}>{d.rel === "." ? "Game folder" : d.rel}</div>
                <div>
                  HelixSR {d.helix_version ?? ""} as the game's DLSS (HelixSR's experimental route, without OptiScaler):
                  select DLSS in the game. The plugin leaves it to HelixSR's setup; to remove it, run helixsr-setup.sh
                  in Desktop Mode and answer r for this game. Don't use it in online games (ban risk).
                </div>
              </Note>
              <CheckBlock check={d.check} ini={{ exists: false, network_resolution: "auto", sharpening: "off", upscaler_dll: "", model_e_enabled: true, network_resolutions: [], sharpener: "off", sharpness: "0.5" }} session={game.session} details={details} />
            </div>
          ))}
        </Accordion>
      )}
      <DirectSection items={game.direct} active={active} guard={guard} session={game.session} details={details} reload={reload} />
      {game.optiscaler.length > 0 && (
        <Accordion id="optiscaler" title="OptiScaler" summary={optiSummary(game.optiscaler)}>
          {game.optiscaler.map((o) => (
            <OptiItem key={o.dir} o={o} active={active} appid={game.appid} guard={guard} session={game.session} details={details} reload={reload} />
          ))}
        </Accordion>
      )}
    </>
  );
}

// --- main panel --------------------------------------------------------------------------------------------------------

function Content() {
  const [helix, setHelix] = useState<HelixState | null>(null);
  const [games, setGames] = useState<GameSummary[] | null>(null);
  const [onlyCompatible, setOnlyCompatible] = useState(storage("onlyCompatible", "1") === "1");
  const [selected, setSelected] = useState<string>(storage("selected", ""));
  const [scanning, setScanning] = useState(false);

  const refreshHelix = useCallback(() => {
    getHelixState().then(setHelix);
  }, []);

  const scan = useCallback(async () => {
    setScanning(true);
    setGames(await listGames());
    setScanning(false);
  }, []);

  useEffect(() => {
    refreshHelix();
    scan();
    const l = addEventListener<[ok: boolean]>("setup_done", () => refreshHelix());
    return () => {
      removeEventListener("setup_done", l);
    };
  }, [refreshHelix, scan]);

  const shown = useMemo(
    () => (games ?? []).filter((g) => !onlyCompatible || g.fsr || g.optiscaler || g.helixsr),
    [games, onlyCompatible],
  );

  const pick = (appid: string) => {
    setSelected(appid);
    store("selected", appid);
  };

  const current = shown.find((g) => g.appid === selected);

  return (
    <>
      <HelixSection state={helix} refresh={refreshHelix} />
      <PanelSection title="Game Configuration">
        <PanelSectionRow>
          <ToggleField
            label="Only FSR 3.1 / OptiScaler games"
            checked={onlyCompatible}
            onChange={(v) => {
              setOnlyCompatible(v);
              store("onlyCompatible", v ? "1" : "0");
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          {games === null ? (
            <Field label="Scanning Steam libraries…" />
          ) : shown.length === 0 ? (
            <div style={small}>No matching games found.</div>
          ) : (
            <DropdownItem
              label="Game"
              rgOptions={shown.map((g) => ({
                data: g.appid,
                label: `${g.name}${g.helixsr ? "  ✓" : ""}`,
              }))}
              selectedOption={current?.appid}
              strDefaultLabel="Select a game"
              onChange={(o) => pick(o.data)}
            />
          )}
        </PanelSectionRow>
        {current && (
          <Note>
            {[current.fsr && "FSR 3.1", current.optiscaler && "OptiScaler", current.helixsr && "HelixSR installed"]
              .filter(Boolean)
              .join(" · ") || "No FSR 3.1 or OptiScaler found"}
          </Note>
        )}
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={scanning} onClick={scan}>
            {scanning ? "Scanning…" : "Rescan games"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      {current && (
        <GameSection
          key={current.appid}
          appid={current.appid}
          active={{
            ready: !!helix?.built,
            tag: helix?.active ?? null,
            version: helix?.version ?? null,
            kind: helix?.kind ?? null,
          }}
        />
      )}
    </>
  );
}

export default definePlugin(() => {
  const listener = addEventListener<[ok: boolean]>("setup_done", (ok) => {
    toaster.toast({
      title: "HelixSR setup",
      body: ok ? "Network built. HelixSR is ready to install." : "Setup failed. Open the plugin to see the log.",
    });
  });
  return {
    name: "HelixSR Manager",
    titleView: <div className={staticClasses.Title}>HelixSR Manager</div>,
    content: <Content />,
    icon: <FaDna />,
    onDismount() {
      removeEventListener("setup_done", listener);
    },
  };
});
