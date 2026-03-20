from textual.theme import Theme

# CSS for the btop-style theme
POLYGLOT_CSS = """
Screen {
    align-horizontal: center;
    align-vertical: middle;
}
"""

SWARM_THEME = Theme(
    name="swarm",
    primary="#00d4aa",        # teal — main accent (btop green equivalent)
    secondary="#0099cc",      # blue — secondary info
    accent="#ff6b35",         # orange — warnings, highlights
    warning="#ffaa00",        # amber
    error="#ff4466",          # red
    success="#00ff88",        # bright green — running/healthy
    background="#0d0f14",     # near-black bg
    surface="#131820",        # panel bg
    panel="#1a2030",          # slightly lighter panel
    boost="#00d4aa",
    dark=True,
    variables={
        # Borders
        "border-color":        "#1e3a4a",
        "border-color-focus":  "#00d4aa",
        # Text tiers
        "text-bright":         "#e0f0ff",
        "text-normal":         "#8ab4cc",
        "text-dim":            "#3a5060",
        "text-muted":          "#3a5060",
        # State colors (used by agent rows)
        "state-running":       "#00ff88",
        "state-done":          "#00d4aa",
        "state-error":         "#ff4466",
        "state-stalled":       "#ffaa00",
        "state-idle":          "#3a5060",
        # Role colors
        "role-scout":          "#00aaff",
        "role-builder":        "#00d4aa",
        "role-developer":      "#aa88ff",
        "role-tester":         "#ffaa00",
        "role-reviewer":       "#ff6b35",
        "role-merger":         "#ff4499",
        "role-monitor":        "#88ccff",
        "role-coordinator":    "#ffffff",
    },
)