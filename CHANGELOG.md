## 1.0.2

- About slogan corrected to the LinSpectacles family slogan: **Expose. Explore. Explain.**
- No other implementation change.

## 1.0.1

- Titlebar only: standalone GUI now shows `Resource Monitor 1.0.1 — LinSpectacles Applet`.
- No other code or behavior changes.

## 1.0.0

- Identity/branding migration only from the frozen `0.0.11-exp2-r7` Resource Monitor source.
- Visible suite branding is now **LinSpectacles - Linux Inspection Suite**.
- Applet ID is now `linspectacles-linux-resmon`.
- Extractable/source Python package folder is now `linspectacles_linux_resmon/`.
- Adds organisation metadata: technical organisation ID `linspectacles`, organisation URL `https://github.com/linspectacles/`, repository `https://github.com/linspectacles/linux-resmon`, and retains `brunonlinespace` as author/editor/publisher.
- Replaces the old Resource Monitor icon with the current mandatory LinSpectacles family logo.
- Renames the privileged helper payload/install identity to `linspectacles-linux-resmon-helper`; helper protocol, operations, trust checks and privilege scope are unchanged.
- Moves the active settings namespace to `~/.config/brunonlinespace/linspectacles/linux_resmon.json` while reading the legacy pre-rebrand settings file when the new file does not yet exist, preserving user presentation state across the identity migration.
- GUI/TUI collectors, refresh/rate logic, Overview, CPU/Memory/Disk/Network behavior, sorting/filtering/selection, persistence semantics, privilege behavior and helper protocol are otherwise unchanged.

## 0.0.11-exp2-r7

- First-use Overview layout defaults to **Stripes** (internal persisted value remains `lines` for compatibility).
- First-use Overview card order is **CPU → Disk → Network → Memory**.
- First-use Overview providers are CPU Processes, Disk Activity, TCP Connections, and Memory Processes.
- Options → Appearance lists Overview Content selectors in CPU → Disk → Network → Memory order.
- Main default tab order remains Overview → CPU → Memory → Disk → Network.
- GUI tables explicitly disable text wrapping; narrow cells remain one line and elide to the right.
- Overview provider tables with no saved widths start with equal preferred widths when first shown; the last visible column absorbs any remaining viewport width.
- User-resized preferred widths continue to persist and are not overwritten by automatic fill.
- r6 canonical provider architecture and all canonical CPU/Memory/Disk/Network data methods are retained.
- Helper/TUI/privilege contract unchanged.

## 0.0.11-exp2-r6

- Adds the Overview Provider Architecture on top of the successful exp2-r5 fallback.
- Removes the four bespoke Overview measurement implementations; each Overview card now mirrors a selected canonical full-tab table after running that tab's existing refresh path.
- Adds persistent Options → Appearance → Overview Content selectors.
- CPU choices: CPU Processes / CPU Services.
- Memory choices: Memory Processes / Physical Memory.
- Disk choices: Processes with Disk Activity / Disk Activity / Disk Devices.
- Network choices: Processes with Network Sockets / Network Activity / TCP Connections / UDP Endpoints / Listening / Bound Ports.
- Dependent mini-panes are intentionally excluded from Overview choices: CPU Handles/Modules, selected-process Memory detail tables, Linux Memory Classes and Virtual Memory Activity.
- Each card title inherits the exact selected Overview Content title.
- Overview retains independent presentation state (filter/sort/selection/scroll/column widths) while data semantics come from the canonical full-tab implementation.
- Settings schema becomes 5 and adds `overview_content`; r5 presentation settings remain compatible.
- All canonical r5 resource refresh/acquisition methods, persistence/keyboard logic, last-column fill, Journal-style Sources UI, helper/TUI/support files and privilege behavior are preserved.
- Privileged helper is unchanged; no reinstall is required.

## 0.0.11-exp2-r5

- Added preferred-width + last-visible-column fill behavior to every GUI table without surrendering persisted user widths to QHeaderView Stretch mode.
- Copied Journal Inspector 0.0.4-r1 Sources dialog canvas styling/formatting exactly, adapting only Resource Monitor source text/font accessor.
- Corrected Sources documentation for the current systemd ControlGroup/cpu.stat CPU source and helper `/proc/net/{tcp,tcp6,udp,udp6}` network sources.
- All collectors/rates, keyboard stabilization, splitter persistence, helper/TUI/support and trusted Disk behavior are unchanged from r4.

## 0.0.11-exp2-r4

