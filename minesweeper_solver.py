import cv2
import mss
import numpy as np
import keyboard
import tkinter as tk
import time
import pyautogui
import random
import math
import threading

# Safety feature: Slam mouse into any corner of the screen to abort script tracking
pyautogui.FAILSAFE = True

# ==============================================================================
# --- AUTOMATION & SPEED CONFIGURATION ---
# ==============================================================================
# Mode Options: 
#   "human"   -> Uses an organic, smooth curve path to move the mouse.
#   "instant" -> Instantly teleports the cursor to the cell (maximum speed).
MOUSE_MODE = "human"

# Speed modifier for "human" mode curves. 
# Lower values make it faster. (e.g., 0.3 is lightning fast, 1.0 is default human speed).
MOUSE_SPEED_FACTOR = 0.3

# Pause duration (min, max in seconds) right AFTER reaching a tile, but BEFORE clicking it.
DELAY_BEFORE_CLICK = (0.01, 0.04)

# Reaction pause duration (min, max in seconds) AFTER making a click before choosing the next move.
DELAY_AFTER_CLICK = (0.08, 0.18)
# ==============================================================================

# --- DARK THEME COLOR PROFILES (BGR ARRYS) ---
COLOR_REVIEWED = np.array([72, 64, 56])    # #384048
COLOR_UNREVIEWED = np.array([92, 84, 76])   # #4C545C
COLOR_FLAG = np.array([89, 89, 247])         # #F75959

NUM_COLORS = {
    "1": np.array([255, 199, 124]),  # #7CC7FF
    "2": np.array([102, 194, 102]),  # #66C266
    "3": np.array([136, 119, 255]),  # #FF7788
    "4": np.array([255, 136, 238]),  # #EE88FF
    "5": np.array([34, 170, 221]),   # #DDAA22
    "6": np.array([204, 204, 102]),  # #66CCCC
    "7": np.array([153, 153, 153]),  # #999999
    "8": np.array([224, 216, 208])   # #D0D8E0
}

def human_move_to(target_x, target_y):
    """Moves mouse to target coordinates adjusting dynamically based on configuration settings."""
    start_x, start_y = pyautogui.position()
    if start_x == target_x and start_y == target_y:
        return

    if MOUSE_MODE == "instant":
        pyautogui.moveTo(target_x, target_y)
        time.sleep(random.uniform(*DELAY_BEFORE_CLICK))
        return

    distance = math.hypot(target_x - start_x, target_y - start_y)
    steps = max(6, int((distance / 25) * MOUSE_SPEED_FACTOR))
    
    control_x = (start_x + target_x) / 2 + random.randint(-40, 40)
    control_y = (start_y + target_y) / 2 + random.randint(-40, 40)
    
    for i in range(1, steps + 1):
        t = i / steps
        t = 1 - (1 - t) ** 3
        
        curr_x = int((1 - t)**2 * start_x + 2 * (1 - t) * t * control_x + t**2 * target_x)
        curr_y = int((1 - t)**2 * start_y + 2 * (1 - t) * t * control_y + t**2 * target_y)
        
        if t < 0.9 and MOUSE_SPEED_FACTOR > 0.5:
            curr_x += random.randint(-1, 1)
            curr_y += random.randint(-1, 1)
        
        pyautogui.moveTo(curr_x, curr_y)
        time.sleep(random.uniform(0.002, 0.006) * MOUSE_SPEED_FACTOR)
        
    pyautogui.moveTo(target_x, target_y)
    time.sleep(random.uniform(*DELAY_BEFORE_CLICK))

