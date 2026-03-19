# src/tui/theme.py

POLYGLOT_CSS = """
/* ═══════════════════════════════════════════
   POLYGLOTSWARM — Cyberpunk 2077 Theme
   ═══════════════════════════════════════════ */

/* Color tokens */
$void:         #060810;
$bg:           #0a0d14;
$bg-panel:     #0d1117;
$bg-elevated:  #111827;
$bg-hover:     #1a2235;

/* Cyberpunk palette */
$yellow:       #f9e718;
$yellow-dim:   #7a7209;
$cyan:         #00e5ff;
$cyan-dim:     #004d5e;
$magenta:      #ff2d6b;
$magenta-dim:  #5e0020;
$orange:       #ff6b1a;
$purple:       #bd00ff;
$green:        #39ff14;
$green-dim:    #0f4400;
$red:          #ff1c1c;
$muted:        #3a4255;
$text:         #c8d8f0;
$text-dim:     #5a6a80;

/* Border styles */
$border:       #1e2d42;
$border-focus: $cyan;
$border-warn:  $yellow;
$border-error: $magenta;

/* ── Global ── */
Screen {
    background: $void;
    color: $text;
    layout: vertical;
}

Header {
    background: $bg-elevated;
    color: $yellow;
    text-style: bold;
    height: 1;
    dock: top;
}

Footer {
    background: $bg-elevated;
    color: $muted;
    height: 1;
    dock: bottom;
}

/* ── Root layout ── */
#layout {
    layout: horizontal;
    height: 1fr;
    width: 1fr;
    background: $void;
}

#left-col {
    width: 42%;
    height: 100%;
    layout: vertical;
    background: $void;
}

#right-col {
    width: 58%;
    height: 100%;
    layout: vertical;
    background: $void;
}

/* ── Overseer Chat ── */
#overseer-chat {
    height: 1fr;
    border: solid $cyan-dim;
    background: $bg-panel;
    layout: vertical;
    padding: 0;
}

#overseer-chat:focus-within {
    border: solid $cyan;
}

#chat-log {
    height: 1fr;
    background: $bg-panel;
    color: $text;
    padding: 0 1;
    scrollbar-color: $cyan-dim;
    scrollbar-color-hover: $cyan;
    scrollbar-background: $bg-panel;
}

#nudge-input {
    height: 3;
    background: $bg-elevated;
    color: $yellow;
    border: tall $border;
    padding: 0 1;
}

#nudge-input:focus {
    border: tall $cyan;
}

/* ── Agent Fleet ── */
#agent-fleet {
    height: 1fr;
    border: solid $border;
    background: $bg-panel;
    layout: vertical;
    padding: 0;
}

#agent-fleet:focus-within {
    border: solid $yellow;
}

#fleet-table {
    height: 1fr;
    background: $bg-panel;
    color: $text;
    scrollbar-color: $yellow-dim;
    scrollbar-background: $bg-panel;
}

DataTable {
    background: $bg-panel;
    color: $text;
}

DataTable > .datatable--header {
    background: $bg-elevated;
    color: $yellow;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: $cyan-dim;
    color: $cyan;
    text-style: bold;
}

DataTable > .datatable--hover {
    background: $bg-hover;
}

DataTable > .datatable--fixed {
    background: $bg-elevated;
    color: $yellow;
}

/* ── Output row ── */
#output-row {
    height: 32%;
    min-height: 10;
    layout: horizontal;
    background: $void;
}

#agent-output {
    width: 65%;
    height: 100%;
    border: solid $border;
    background: $bg-panel;
    layout: vertical;
    padding: 0;
}

#agent-output:focus-within {
    border: solid $purple;
}

#output-log {
    height: 1fr;
    background: $bg-panel;
    color: $text;
    padding: 0 1;
    scrollbar-color: $purple;
    scrollbar-background: $bg-panel;
}

#event-log {
    width: 35%;
    height: 100%;
    border: solid $border;
    background: $bg-panel;
    layout: vertical;
    padding: 0;
}

#event-log:focus-within {
    border: solid $orange;
}

#event-log-widget {
    height: 1fr;
    background: $bg-panel;
    color: $text;
    padding: 0 1;
    scrollbar-color: $orange;
    scrollbar-background: $bg-panel;
}

/* ── Panel title bar ── */
.panel--title {
    height: 1;
    width: 100%;
    background: $bg-elevated;
    padding: 0 1;
    text-style: bold;
}

.panel--title-cyan    { color: $cyan; }
.panel--title-yellow  { color: $yellow; }
.panel--title-purple  { color: $purple; }
.panel--title-orange  { color: $orange; }

/* ── Role colors ── */
.role-orchestrator { color: $purple;  text-style: bold; }
.role-coordinator  { color: #818cf8;  }
.role-supervisor   { color: $cyan;    }
.role-lead         { color: #38bdf8;  }
.role-scout        { color: $green;   }
.role-developer    { color: $cyan;    }
.role-builder      { color: $yellow;  }
.role-tester       { color: $orange;  }
.role-reviewer     { color: $magenta; }
.role-merger       { color: $purple;  }
.role-monitor      { color: $muted;   }

/* ── State badge colors (used in markup) ── */
/* Running = green, Stalled = magenta blink, Done = muted, Error = red, Queued = yellow */

/* ── Spinner ── */
.spinner {
    color: $cyan-dim;
    text-style: italic;
}

/* ── Modal ── */
ModalScreen {
    background: $void 85%;
    align: center middle;
}

.modal-dialog {
    background: $bg-elevated;
    border: solid $cyan;
    padding: 1 2;
    width: 72%;
    height: auto;
    max-height: 80%;
}

.modal-dialog Label {
    color: $cyan;
    text-style: bold;
}

Button {
    background: $bg-elevated;
    border: tall $border;
    color: $text;
    margin: 1 0 0 0;
}

Button:hover {
    background: $cyan-dim;
    border: tall $cyan;
    color: $cyan;
}

Button.-primary {
    background: $cyan-dim;
    border: tall $cyan;
    color: $cyan;
    text-style: bold;
}

Button.-error {
    background: $magenta-dim;
    border: tall $magenta;
    color: $magenta;
    text-style: bold;
}
"""