- Final presentation-state/keyboard consolidation.
- Persists manual column widths for every current GUI table.
- Persists each table's active sort column and ascending/descending direction.
- Persists all resizable multi-panel splitter proportions, including Overview Strips, CPU associated panels, Memory selected-process panels and Physical Memory panels.
- Fixes Up/Down keyboard navigation after live refresh by anchoring movement to the selected visible row rather than Qt's cleared current index.
- CPU Processes, Processes with Disk Activity and Disk Activity retain their already-good native keyboard behavior unchanged.
- Corrects Overview terminology: **Quadrants** remains Quadrants; former **Lines** is now **Strips**. Internal saved values remain backward compatible.
- No collector, rate, privilege, helper, TUI or Disk acquisition logic changes.

## 0.0.11-exp2-r3

- CPU Services: stable selection keyed by systemd unit.
- CPU Services: whole-service CPU now comes from systemd ControlGroup `cpu.stat` (`usage_usec`) when available, matching the existing TUI implementation; MainPID remains context/fallback.
- CPU Services retains Load / Active / Sub / Description and adds CPU %.
- Disk Devices: stable selection keyed by exact device; selected device no longer owns the viewport.
- Services and Disk Devices default A → Z.
- Disk acquisition/rate logic is unchanged; Processes with Disk Activity and Disk Activity are untouched.
- All exp2-r2-r1 Memory, Network, persistence, shortcut, status, icon, TUI and helper behavior is retained.
- Privileged helper is unchanged; no reinstall is required if the exp2-r2 helper is already installed.

## 0.0.11-exp2-r2-r1

- Startup hotfix only: restores the accidentally removed `@staticmethod` decorator on `_endpoint()`.
- Fixes the immediate Network-refresh `TypeError` that caused r2 standalone launch to exit with code 1.
- No Network semantics, counters, privilege merge, selection behavior, Memory, Disk, CPU, TUI, helper or icon behavior changed.
- Privileged helper is byte-for-byte unchanged from r2; no helper reinstall is required if the r2 helper is already installed.

## 0.0.11-exp2-r2

- Renames Processes with Network Activity to **Processes with Network Sockets** and `Connections` to `Sockets`.
- Adds **UDP Endpoints** without describing UDP as connection-oriented.
- Renames Listening Ports to **Listening / Bound Ports**.
- Makes privileged Network visibility additive: ordinary-visible sockets cannot disappear when privilege is enabled; helper-only/ownership-enriched rows are additive amber provenance.
- Normalizes `/proc/net/*` wildcard remote endpoints (`0.0.0.0:0` / `[::]:0`) as no remote peer for TCP/UDP classification.
- Privileged helper `net_connections` now retains the reported socket inode; helper version/hash are updated and the helper must be updated/repaired for r2 privilege.
- Stabilizes selection/viewport for Processes with Network Sockets, TCP Connections, UDP Endpoints and Listening / Bound Ports.
- Preserves the already-stable Network Activity interface counters and selection behavior.
- Adds A → Z default ordering to Overview-card inventories and stabilized Network inventories.
- Adds Ctrl+/ = Options, Ctrl+L = toggle Overview layout, Ctrl+Shift+L = toggle Lock Layout.
- User-facing Overview layout labels are now Lines / Strips.
- Moves privilege/status prose to the bottom Kernel Ring Buffer-style status surface.
- Retains persistent column widths and adds UDP Endpoints to width persistence.
- Retains the exp2-r1-r1 standalone icon correction.
- Disk collection/refresh code and the proven Memory stabilization are unchanged.
- TUI receives additive Network privilege, the revised Network terminology and UDP Endpoints while retaining its approved Network Activity toggle.

## 0.0.11-exp2-r1-r1

- Standalone icon/application-identity hotfix only.
- Copies Kernel Ring Buffer's established standalone icon behavior: application name, organization name, QApplication icon and QMainWindow icon.
- The packaged 256×256 `icon.png` is unchanged.
- No Resource Monitor data acquisition, refresh, selection, privilege, helper, TUI, CPU, Memory, Disk or Network behavior changed.

## 0.0.11-exp2-r1