def auto_solver_loop(app_signals, screen_x, screen_y, cell_w_step, cell_h_step):
    """Continuous worker loop processing step decisions dynamically."""
    print("[AUTOPILOT] Worker Loop Core Activated.")
    
    while app_signals["auto_play"] and not app_signals["terminate"] and not app_signals["recapture"]:
        if not app_signals.get("latest_moves"):
            time.sleep(0.02)
            continue

        safe_set, mine_set, yellow_dict = app_signals["latest_moves"]
        if not safe_set and not mine_set and not yellow_dict:
            time.sleep(0.02)
            continue

        target_cell = None
        click_type = "left"

        if mine_set:
            target_cell = list(mine_set)[0]
            click_type = "right"
        elif safe_set:
            target_cell = list(safe_set)[0]
            click_type = "left"
        elif yellow_dict:
            min_p = min(yellow_dict.values())
            best_guesses = [k for k, v in yellow_dict.items() if v == min_p]
            if best_guesses:
                target_cell = random.choice(best_guesses)
                click_type = "left"

        if target_cell and app_signals["auto_play"]:
            r, c = target_cell
            click_x = screen_x + int((c + 0.5) * cell_w_step)
            click_y = screen_y + int((r + 0.5) * cell_h_step)
            
            try:
                human_move_to(click_x, click_y)
                if app_signals["auto_play"]:
                    pyautogui.click(button=click_type)
                    app_signals["latest_moves"] = (set(), set(), {})
                    app_signals["force_refresh"] = True
                    time.sleep(random.uniform(*DELAY_AFTER_CLICK))
            except pyautogui.FailSafeException:
                print("[ABORT] Fail-safe triggered via hardware gesture boundary!")
                app_signals["auto_play"] = False
                break
        else:
            time.sleep(0.02)

    app_signals["auto_playing_thread"] = False
    print("[AUTOPILOT] Worker Loop Core Terminated Safely.")

def identify_cell_state(cell_img):
    """Scans cell core using exact pixel-matching arrays for custom theme profiles."""
    h, w, _ = cell_img.shape
    if h == 0 or w == 0: return "?"

    inner = cell_img[int(h*0.25):int(h*0.75), int(w*0.25):int(w*0.75)]
    avg_bgr = np.mean(inner, axis=(0, 1))

    if np.sum(np.linalg.norm(inner - COLOR_FLAG, axis=2) < 40) > 8: return "F"
    if np.linalg.norm(avg_bgr - COLOR_UNREVIEWED) < 15: return "H" 

    color_scores = {}
    for num_str, target_bgr in NUM_COLORS.items():
        distances = np.linalg.norm(inner - target_bgr, axis=2)
        color_scores[num_str] = np.sum(distances < 45)

    best_number = max(color_scores, key=color_scores.get)
    if color_scores[best_number] >= 10: return best_number

    return "."

def get_neighbors(r, c, rows, cols):
    neighbors = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0: continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append((nr, nc))
    return neighbors

