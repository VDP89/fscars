# Functional Scars - demo.tape
#
# Renders to assets/demo.gif via charmbracelet/vhs-action in CI.
# Storyboard target: ~28s, terminal-only, full lifecycle:
#   install -> list -> fire -> log -> stats
#
# Edit and push -> CI re-renders demo.gif automatically.

Output assets/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 720
Set Padding 30
Set TypingSpeed 55ms
Set Theme "Catppuccin Mocha"

# ---------------------------------------------------------------------------
# Hidden setup: a clean demo project, fscar on PATH, settings wired.
# ---------------------------------------------------------------------------
Hide
Type "export PATH=$HOME/.local/bin:$PATH"
Enter
Type "cd /tmp && rm -rf fscar-demo && mkdir fscar-demo && cd fscar-demo"
Enter
Type "clear"
Enter
Sleep 200ms
Show

# ---------------------------------------------------------------------------
# Frame 1: install + init (0 - 7s)
# ---------------------------------------------------------------------------
Type "# Functional Scars - bolt-on correction primitive for AI coding agents."
Sleep 1.5s
Enter
Sleep 500ms

Type "fscar init"
Sleep 700ms
Enter
Sleep 2.5s

Type "clear"
Sleep 200ms
Enter
Sleep 300ms

# ---------------------------------------------------------------------------
# Frame 2: see the starter scars (7 - 13s)
# ---------------------------------------------------------------------------
Type "# Five starter scars come pre-installed."
Sleep 1.2s
Enter
Sleep 400ms

Type "fscar list"
Sleep 700ms
Enter
Sleep 4s

Type "clear"
Sleep 200ms
Enter
Sleep 300ms

# ---------------------------------------------------------------------------
# Frame 3: a real-shape PreToolUse payload triggers utc-timestamps (13 - 20s)
# ---------------------------------------------------------------------------
Type "# Claude Code is about to write time.Now() in a handler..."
Sleep 1.2s
Enter
Sleep 400ms

Type `echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"src/handler.go","content":"now := time.Now()"},"cwd":".","session_id":"demo"}' | python -m fscars.run_hook --adapter claude_code`
Sleep 800ms
Enter
Sleep 3s

Type "clear"
Sleep 200ms
Enter
Sleep 300ms

# ---------------------------------------------------------------------------
# Frame 4: log + stats (20 - 27s)
# ---------------------------------------------------------------------------
Type "# Every fire is logged. Recall is computable."
Sleep 1.2s
Enter
Sleep 400ms

Type "fscar log"
Sleep 700ms
Enter
Sleep 3s

Type "fscar stats"
Sleep 700ms
Enter
Sleep 3s

# ---------------------------------------------------------------------------
# Closing breath
# ---------------------------------------------------------------------------
Sleep 1.5s