- Retains the stable exp2 Memory PID-selection / viewport behavior.
- Stabilizes Network Activity selection by persistent interface identity.
- Network Activity no longer lets one-second refresh move the blue selection to a different interface or pull the viewport to the selected interface.
- Network Activity default inventory order is Interface A → Z.
- Memory Processes explicitly defaults to Process Name A → Z.
- Adds persistent user column widths across Resource Monitor tables via the existing JSON settings file.
- Existing Network Activity counters/rate calculations are unchanged.
- CPU Services and the remaining Network views are unchanged.
- Disk setup and Disk acquisition/refresh methods remain byte-for-byte unchanged.

## 0.0.11-exp2

- Memory → Processes only: preserve selected PID without letting periodic refresh force the viewport back to that process.
- Programmatic Memory selection now uses QItemSelectionModel without assigning a current index.
- Memory restores vertical/horizontal viewport position after selection restoration.
- Memory filtering uses the same non-scrolling selection mechanism.
- No Memory data collection, smaps/smaps_rollup, selected-process detail, CPU, Services, Network, helper, TUI or launcher behavior changed.
- Disk setup and Disk collection/refresh methods are byte-for-byte unchanged from 0.0.11-exp1-r2-r1.

## 0.0.11-exp1-r2-r1

- Overview movement buttons now show an explicit disabled visual treatment when a move is impossible at the current edge.
- Lock Layout now removes all Overview positioning buttons from the cards; unlocking restores the controls appropriate to Lines or Quadrants with edge-aware disabled states.
- No TUI, helper, privilege, CPU, Memory, Disk, Network, launcher, or shared-support behavior changed from 0.0.11-exp1-r2.

# Changelog

## 0.0.11-exp1-r2

- Keeps the working 0.0.11-exp1-r1 RAMMap/VMMap memory/helper behavior intact and focuses on GUI Overview/layout configurability.
- Adds **Options... → Appearance** as the first Options tab; Options are now exactly **Appearance | Helper | Sources | About**.
- Appearance adds persistent **Overview layout: Lines / Quadrants**. Lines retains the vertical Overview-card model; Quadrants places CPU, Memory, Disk and Network activity into a persistent 2×2 arrangement.
- Overview cards retain **Up / Down** movement; **Left / Right** controls appear only in Quadrants. Movement controls disable automatically when the card has reached the relevant edge.
- Adds **Lock Layout**, default off. When locked, Overview movement controls are disabled, Overview layout selection is frozen, and the main Overview/CPU/Memory/Disk/Network tab bar is no longer movable. Unlocking restores both forms of rearrangement.
- Persists Overview layout mode, Overview card order, Lock Layout state and existing main-tab order in the same `linux_resmon.json` settings file.
- Adds an Appearance note explaining that both Overview cards and Resource Monitor tabs are rearrangeable while unlocked.
- Corrects the unavailable-helper route for the new Options order so it opens the **Helper** tab rather than Appearance.
- TUI code, CPU/Memory/Disk/Network collectors, privilege client, helper payload/protocol, helper installer and shared support are unchanged from 0.0.11-exp1-r1.

## 0.0.11-exp1-r1

- Keeps `0.0.11-exp1` as the memory experiment and makes a focused privilege/presentation correction.
- Physical Memory now uses an adjustable vertical splitter between **Physical Memory Summary** and the lower **Linux Memory Classes / Virtual Memory Activity** pair; the lower pair remains horizontally adjustable.
- Extends the fixed read-only helper with two PID-scoped operations for selected-process `smaps_rollup` and `smaps`; there is still no arbitrary-file-read API. Ordinary access is always tried first and helper access is used only when ordinary selected-process memory inspection is restricted and Privileged is active.
- Helper-derived selected-process Memory Summary rows and Memory Map rows use the SELinux-aligned amber provenance palette; ordinary rows remain ordinary. Raw `Errno 13` presentation is replaced by a clear Restricted message when access is denied.
- Aligns Resource Monitor's **Privileged: On** button with the established SELinux top-level active privilege styling.
- Enriches the applet helper contract with explicit Standard access vs With helper descriptions, including selected-process memory, so Configuration → Helpers can explain the actual privilege expansion instead of showing Not described.
- TUI selected-process Memory uses the same ordinary-first/helper-fallback semantics; unrelated TUI code and behavior are unchanged.
- Because the helper payload changes, users with the older helper installed must use **Options... → Helper → Install or Update/Repair Helper...** (or the central Helpers manager) before the new privileged memory operations are available.

## 0.0.11-exp1

