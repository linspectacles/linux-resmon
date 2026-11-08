# Resource Monitor 1.0.2

Resource Monitor remains usable standalone while retaining the GUI/TUI applet contracts needed for LinSpectacles integration. Version **1.0.0** is an identity-only migration from the frozen `0.0.11-exp2-r7` implementation: Resource Monitor behavior is unchanged.

- **Suite:** LinSpectacles - Linux Inspection Suite
- **Applet ID:** `linspectacles-linux-resmon`
- **Python package / extractable folder:** `linspectacles_linux_resmon/`
- **Organisation ID:** `linspectacles`
- **Organisation:** https://github.com/linspectacles/
- **Repository:** https://github.com/linspectacles/linux-resmon
- **Author / editor / publisher:** `brunonlinespace`

## 0.0.11-exp2-r2 — Network correctness and live-table stabilization

This revision keeps the proven exp2 Memory stabilization, exp2-r1 Network
Activity stabilization/counters, persistent column widths, and the r1-r1
standalone icon correction.

### Network taxonomy

The GUI Network views are now:

- **Processes with Network Sockets** — all presently observed process-owned
  TCP/UDP socket presence; columns are `Process Name | PID | TCP | UDP |
  Remote Endpoints | Sockets`.
- **Network Activity** — the existing per-interface byte counters and
  interval-rate deltas; its proven exp2-r1 implementation is preserved.
- **TCP Connections** — non-LISTEN TCP sockets with a reported remote peer.
- **UDP Endpoints** — UDP sockets with a reported remote/default peer. UDP is
  not described as connection-oriented.
- **Listening / Bound Ports** — TCP LISTEN sockets plus locally
  bound/unconnected UDP sockets.

The TUI receives matching terminology and a UDP Endpoints view while retaining
its established Network Activity V-toggle behavior.

### Additive privilege

Network privileged mode no longer replaces ordinary socket observations.

Every privileged socket refresh starts with the ordinary
`psutil.net_connections(kind="inet")` inventory. When the fixed helper is
active, helper `/proc/net/{tcp,tcp6,udp,udp6}` observations are reconciled
against that ordinary baseline:

- ordinary-visible sockets remain visible;
- helper-confirmed ordinary rows stay ordinary-coloured when no displayed field
  needed privileged help;
- helper ownership can enrich an otherwise unknown/restricted PID/process;
- helper-only sockets are added and shown with amber provenance.

The helper now returns the socket inode it already reads internally so helper
records have a stronger identity for reconciliation and selection.

Wildcard remote endpoints reported by `/proc/net/*` (`0.0.0.0:0` / `[::]:0`)
are normalized to "no remote peer" for classification. This specifically
prevents an unconnected UDP6 socket from disappearing from Listening / Bound
Ports merely because helper mode represented its absent remote peer as `::`.

**The packaged helper changed in r2 and must be installed/updated/repaired
through Options → Helper before r2 privileged Network inspection can be used.**

### Stable Network selection

Processes with Network Sockets, TCP Connections, UDP Endpoints and Listening /
Bound Ports now use stable process/socket identities during refresh. A selected
record is restored without assigning a Qt current index, and the user's
horizontal/vertical viewport is restored after selection. Network Activity
retains its already-proven exp2-r1 equivalent behavior.

### UI

- Inventory defaults are A → Z for the four Overview cards and the stabilized
  Memory/Network inventories.
- Column-width persistence from exp2-r1 is retained and includes UDP Endpoints.
- `Ctrl+/` opens Options.
- `Ctrl+L` toggles the Overview layout while unlocked.
- `Ctrl+Shift+L` toggles Lock Layout.
- User-facing Overview layout names are **Quadrants** and **Strips**; saved internal
  layout values remain backward compatible.
- Privilege/status prose moves from the top control row to the bottom status
  surface, following Kernel Ring Buffer behavior: neutral/transparent in normal
  visibility and amber (`#3a2d13` / `#f2d18b`) only while privileged access is
  active.
- The standalone taskbar/window icon fix from exp2-r1-r1 is retained.

### Preservation

