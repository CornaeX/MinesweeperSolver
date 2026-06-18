# Minesweeper Vision Solver & Autopilot

A computer-vision Minesweeper assistant that watches any Minesweeper window on your screen, works out which tiles are safe and which are mines, and draws a live color-coded overlay on top of the board. It can also drive the mouse for you in a fully automatic "autopilot" mode.

No game files, memory, or APIs are touched — the tool only reads pixels from the screen and (optionally) moves the mouse, so it works with virtually any Minesweeper clone, regardless of how it's built.

## Features

- **Automatic grid detection** — select a rough region with your mouse once; the tool detects the exact tile grid and dimensions using contour and edge-projection analysis.
- **Live board reading** — continuously re-reads tile colors to detect hidden tiles, flags, and revealed numbers (1–8).
- **Solver engine** with three layers of logic:
  - First-order deduction (a numbered tile's mines vs. flags vs. hidden neighbors).
  - Subset/pattern deduction for classic patterns like 1-2-1 and 1-2-2-1.
  - A probability heuristic that estimates mine likelihood for tiles that can't be solved with certainty, and highlights the safest guess.
- **Transparent on-screen overlay** drawn with Tkinter: blue outlines for confirmed safe tiles, red for confirmed mines, yellow for the best available guess.
- **Optional autopilot** that automatically left-clicks safe tiles, right-clicks (flags) confirmed mines, and clicks the lowest-probability guess when nothing is certain.
- **Configurable mouse movement** — choose between human-like curved mouse paths or instant teleportation to the target tile.
- **Hardware fail-safe** — slamming the mouse into a screen corner (a built-in PyAutoGUI safety feature) immediately aborts any automated movement.

## How It Works

1. **Capture & calibration (F8).** You draw a rough box around the Minesweeper board. The script runs edge detection inside that box, finds the individual tile contours (or falls back to projecting edge density if contours aren't clean), and computes the exact row/column count and tile size.
2. **Reading the board.** On every refresh tick, the script grabs a fresh screenshot of just the board region and classifies each tile by sampling its center pixels against a set of reference colors (hidden, flagged, or numbers 1–8).
3. **Solving.** The classified grid is fed into the solver, which iterates direct-logic and subset-logic passes until no further deductions can be made, then computes a probability map for any remaining ambiguous tiles.
4. **Overlay.** Results are drawn as colored rectangles on a transparent, click-through Tkinter window positioned exactly over the real board.
5. **Autopilot (F9).** If enabled, a background thread continuously reads the latest solver output and moves/clicks the mouse on the highest-priority target (mines first, then certain-safe tiles, then the best guess), pausing briefly between actions.

## Requirements

- Python 3.8+
- A Minesweeper window/app visible on screen (desktop game, browser version, etc.)
- Windows is recommended for full hotkey and mouse-automation support. On Linux, the `keyboard` library generally needs to run with elevated (root) privileges to register global hotkeys.

### Python packages

```bash
pip install opencv-python mss numpy keyboard pyautogui
```

`tkinter` ships with most Python installations on Windows and macOS. On Linux you may need to install it separately:

```bash
sudo apt-get install python3-tk
```

## Usage

```bash
python minesweeper_solver.py
```

1. Open your Minesweeper game so the board is visible on screen.
2. Run the script and press **F8**.
3. Drag a selection box loosely around the Minesweeper board (it doesn't need to be pixel-perfect — the script finds the exact grid edges for you) and press Enter/Space to confirm.
4. The overlay appears over the board and starts updating live as you play.
5. Optionally press **F9** to let the bot play automatically.

## Controls

| Key | Action |
|-----|--------|
| `F8` | Capture or re-capture the board region |
| `F9` | Toggle autopilot on/off |
| `F10` | Show/hide the overlay HUD |
| `Esc` | Exit the program |

## Configuration

These settings live at the top of the script:

| Variable | Description |
|---|---|
| `MOUSE_MODE` | `"human"` for a curved, organic mouse path, or `"instant"` to teleport directly to each tile. |
| `MOUSE_SPEED_FACTOR` | Speed multiplier for `"human"` mode. Lower values move faster (e.g. `0.3` is very fast, `1.0` is closer to natural speed). |
| `DELAY_BEFORE_CLICK` | Min/max random pause (seconds) after reaching a tile but before clicking it. |
| `DELAY_AFTER_CLICK` | Min/max random pause (seconds) after a click, before the next move is chosen. |

## Matching Your Theme's Colors

Tile classification works by comparing pixel colors against reference values defined near the top of the script:

- `COLOR_REVIEWED` / `COLOR_UNREVIEWED` — the background color of revealed vs. hidden tiles.
- `COLOR_FLAG` — the color used to render a flag.
- `NUM_COLORS` — a dictionary mapping `"1"`–`"8"` to the color each number is drawn in.

These are currently tuned for a specific dark theme. If the overlay misreads tiles in your game, sample the actual colors from a screenshot (e.g. with an eyedropper/color-picker tool) and update these arrays — they're stored as BGR (not RGB) since that's the format OpenCV uses.

## Limitations

- Grid detection relies on visible tile borders/edges; boards with very low contrast or unusual styling may need the color profiles or contour thresholds adjusted.
- The solver's pattern-matching pass handles common deduction patterns but isn't a full constraint-satisfaction/CSP solver, so some advanced multi-tile deductions may be left to the probability heuristic instead of being solved with certainty.
- Autopilot timing and mouse paths are tunable but are not guaranteed to look indistinguishable from real input; this matters if you intend to use the tool somewhere that prohibits automation.

## Disclaimer

This project is intended for personal use and experimentation with computer vision and game-solving algorithms on the single-player puzzle game Minesweeper. If you use it against a version of the game with its own terms of service (e.g., an online or app-store release), check that automation is permitted there before enabling autopilot.

## License

Add a license of your choice (e.g. MIT) before publishing.