def compute_solver_overlay(matrix, rows, cols):
    """Advanced solver engine utilizing first-order logic and subset/pattern deduction maps."""
    overlay = [["" for _ in range(cols)] for _ in range(rows)]
    confirmed_safe = set()
    confirmed_mines = set()

    for r in range(rows):
        for c in range(cols):
            if matrix[r][c] == 'F': overlay[r][c] = '#FF4444'

    # Loop logic passes iteratively to combine cascading matrix discoveries seamlessly
    while True:
        deductions_made = False

        # --- PASS 1: FIRST-ORDER DIRECT LOGIC ---
        for r in range(rows):
            for c in range(cols):
                val = matrix[r][c]
                if val in ['1', '2', '3', '4', '5', '6', '7', '8']:
                    num = int(val)
                    neighbors = get_neighbors(r, c, rows, cols)
                    
                    h_list = [n for n in neighbors if matrix[n[0]][n[1]] == 'H' and n not in confirmed_safe and n not in confirmed_mines]
                    f_count = len([n for n in neighbors if matrix[n[0]][n[1]] == 'F' or n in confirmed_mines])
                    
                    # All remaining are mines
                    if len(h_list) + f_count == num and len(h_list) > 0:
                        for cell in h_list:
                            confirmed_mines.add(cell)
                            deductions_made = True
                    # All remaining are safe
                    if f_count == num and len(h_list) > 0:
                        for cell in h_list:
                            confirmed_safe.add(cell)
                            deductions_made = True

        # --- PASS 2: SUBSET/PATTERN COMPLEX LOGIC (Handles 1-2-1, 1-2-2-1, etc.) ---
        constraints = []
        for r in range(rows):
            for c in range(cols):
                val = matrix[r][c]
                if val in ['1', '2', '3', '4', '5', '6', '7', '8']:
                    num = int(val)
                    neighbors = get_neighbors(r, c, rows, cols)
                    
                    h_set = set(n for n in neighbors if matrix[n[0]][n[1]] == 'H' and n not in confirmed_safe and n not in confirmed_mines)
                    f_count = len([n for n in neighbors if matrix[n[0]][n[1]] == 'F' or n in confirmed_mines])
                    
                    rem_mines = num - f_count
                    if h_set:
                        constraints.append((h_set, rem_mines))

        # Cross-compare shared borders between adjacent constraints
        for i in range(len(constraints)):
            for j in range(len(constraints)):
                if i == j: continue
                set_A, mines_A = constraints[i]
                set_B, mines_B = constraints[j]

                # If group A's cells are completely inside group B's cells
                if set_A.issubset(set_B) and set_A != set_B:
                    diff_set = set_B - set_A
                    diff_mines = mines_B - mines_A

                    # Case A: Leftover cells cannot contain any mines -> Clear them!
                    if diff_mines == 0:
                        for cell in diff_set:
                            if cell not in confirmed_safe:
                                confirmed_safe.add(cell)
                                deductions_made = True
                    # Case B: Leftover cells match exact remaining mines -> Flag them!
                    elif diff_mines == len(diff_set):
                        for cell in diff_set:
                            if cell not in confirmed_mines:
                                confirmed_mines.add(cell)
                                deductions_made = True

        if not deductions_made:
            break

    # Commit deductions to screen graphics pipeline
    for (r, c) in confirmed_safe: overlay[r][c] = "#00FF22"  # Blue
    for (r, c) in confirmed_mines: overlay[r][c] = '#FF4444' # Red

    # --- PASS 3: PROBABILITY HEURISTIC ESTIMATION ---
    mine_probs = {}
    for r in range(rows):
        for c in range(cols):
            val = matrix[r][c]
            if val in ['1', '2', '3', '4', '5', '6', '7', '8']:
                num = int(val)
                neighbors = get_neighbors(r, c, rows, cols)
                unresolved_h = [n for n in neighbors if matrix[n[0]][n[1]] == 'H' and n not in confirmed_safe and n not in confirmed_mines]
                locked_mines = len([n for n in neighbors if matrix[n[0]][n[1]] == 'F' or n in confirmed_mines])
                
                rem_mines = num - locked_mines
                if len(unresolved_h) > 0 and rem_mines >= 0:
                    local_p = rem_mines / len(unresolved_h)
                    for h_cell in unresolved_h:
                        mine_probs[h_cell] = max(mine_probs.get(h_cell, 0.0), local_p)

    eligible_yellows = {k: v for k, v in mine_probs.items() if k not in confirmed_safe and k not in confirmed_mines}
    if eligible_yellows:
        min_p = min(eligible_yellows.values())
        if min_p < 1.0:
            for h_cell, p in eligible_yellows.items():
                if p == min_p: overlay[h_cell[0]][h_cell[1]] = '#FFBB33' # Yellow

    return overlay, confirmed_safe, confirmed_mines, eligible_yellows

def calculate_matrix_by_projection(edge_map, total_w, total_h):
    v_proj = np.sum(edge_map, axis=0)
    h_proj = np.sum(edge_map, axis=1)
    
    def get_spacing(proj):
        thresh = np.max(proj) * 0.20
        peaks = [i for i in range(1, len(proj)-1) if proj[i] > thresh and proj[i] >= proj[i-1] and proj[i] >= proj[i+1]]
        if len(peaks) < 2: return None
        return np.median(np.diff(peaks))

    space_w = get_spacing(v_proj)
    space_h = get_spacing(h_proj)
    
    if space_w and space_h and space_w > 12 and space_h > 12:
        return int(round(total_h / space_h)), int(round(total_w / space_w))
    return (16, 16) if total_w > 450 else (9, 9)