Disk collection/refresh code is unchanged. The proven Memory selection
stabilization and Network Activity interface-counter/rate logic are unchanged.


## 0.0.11-exp2 — Memory-only live-table stabilization

This experiment changes **Memory → Processes only**.

The existing selected-PID behavior remains, but periodic refresh no longer
restores that PID with `QTableWidget.selectRow()`. Memory restores the PID via
`QItemSelectionModel` without assigning a current index, then restores the
user's vertical/horizontal viewport.

Expected result: a PID may stay selected while the user scrolls elsewhere, and
the one-second refresh must not pull that PID back into view.

Memory acquisition, smaps/smaps_rollup attribution and selected-process details
are unchanged.

**Disk protection:** Disk setup, process I/O, associated-file activity, device
counters, sysfs in-flight handling and `_refresh_disk()` are byte-for-byte
unchanged from `0.0.11-exp1-r2-r1`.


## 0.0.11-exp2-r1 — Network Activity stabilization + UI persistence

Builds on the proven Memory selection/viewport correction from exp2.

### Network Activity
- Interface identity, not physical row number, owns selection.
- Periodic refresh clears stale row/current-index state before rebuilding.
- A selected interface is restored through QItemSelectionModel without making it
  the current navigation index.
- Vertical and horizontal viewport positions are restored after selection.
- If no interface was selected, refresh does not invent a blue selection.
- Interface inventory defaults to A → Z by Interface name.
- Existing psutil.net_io_counters(pernic=True) byte counters and delta-rate
  calculations are unchanged.

### UI persistence
- User column widths are persisted in the existing linux_resmon.json settings.
- Widths are restored for the ResMon tables at startup.
- Writes are debounced while the user drags a header.
- Memory Processes and Network Activity explicitly default to A → Z on their
  primary identity columns.

### Protection
- Memory's proven exp2 fix is retained.
- CPU Services is not changed in this revision.
- Processes with Network Activity, TCP Connections and Listening Ports are not
  semantically changed yet.
- Disk setup, associated-file logic, sysfs in-flight logic and Disk refresh
  remain byte-for-byte unchanged from exp2 / exp1-r2-r1. Column-width
  persistence is generic presentation state only and does not participate in
  Disk acquisition or refresh calculations.


## 0.0.11-exp2-r1-r1 — standalone taskbar/window icon hotfix

This revision changes standalone application identity/icon setup only.

It copies the established Kernel Ring Buffer standalone behavior:

- sets QApplication application name to `Resource Monitor`;
- sets organization name to `brunonlinespace`;
- loads the packaged `icon.png` as the QApplication window icon;
- explicitly sets the same icon on the standalone QMainWindow.

No Resource Monitor collector, refresh, selection, sorting, privilege, TUI,
helper, Memory, Network, CPU or Disk behavior changes in this hotfix.


## 0.0.11-exp2-r2-r1 — startup hotfix

r2 accidentally dropped the `@staticmethod` decorator from `_endpoint()` while
the Network merge helpers were inserted. The first Network refresh therefore
bound `self` to a function that accepts only `(ip, port)`, causing a startup
`TypeError` and exit code 1.

r1 restores that decorator only.

The r2 Network taxonomy, additive privilege merge, UDP endpoint handling,
selection stabilization, Memory/Network Activity fixes, Disk implementation,
shortcuts, Quadrants/Strips UI, status-bar behavior, icon fix, TUI changes and
privileged helper are otherwise unchanged.

The packaged privileged helper is byte-for-byte identical to r2. If the r2
helper is already installed, no helper reinstall is required for r2-r1.


## 0.0.11-exp2-r3 — CPU Services + Disk Devices stabilization

### CPU → Services
- Stable selection identity is the exact systemd unit name.
- Refresh restores selection without assigning a current index, so a selected
  service cannot drag the viewport.
- GUI CPU accounting now reuses the existing ResMon TUI model:
  `systemctl show ... ControlGroup` → `/sys/fs/cgroup/<ControlGroup>/cpu.stat`
  → `usage_usec` deltas.