- Experimental Memory-only deepening on top of 0.0.10-r1; CPU, Disk, Network, Overview, helper protocol/management and Suite lifecycle are intentionally unchanged.
- Restores the GUI Memory **View** dropdown with exactly **Processes / Physical Memory**.
- Memory → Processes keeps the live process inventory and adds a selected-process **Memory Summary** plus **Memory Map** parsed lazily from `/proc/<pid>/smaps_rollup` and `/proc/<pid>/smaps`; detailed smaps is never scanned across all processes.
- The selected-process mapping inventory reports address range, permissions, RSS, PSS, private, shared, swap and mapping/path using Linux-native semantics.
- Memory → Physical Memory expands the former compact summary into RAM summary, Linux `/proc/meminfo` memory classes, and `/proc/vmstat` activity counters with per-second deltas derived only between active samples.
- Deliberately excludes NUMA/PCI/IOMMU topology from ResMon; that remains future Hardware Inspector scope.
- TUI Memory is revised in parallel: one Memory row with `V` toggling **Processes / Physical Memory**; Processes adds selected-PID memory details/mappings while Physical Memory mirrors the new Linux RAM/VM activity model.
- TUI CPU, Disk, Network, privilege controls and helper implementation are not changed.

## 0.0.10-r1

- Adds the standard GUI **Options...** surface with tabs exactly **Helper | Sources | About**.
- Helper tab provides **Install or Update/Repair Helper...** and **Remove Helper...**, fixed-path PolicyKit management, and packaged-vs-installed helper integrity checking.
- Exports the GUI `create_applet` factory from the package root for Linspector exp9-r5 modular loading.
- Hosted GUI deactivation now ends any active/pending privileged helper session.
- A timed-out helper request invalidates the helper session to prevent stale-response protocol desynchronisation.
- The privileged helper executable/protocol remains unchanged.
- TUI source files are unchanged.

## 0.0.10

- Simplifies the GUI Memory tab: **Physical Memory** is now a compact always-visible summary above **Processes**, so Memory no longer shows a redundant View dropdown. CPU, Disk and Network dropdown behavior is unchanged.
- Keeps privilege in-place rather than opening a duplicate privileged Resource Monitor window. The application itself still never runs as root.
- Gives active GUI privileged mode a distinctive amber button/status treatment. Returning to normal mode restores the ordinary theme immediately.
- Marks rows actually sourced through the privileged helper with the same amber provenance accent and a tooltip. This applies to CPU Associated Handles/Modules, privileged Disk Activity file associations, and privileged network ownership/connection rows. Ordinary data remains normally coloured even while privileged mode is active.
- Does not widen the helper protocol or privilege scope; `privilege.py`, the root-owned helper, install mechanism and TUI privilege model remain unchanged.
- Preserves the exp6-derived CPU collector/refresh behavior, movable/persistent GUI tab order, movable Overview cards, Disk Devices semantics, and standalone lifecycle.

## 0.0.9

- Renames the internal applet/package identity from the former Resource Monitor identifier to **`linux_resmon`**. The distributable ZIP now extracts to exactly `linux_resmon/`, the manifest ID is `linux_resmon`, and the GUI standalone imports `linux_resmon.applet`.
- Makes the five GUI resource tabs **user-movable** and persists their order across launches. Refresh/navigation dispatch now uses stable resource identities rather than numeric tab positions, so reordering cannot cross-wire resource collectors.
- Stores GUI tab order in `~/.config/brunonlinespace/linspector/linux_resmon.json`, respecting `XDG_CONFIG_HOME` when present. Corrupt/missing settings safely fall back to the default order.
- Renames Disk **Storage** to **Disk Devices**.
- Aligns the GUI Disk views with the agreed semantics: **Disk Activity** shows visible open/mapped files associated with disk-active processes and explicitly uses the process aggregate I/O rate; **Disk Devices** shows live device/mount read/write rates, IOPS, busy %, in-flight I/O and filesystem space used.
- Renames the matching TUI leaf/view to **Disk Devices** without changing its underlying collector behavior.
- Preserves the exp6-derived GUI CPU sampling/refresh behavior, Overview card implementation, CPU Handles/Modules relationship, safe privilege scope, and standalone lifecycle.

## 0.0.8

- Corrects the 0.0.7 CPU navigation mistake: the CPU View dropdown is now only **Processes / Services**.
- Moves **Associated Handles** and **Associated Modules** back onto the **CPU → Processes** screen, where they belong as contextual details of the selected process.
- CPU → Processes uses a resizable vertical split: the exp6-derived process table remains on top, with Handles and Modules in a resizable side-by-side lower split.
- Selecting a CPU process drives both contextual panels; with no selection they remain empty and show a clear selection prompt.
- Handles/Modules refresh live while CPU → Processes is visible, including optional expanded visibility through the existing safe privilege helper.
- Does not change the exp6-derived CPU sampling/refresh implementation.
- Memory, Disk and Network dropdowns are unchanged from 0.0.7.
- Overview, TUI, standalone launchers and privilege implementation are unchanged from 0.0.7.

