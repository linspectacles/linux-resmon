# Optional privileged data collection

Resource Monitor is fully usable without administrator privileges. Privileged mode is **off by default** and exists only to improve visibility into process handles/modules and system-wide socket ownership that Linux may hide from an ordinary user.

The application itself is never elevated. Instead it can talk to a dedicated read-only helper installed at:

`/usr/libexec/linspectacles-linux-resmon-helper`

Resource Monitor refuses to use that helper unless it is a regular file owned by root, executable, and not writable by group or other users. Authorization is requested through `pkexec`/polkit. Resource Monitor never receives or stores the user's password.

The helper accepts only five fixed read-only requests: process file-descriptor targets, process mapped-file/module paths, selected-process `smaps_rollup`, selected-process `smaps`, and system socket data. The two memory requests accept only a validated PID and read only those fixed `/proc/<pid>/` files. There is no arbitrary shell-command or arbitrary-file-read request.

## GUI provenance

Privileged access stays inside the existing Resource Monitor window; it does not open a second privileged copy of the applet. When authorization is active, the GUI Privileged control uses the same amber/gold active-button treatment as SELinux Inspector. Only table rows whose visibility was actually supplied by the privileged helper receive the aligned amber provenance colour and tooltip. Data collected normally remains in the ordinary theme, even while privileged mode is active.

## Helper management

In the GUI, open **Options... → Helper**. The Helper tab reports whether the fixed installed helper matches the helper packaged with this Resource Monitor revision and provides:

- **Install or Update/Repair Helper...**
- **Remove Helper...**

Both actions use PolicyKit only for the fixed `/usr/libexec/linspectacles-linux-resmon-helper` path. Installing/updating copies the packaged helper as a root-owned executable and then verifies its integrity against the applet manifest. Removing it does not affect ordinary Resource Monitor operation.

The bundled script remains available as a command-line fallback. From this applet folder, run as your normal user:

```bash
./privileged/install-helper.sh
```

The script uses `pkexec` only for `/usr/bin/install` of the fixed helper into the fixed system path. To remove it:

```bash
./privileged/install-helper.sh --uninstall
```

Installing the helper is optional. If it is absent or does not match the packaged helper, the Privileged control remains off and the GUI routes helper management through **Options... → Helper**. Resource Monitor continues in normal unprivileged mode. A hosted GUI deactivation ends any active/pending helper session; a timed-out helper request invalidates the session rather than leaving a late response queued for the next request.


## Network privilege in 0.0.11-exp2-r2

Network privilege is **additive**. Resource Monitor always keeps the ordinary
socket observations it can already see and then reconciles helper observations
on top of them. Enabling privilege must not make an ordinary-visible socket
disappear.

The helper's fixed `net_connections` operation reads only:

- `/proc/net/tcp`
- `/proc/net/tcp6`
- `/proc/net/udp`
- `/proc/net/udp6`
- `/proc/<pid>/fd` symlink targets for socket-inode ownership

The operation now includes the `/proc/net/*` socket inode in its returned
structured row. This is an additive protocol-v1 field used for stronger
reconciliation/selection identity; it does not add an arbitrary file-read or
command-execution capability.

Ordinary rows remain normal-coloured when the helper merely confirms them.
Rows visible only through the helper, or rows whose displayed ownership was
actually recovered by the helper, receive the established amber provenance.

Because the packaged helper payload changed in 0.0.11-exp2-r2, an older
installed Resource Monitor helper must be updated/repaired through
**Options → Helper** before privileged inspection is available.