- CPU therefore represents the whole service cgroup rather than MainPID alone.
- MainPID remains visible and is only a CPU fallback if cgroup data is absent.
- Load / Active / Sub / Description are preserved.
- Services default A → Z.

### Disk → Disk Devices
- Stable selection identity is the exact device string.
- Refresh restores selection without current-index/viewport ownership.
- Disk Devices defaults A → Z.
- Disk acquisition/rate logic is unchanged. Process I/O, associated-file
  behavior, per-device counters, partitions, Busy %, IOPS and sysfs in-flight
  acquisition are preserved.
- Processes with Disk Activity and Disk Activity are untouched.

All stable Memory, Network Activity, additive Network privilege/taxonomy,
persistence, shortcut, Quadrants/Strips, status-bar and icon behavior is retained.
The privileged helper is unchanged; no helper reinstall is required if the
exp2-r2 helper is already installed.


## 0.0.11-exp2-r4 — final presentation-state + keyboard consolidation

### Presentation persistence
Resource Monitor now treats table presentation as first-class persistent state
across every current GUI table:

- manual column widths;
- selected sort column and ascending/descending direction;
- splitter proportions wherever a view contains multiple resizable panels.

This includes Overview cards, CPU Processes/Services/Handles/Modules, all Memory
tables, all three Disk tables, and all five Network tables. Old saved
`column_widths` values are migrated transparently; settings schema is now 3.

The persisted splitters are Overview Strips, CPU Processes ↕ Associated Details,
Handles ↔ Modules, Memory Processes ↕ Selected Process, Memory Summary ↔ Memory
Map, Physical Memory Summary ↕ Details, and Memory Classes ↔ VM Activity.

### Keyboard selection
The stable mouse-selection architecture is retained. Up/Down keyboard navigation
now uses the currently selected visible row as its anchor even after a live
refresh deliberately cleared Qt's current index. The keyboard action itself may
scroll the newly selected row into view; subsequent automatic refreshes do not.

The three tables already proven correct keep their native keyboard path unchanged:
**CPU Processes**, **Processes with Disk Activity**, and **Disk Activity**.

### Layout terminology correction
The final user-facing Overview layout names are **Quadrants** and **Strips**.
`Quadrants` remains the 2×2 arrangement. The former user-facing `Lines` label is
renamed `Strips`; the existing internal `lines` value is retained for backward
compatibility with saved settings.

No resource collector, rate formula, privilege operation, helper protocol, TUI
collector, or protected Disk acquisition logic changes in r4.


## 0.0.11-exp2-r5 — last-column fill + exact Sources styling

- Every table keeps persisted user-preferred column widths.
- The right-most visible column expands only when needed to consume otherwise unused viewport width.
- Automatic fill never overwrites the stored preferred width; when space becomes tight, the last column contracts only to its preferred width and horizontal scrolling takes over after that.
- If visible column order changes, the newly right-most visible column becomes the fill column and a formerly expanded column returns to its persisted preferred width.
- Sources now copies the actual Journal Inspector 0.0.4-r1 Sources canvas composition and styling: `#151719` background, `#333333` border, `#dcdcdc` values, bold `#9cdcfe` top-level source headings, and the same heading/note/layout treatment.
- Sources documentation is synchronized with the already-current CPU Services cgroup source and privileged `/proc/net/*` socket sources.
- No Resource Monitor collector, rate calculation, selection, keyboard-navigation, splitter behavior, privilege helper, TUI, or trusted Disk acquisition behavior changes in r5.

## 0.0.11-exp2-r6 — Overview Provider Architecture

This is an isolated Overview architecture experiment built directly on the
successful `0.0.11-exp2-r5` fallback.

### Overview no longer re-implements resource measurements

The four Overview cards remain structural CPU / Memory / Disk / Network slots,
but each card now mirrors one **canonical full-tab view**. Overview itself no
longer recalculates CPU, memory, disk or network rows.

The selected full-tab refresh path remains the one authoritative implementation;
Overview copies its resulting rows into a separate presentation table. This means
future fixes to the canonical full-tab data/identity/provenance path naturally
flow into Overview without maintaining another measurement implementation.