def main():
    while True:
        print("\n[READY] Press F8 to map/recapture your Minesweeper window area...")
        keyboard.wait("F8")
        time.sleep(0.2)

        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            screenshot = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
            roi = cv2.selectROI("Select Minesweeper Area", screenshot, fromCenter=False)
            cv2.destroyAllWindows()

            x, y, w, h = roi
            if w == 0 or h == 0: break

            rough_crop = screenshot[y:y+h, x:x+w]
            gray = cv2.cvtColor(rough_crop, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            valid_cells = []
            large_grid_contour = None

            for c in contours:
                bx, by, bw, bh = cv2.boundingRect(c)
                aspect_ratio = float(bw) / bh if bh != 0 else 0
                if 12 <= bw <= 65 and 12 <= bh <= 65 and 0.85 <= aspect_ratio <= 1.15:
                    valid_cells.append((bx, by, bw, bh))
                elif bw >= 150 and bh >= 150 and 0.95 <= aspect_ratio <= 1.05:
                    large_grid_contour = (bx, by, bw, bh)

            if valid_cells:
                grid_x1, grid_y1 = min(c[0] for c in valid_cells), min(c[1] for c in valid_cells)
                grid_x2, grid_y2 = max(c[0] + c[2] for c in valid_cells), max(c[1] + c[3] for c in valid_cells)
            elif large_grid_contour:
                bx, by, bw, bh = large_grid_contour
                grid_x1, grid_y1, grid_x2, grid_y2 = bx, by, bx + bw, by + bh
            else:
                continue

            final_w, final_h = grid_x2 - grid_x1, grid_y2 - grid_y1
            screen_x = monitor["left"] + x + grid_x1
            screen_y = monitor["top"] + y + grid_y1

            if valid_cells:
                max_d_w = max(c[2] for c in valid_cells)
                max_d_h = max(c[3] for c in valid_cells)
                true_tiles = [c for c in valid_cells if c[2] >= max_d_w - 4 and c[3] >= max_d_h - 4]
                cols = int(round(final_w / np.median([c[2] for c in true_tiles])))
                rows = int(round(final_h / np.median([c[3] for c in true_tiles])))
            else:
                rows, cols = calculate_matrix_by_projection(edges[grid_y1:grid_y2, grid_x1:grid_x2], final_w, final_h)

            cell_w_step, cell_h_step = final_w / cols, final_h / rows

            print(f"\n--- RADAR AUTO-SYNCHRONIZED (REAL-TIME ACTIVE) ---")
            print(f"Detected Matrix: {rows} rows x {cols} columns")
            print(f"Current Target Engine Mode: '{MOUSE_MODE.upper()}'")
            print("\n[CONTROLS]: F8 -> Recapture | F9 -> TOGGLE AUTOPILOT | F10 -> Hide HUD | ESC -> Exit")

            root = tk.Tk()
            root.overrideredirect(True)
            root.geometry(f"{final_w}x{final_h}+{screen_x}+{screen_y}")
            root.lift()
            root.wm_attributes("-topmost", True, "-disabled", True, "-transparentcolor", "pink")

            canvas = tk.Canvas(root, bg="pink", highlightthickness=0)
            canvas.pack(fill="both", expand=True)

            for i in range(cols + 1):
                lx = int(i * cell_w_step)
                canvas.create_line(lx, 0, lx, final_h, fill="#2A2A2A", width=1, tags="grid")
            for j in range(rows + 1):
                ly = int(j * cell_h_step)
                canvas.create_line(0, ly, final_w, ly, fill="#2A2A2A", width=1, tags="grid")

            app_signals = {
                "visible": True, "recapture": False, "terminate": False, "toggle_visible": False,
                "auto_play": False, "auto_playing_thread": False, "latest_moves": None,
                "force_refresh": False, "debug_grid": False
            }
            last_board_matrix = [None]

            def trigger_recapture(): app_signals["auto_play"], app_signals["recapture"] = False, True
            def trigger_toggle(): app_signals["toggle_visible"] = True
            def trigger_terminate(): app_signals["auto_play"], app_signals["terminate"] = False, True
            def trigger_toggle_auto():
                if not app_signals["visible"]: return
                app_signals["auto_play"] = not app_signals["auto_play"]
                print(f"[HUD-BOT] Continuous Autopilot state: {'[STARTED]' if app_signals['auto_play'] else '[STOPPED]'}")
                if app_signals["auto_play"] and not app_signals["auto_playing_thread"]:
                    app_signals["auto_playing_thread"] = True
                    threading.Thread(target=auto_solver_loop, args=(app_signals, screen_x, screen_y, cell_w_step, cell_h_step), daemon=True).start()
            def trigger_debug_grid():
                app_signals["debug_grid"] = not app_signals["debug_grid"]
                app_signals["force_refresh"] = True # Force a redraw frame
                print(f"[DEBUG] Verification grid overlay: {'[ENABLED]' if app_signals['debug_grid'] else '[DISABLED]'}")
                
            hk_w = keyboard.add_hotkey("w", trigger_debug_grid)    
            hk_f8 = keyboard.add_hotkey("F8", trigger_recapture)
            hk_f9 = keyboard.add_hotkey("F9", trigger_toggle_auto)
            hk_f10 = keyboard.add_hotkey("F10", trigger_toggle)
            hk_esc = keyboard.add_hotkey("esc", trigger_terminate)

            def clean_hotkeys():
                keyboard.remove_hotkey(hk_w); keyboard.remove_hotkey(hk_f8); keyboard.remove_hotkey(hk_f9)
                keyboard.remove_hotkey(hk_f10); keyboard.remove_hotkey(hk_esc)

            def check_inputs_and_update():
                if app_signals["terminate"] or app_signals["recapture"]:
                    clean_hotkeys(); root.destroy(); return

                if app_signals["toggle_visible"]:
                    app_signals["toggle_visible"] = False
                    app_signals["visible"] = not app_signals["visible"]
                    action_state = "normal" if app_signals["visible"] else "hidden"
                    canvas.itemconfigure("grid", state=action_state)
                    canvas.itemconfigure("overlay", state=action_state)
                    if not app_signals["visible"]:
                        app_signals["auto_play"] = False
                        canvas.delete("overlay")
                        last_board_matrix[0] = None

                if app_signals["visible"]:
                    grid_config = {"top": screen_y, "left": screen_x, "width": final_w, "height": final_h}
                    with mss.MSS() as fresh_sct:
                        fresh_shot = cv2.cvtColor(np.array(fresh_sct.grab(grid_config)), cv2.COLOR_BGRA2BGR)
                    
                    board_matrix = []
                    for r in range(rows):
                        row_states = []
                        for c in range(cols):
                            x1, y1 = int(c * cell_w_step), int(r * cell_h_step)
                            x2, y2 = int((c + 1) * cell_w_step), int((r + 1) * cell_h_step)
                            row_states.append(identify_cell_state(fresh_shot[y1:y2, x1:x2]))
                        board_matrix.append(row_states)

                    if board_matrix != last_board_matrix[0] or app_signals.get("force_refresh"):
                        app_signals["force_refresh"] = False # Reset the flag immediately
                        last_board_matrix[0] = board_matrix
                        canvas.delete("overlay")
                        canvas.delete("debug_line")
                        
                        if app_signals["debug_grid"]:
                            # Vertical lines
                            for i in range(cols + 1):
                                lx = int(i * cell_w_step)
                                canvas.create_line(lx, 0, lx, final_h, fill="#FF00FF", width=2, tags="debug_line")
                            # Horizontal lines
                            for j in range(rows + 1):
                                ly = int(j * cell_h_step)
                                canvas.create_line(0, ly, final_w, ly, fill="#FF00FF", width=2, tags="debug_line")
                        
                        solver_map, safe_set, mine_set, yellow_dict = compute_solver_overlay(board_matrix, rows, cols)
                        # app_signals["latest_moves"] = (safe_set, mine_set, yellow_dict)
                        
                        for r in range(rows):
                            for c in range(cols):
                                color_hex = solver_map[r][c]
                                if color_hex:
                                    x1, y1 = int(c * cell_w_step), int(r * cell_h_step)
                                    x2, y2 = int((c + 1) * cell_w_step), int((r + 1) * cell_h_step)
                                    canvas.create_rectangle(x1 + 3, y1 + 3, x2 - 3, y2 - 3, outline=color_hex, width=2, tags="overlay")

                root.after(40, check_inputs_and_update)

            root.after(40, check_inputs_and_update)
            root.mainloop()

            if app_signals["terminate"]: break
            if app_signals["recapture"]: time.sleep(0.3); continue

if __name__ == "__main__":
    main()