## 0.0.7

- Restores the exp6-style **Overview** GUI tab with movable CPU, Memory, Disk and Network cards and their familiar Up/Down controls.
- Replaces the multi-frame detailed GUI tabs with a single full-size view selected by one dynamic `View` dropdown per main resource tab.
- CPU dropdown is **Processes / Associated Handles / Associated Modules / Services**; Handles and Modules use the process selected in CPU → Processes.
- Memory dropdown is **Processes / Physical Memory**.
- Disk dropdown is **Processes with Disk Activity / Disk Activity / Storage**.
- Network dropdown is **Processes with Network Activity / Network Activity / TCP Connections / Listening Ports**.
- Keeps the known-good exp6/v23 CPU Processes collector/refresh behavior. A selected CPU process remains available for Handles/Modules context even during a 0% CPU sample.
- Adds no new process-filter popups or nested tabs.
- Retains the 0.0.6 safe optional privilege helper and detailed TUI without widening privilege scope.

## 0.0.6

- Restored GUI CPU process sampling/refresh behavior from the user-supplied, last-known-working Linspector 0.0.1-exp6 Resource Monitor (linux-resmon v23 lineage).
- Restored the five-column CPU process table, active-process-only default view, persistent psutil process cache, in-place cell updates, and scroll/sort preservation.
- Kept the newer Services, Associated Handles and Associated Modules panels and safe optional privilege helper.
- Hardened standalone lifecycle/shutdown and packages both GUI/TUI standalone launchers executable.
- Retained the 0.0.5 detailed 13-view TUI unchanged except for version/package documentation.

## 0.0.5

- Corrects the incomplete 0.0.4 TUI implementation and implements the agreed 13-section Resource Monitor hierarchy.
- Keeps all hierarchy rows selectable without requiring changes to the existing Linspector host by rendering each group together with its first selectable child.
- CPU TUI now provides Processes, systemd Services with sampled cgroup CPU, Associated Handles (FD/type/flags/target) and Associated Modules.
- Adds host-safe `[` / `]` process selection; Handles and Modules follow the selected CPU PID.
- Memory TUI now provides Major Faults/s, RSS, PSS, USS, Shared and Swap plus Linux-native Physical Memory/commit metrics from `/proc/meminfo`.
- Disk TUI now separates Processes with Disk Activity, honest file associations for Disk Activity, and Storage with rates, IOPS, busy %, in-flight I/O and space.
- Network TUI now separates Processes with Network Activity, Network Activity, TCP Connections and Listening Ports.
- Preserves the approved 0.0.3 `V` behavior inside Network Activity as Connections/Interfaces, with exact interface byte-rate deltas.
- Retains the 0.0.4 safe optional `P` privileged-mode helper unchanged: GUI/TUI never run as root and the helper remains fixed-protocol/read-only.
- GUI behavior from 0.0.4 is otherwise unchanged.

## 0.0.4

- Rebased from the supplied Linspector GUI Resource Monitor 0.0.2 and approved TUI Resource Monitor 0.0.3.
- Removed the GUI Overview tab and moved the GUI to four top-level CPU / Memory / Disk / Network views.
- Added Windows Resource Monitor-inspired Linux-native GUI panels:
  - CPU: Processes, Services, Associated Handles, Associated Modules.
  - Memory: Processes, Physical Memory.
  - Disk: Processes with Disk Activity, Disk Activity, Storage.
  - Network: Processes with Network Activity, Network Activity, TCP Connections, Listening Ports.
- Preserved the TUI 0.0.3 left-pane CPU / Memory / Disk / Network baseline and Network `V` toggle.
- Added explicit TUI `P` privileged-mode toggle without changing the four-row navigation model.
- Added optional privileged read-only visibility. It is disabled by default; the GUI/TUI is never elevated.
- Added a fixed-path root-owned helper trust check and polkit/pkexec authorization. The helper exposes no arbitrary command or arbitrary-file API.
- Kept both GUI and TUI applet entrypoints in one source tree to preserve a clean future Linspector re-coupling path.