Overview presentation state remains independent: its own filter, sort, selection,
scroll position, column widths/order and last-visible-column fill behavior are
still separate from the full tab.

### Options → Appearance owns Overview content

There are no content selectors on the cards. The four choices live under
**Options... → Appearance → Overview Content** and persist across launches.

Eligible self-contained views:

- CPU: `CPU Processes`, `CPU Services`
- Memory: `Memory Processes`, `Physical Memory`
- Disk: `Processes with Disk Activity`, `Disk Activity`, `Disk Devices`
- Network: `Processes with Network Sockets`, `Network Activity`,
  `TCP Connections`, `UDP Endpoints`, `Listening / Bound Ports`

Dependent/deep mini-panes are deliberately excluded. Overview therefore does not
offer CPU Handles/Modules, selected-process Memory Summary/Memory Map, Linux
Memory Classes, or Virtual Memory Activity as independent card choices.

The visible card title is exactly the selected Appearance dropdown title.

Default choices are CPU Processes, Memory Processes, Processes with Disk Activity,
and Processes with Network Sockets.

### Preservation

The r5 canonical CPU, Memory, Disk and Network refresh/acquisition methods are
unchanged. The r5 persistence, keyboard-navigation stabilization, preferred-width
plus last-visible-column fill behavior, exact Journal-style Sources UI, privilege
behavior, helper, TUI, taskbar icon, and protected Disk implementation remain the
fallback authority.

Settings schema is now 5 to persist `overview_content`; existing r5 layout,
column-width, sort and splitter settings remain compatible.

The privileged helper is unchanged from exp2-r2; no helper reinstall is required.


## 0.0.11-exp2-r7 — Overview first-use defaults / one-line polish

Built directly on the r6 Overview Provider Architecture. r5 remains the known
fallback line.

### First-use Overview defaults

With no existing `linux_resmon.json`:

- layout: **Stripes**
- card order: **CPU → Disk → Network → Memory**
- CPU card: **CPU Processes**
- Disk card: **Disk Activity**
- Network card: **TCP Connections**
- Memory card: **Memory Processes**
- main tab order: **Overview → CPU → Memory → Disk → Network**

Options → Appearance lists the Overview Content selectors in the same
CPU → Disk → Network → Memory order.

The internal saved layout value remains `lines` for compatibility, but the
user-facing name is now **Stripes** (alongside **Quadrants**).

### Table presentation

GUI table cells are explicitly single-line (`wordWrap=False`) with right-side
elision for text that does not fit.

On first use, each Overview provider table starts with equally distributed
preferred column widths once that provider becomes visible. The existing
preferred-width model then applies normally:

- the final visible column absorbs any spare width to the edge of the widget;
- automatic fill never overwrites user-preferred widths;
- user resizing persists normally;
- changing provider/column order keeps the r5/r6 last-visible-column behavior.

Full-tab first-use widths are not redefined by this experiment; the equal
first-use rule is deliberately scoped to Overview cards.

### Preservation

The r6 canonical-provider architecture is retained. Canonical CPU, Memory,
Disk, and Network acquisition/refresh methods are unchanged. r6 privilege,
selection, persistence, Sources styling, helper, TUI, and taskbar behavior are
retained.


## GUI

0.0.11-exp1 continues to use the user-supplied pre-rebrand 0.0.1-exp6 Resource Monitor as the GUI behavioral reference. The proven exp6/v23 CPU process sampling model remains in place: persistent `psutil.Process` objects, one-time CPU counter priming, active-process-only default display, in-place table updates, and scroll/sort preservation.

The GUI navigation remains one row:

- **Overview** — CPU, Memory, Disk and Network activity cards with persistent **Quadrants / Strips** presentation. Strips uses **Up / Down** movement; Quadrants adds **Left / Right** movement. Edge-invalid moves disable automatically, and all movement is disabled when **Lock Layout** is enabled.
- **CPU** — dynamic View dropdown: **Processes**, **Services**. The **Processes** screen keeps **Associated Handles** and **Associated Modules** visible beneath the process table; both follow the selected process.
- **Memory** — dynamic View dropdown: **Processes**, **Physical Memory**. **Processes** keeps the live process inventory and adds lazy selected-process Linux memory attribution plus `/proc/<pid>/smaps` mappings; **Physical Memory** deepens the former compact summary into Linux RAM classes and `/proc/vmstat` activity without duplicating NUMA/topology work reserved for Hardware Inspector.
- **Disk** — **Processes with Disk Activity**, **Disk Activity**, **Disk Devices**.
  - **Disk Activity** shows visible open/mapped files associated with processes currently producing disk I/O and labels its I/O rate as the process aggregate rather than pretending Linux exposes a per-file byte rate.
  - **Disk Devices** is the live device-level view: device, mount, filesystem, read/write rates, IOPS, busy %, in-flight I/O and current filesystem space used. Deeper storage structure/configuration remains the job of LinSpectacles' Storage Inspector.
- **Network** — **Processes with Network Activity**, **Network Activity**, **TCP Connections**, **Listening Ports**.

The five main tabs (**Overview / CPU / Memory / Disk / Network**) are user-movable while **Lock Layout** is off. Their visual order, the Overview card order, Overview Quadrants/Strips mode, and Lock Layout state persist between launches in:

```text
~/.config/brunonlinespace/linspectacles/linux_resmon.json
```

When `XDG_CONFIG_HOME` is set, that directory is used instead of `~/.config`.

There are no nested/double tabs and no process-filter popups. CPU, Memory, Disk and Network remember their View selection while the app is running. CPU → Processes keeps Handles/Modules attached to process context; Memory → Processes similarly keeps the VMMap-style memory summary/mappings attached to the selected process rather than making them a third top-level Memory view.

## Options

The GUI uses the standard LinSpectacles **Options...** treatment with tabs:

- **Appearance** — first tab. Selects **Overview layout: Quadrants / Strips** and provides **Lock Layout** (off by default). When unlocked, Overview cards can be moved with their contextual controls and the main Resource Monitor tabs can be dragged; both arrangements persist. Lock Layout freezes both.
- **Helper** — shows the fixed optional helper status and provides **Install or Update/Repair Helper...** and **Remove Helper...**. PolicyKit is used only for the fixed system helper operation; the GUI itself is never elevated.
- **Sources** — documents the read-only psutil, `/proc`, `/sys`, `systemctl`, and optional helper data sources used by the monitor.
- **About** — standard LinSpectacles applet identity/version/license information.

There is no Export tab in Resource Monitor Options.

## TUI

The TUI changes only its Memory area to remain parallel with the GUI: **Memory** is one selectable resource row and `V` toggles **Processes / Physical Memory**. In Processes mode `[` / `]` (or `<` / `>`) changes the selected PID and the right pane includes lazy selected-process memory attribution/mappings. Physical Memory reports the same Linux memory classes and VM-activity counters/rates as the GUI. CPU, Disk, Network and their existing controls are otherwise unchanged.

## Safe optional privilege

Privileged mode is **off by default**. Neither GUI nor TUI runs as root. The optional fixed-path root-owned helper remains limited to read-only process handles, mapped modules/files, selected-process `smaps_rollup`/`smaps`, and system socket visibility. It exposes no arbitrary command execution or arbitrary-file read API. In the GUI, the Privileged button turns amber while active and rows actually sourced through the helper use the same amber provenance accent and tooltip; ordinary data keeps the normal theme. Helper installation/repair/removal is available from **Options... → Helper**; the bundled `privileged/install-helper.sh` remains available as a command-line fallback. See `PRIVILEGED.md`.

## Standalone

From inside the extracted `linspectacles_linux_resmon/` folder:

GUI:

```bash
python3 standalone.py
```

TUI:

```bash
python3 standalone_tui.py
```

### Overview layout correction (r2-r1)

When layout is unlocked, unavailable edge moves are visibly disabled. When **Lock Layout** is enabled, Overview positioning buttons are hidden completely; unlocking restores them with the correct Quadrants/Strips edge state.
