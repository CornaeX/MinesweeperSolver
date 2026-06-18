import cv2
import mss
import numpy as np
import keyboard
import tkinter as tk
import time

# --- YOUR DARK THEME COLORS (CONVERTED HEX TO BGR) ---
COLOR_REVIEWED = np.array([72, 64, 56])   # #384048
COLOR_UNREVIEWED = np.array([92, 84, 76])     # #4C545C
COLOR_FLAG = np.array([89, 89, 247])        # #F75959

# Precise 1-8 Digit Palette Mapping
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

def identify_cell_state(cell_img):
    """Scans cell core using exact pixel-matching arrays for custom theme profiles."""
    h, w, _ = cell_img.shape
    if h == 0 or w == 0:
        return "?"

    inner = cell_img[int(h*0.25):int(h*0.75), int(w*0.25):int(w*0.75)]
    avg_bgr = np.mean(inner, axis=(0, 1))

    # 1. Flag Detection
    flag_dist = np.linalg.norm(inner - COLOR_FLAG, axis=2)
    if np.sum(flag_dist < 40) > 8: 
        return "F"

    # 2. Unreviewed / Hidden Detection
    if np.linalg.norm(avg_bgr - COLOR_UNREVIEWED) < 15:
        return "H" 

    # 3. Reviewed Space / Number Detection
    color_scores = {}
    for num_str, target_bgr in NUM_COLORS.items():
        distances = np.linalg.norm(inner - target_bgr, axis=2)
        matching_pixels = np.sum(distances < 45)
        color_scores[num_str] = matching_pixels

    best_number = max(color_scores, key=color_scores.get)
    highest_pixel_count = color_scores[best_number]

    if highest_pixel_count >= 10:
        return best_number

    return "."

def get_neighbors(r, c, rows, cols):
    """Returns valid 8-directional coordinate neighbors for a given grid cell coordinate."""
    neighbors = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append((nr, nc))
    return neighbors

def compute_solver_overlay(matrix, rows, cols):
    """Executes logical deduction matrix rules and analyzes risk probabilities."""
    overlay = [["" for _ in range(cols)] for _ in range(rows)]
    confirmed_safe = set()
    confirmed_mines = set()

    for r in range(rows):
        for c in range(cols):
            if matrix[r][c] == 'F':
                overlay[r][c] = '#FF4444'  # Red
            elif matrix[r][c] == 'H':
                overlay[r][c] = '#00FF66'  # Green (Default Uncertain)

    # 1. First-Order Logic Pass
    for r in range(rows):
        for c in range(cols):
            val = matrix[r][c]
            if val in ['1', '2', '3', '4', '5', '6', '7', '8']:
                num = int(val)
                neighbors = get_neighbors(r, c, rows, cols)
                
                h_list = [n for n in neighbors if matrix[n[0]][n[1]] == 'H']
                f_list = [n for n in neighbors if matrix[n[0]][n[1]] == 'F']
                
                h_count, f_count = len(h_list), len(f_list)

                if f_count == num:
                    for h_cell in h_list:
                        confirmed_safe.add(h_cell)
                if f_count + h_count == num:
                    for h_cell in h_list:
                        confirmed_mines.add(h_cell)

    for (r, c) in confirmed_safe:
        overlay[r][c] = '#00A2FF'  # Blue (Safe)
    for (r, c) in confirmed_mines:
        overlay[r][c] = '#FF4444'  # Red (Mine)

    # 2. Probability Heuristic Pass
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
                rem_h = len(unresolved_h)

                if rem_h > 0 and rem_mines >= 0:
                    local_p = rem_mines / rem_h
                    for h_cell in unresolved_h:
                        mine_probs[h_cell] = max(mine_probs.get(h_cell, 0.0), local_p)

    eligible_yellows = {k: v for k, v in mine_probs.items() if k not in confirmed_safe and k not in confirmed_mines}
    if eligible_yellows:
        min_p = min(eligible_yellows.values())
        if min_p < 1.0:
            for h_cell, p in eligible_yellows.items():
                if p == min_p:
                    overlay[h_cell[0]][h_cell[1]] = '#FFBB33'  # Yellow (Best Guess)

    return overlay

def calculate_matrix_by_projection(edge_map, total_w, total_h):
    """Fallback Line Analyzer scanner mechanism."""
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
    
    ratio = total_w / total_h
    if 0.95 <= ratio <= 1.05:
        return (16, 16) if total_w > 450 else (9, 9)
    return 16, 30

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
            if w == 0 or h == 0:
                print("Selection cancelled. Terminating program script.")
                break

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
                grid_x1, grid_y1 = bx, by
                grid_x2, grid_y2 = bx + bw, by + bh
            else:
                print("[ERROR] Could not detect grid contours. Try expanding selection wider than the board.")
                continue

            final_w = grid_x2 - grid_x1
            final_h = grid_y2 - grid_y1
            screen_x = monitor["left"] + x + grid_x1
            screen_y = monitor["top"] + y + grid_y1

            grid_edges = edges[grid_y1:grid_y2, grid_x1:grid_x2]
            if valid_cells:
                max_detected_w = max(c[2] for c in valid_cells)
                max_detected_h = max(c[3] for c in valid_cells)
                true_tile_contours = [c for c in valid_cells if c[2] >= max_detected_w - 4 and c[3] >= max_detected_h - 4]
                
                avg_cell_w = np.median([c[2] for c in true_tile_contours])
                avg_cell_h = np.median([c[3] for c in true_tile_contours])
                
                cols = int(round(final_w / avg_cell_w))
                rows = int(round(final_h / avg_cell_h))
            else:
                rows, cols = calculate_matrix_by_projection(grid_edges, final_w, final_h)

            cell_w_step = final_w / cols
            cell_h_step = final_h / rows

            print(f"\n--- RADAR AUTO-SYNCHRONIZED (REAL-TIME ACTIVE) ---")
            print(f"Detected Matrix: {rows} rows x {cols} columns")
            print(f"Unit Cell Size: {cell_w_step:.2f}x{cell_h_step:.2f} pixels")
            print("\n[CONTROLS]:")
            print("  F8  -> Recapture Board Bounds & Reset Tracking Alignment")
            print("  F10 -> Toggle Entire HUD Display Layer ON/OFF")
            print("  ESC -> Close Script Completely")

            # --- LATTICE HUD DISPLAY (TKINTER) ---
            root = tk.Tk()
            root.overrideredirect(True)
            root.geometry(f"{final_w}x{final_h}+{screen_x}+{screen_y}")
            root.lift()
            root.wm_attributes("-topmost", True)
            root.wm_attributes("-disabled", True)
            root.wm_attributes("-transparentcolor", "pink")

            canvas = tk.Canvas(root, bg="pink", highlightthickness=0)
            canvas.pack(fill="both", expand=True)

            for i in range(cols + 1):
                lx = int(i * cell_w_step)
                canvas.create_line(lx, 0, lx, final_h, fill="#2A2A2A", width=1, tags="grid")
            for j in range(rows + 1):
                ly = int(j * cell_h_step)
                canvas.create_line(0, ly, final_w, ly, fill="#2A2A2A", width=1, tags="grid")

            # Thread-safe context signals register
            app_signals = {
                "visible": True, 
                "recapture": False, 
                "terminate": False,
                "toggle_visible": False
            }
            last_board_matrix = [None]

            # Callback modifiers to protect Tkinter thread runtime
            def trigger_recapture(): app_signals["recapture"] = True
            def trigger_toggle(): app_signals["toggle_visible"] = True
            def trigger_terminate(): app_signals["terminate"] = True

            # Register hardware background listeners (Locks input instantly)
            hk_f8 = keyboard.add_hotkey("F8", trigger_recapture)
            hk_f10 = keyboard.add_hotkey("F10", trigger_toggle)
            hk_esc = keyboard.add_hotkey("esc", trigger_terminate)

            def clean_hotkeys():
                keyboard.remove_hotkey(hk_f8)
                keyboard.remove_hotkey(hk_f10)
                keyboard.remove_hotkey(hk_esc)

            def check_inputs_and_update():
                if app_signals["terminate"]:
                    clean_hotkeys()
                    root.destroy()
                    return

                if app_signals["recapture"]:
                    clean_hotkeys()
                    root.destroy()
                    return

                # Handle instantaneous visibility state switch safely 
                if app_signals["toggle_visible"]:
                    app_signals["toggle_visible"] = False # Reset flag latch
                    app_signals["visible"] = not app_signals["visible"]
                    action_state = "normal" if app_signals["visible"] else "hidden"
                    
                    canvas.itemconfigure("grid", state=action_state)
                    canvas.itemconfigure("overlay", state=action_state)
                    
                    if not app_signals["visible"]:
                        canvas.delete("overlay")
                        last_board_matrix[0] = None
                    print(f"[HUD] Overlay Layer: {'VISIBLE' if app_signals['visible'] else 'HIDDEN'}")

                # --- REAL-TIME GRAPHICS ENGINE PASS ---
                if app_signals["visible"]:
                    grid_config = {"top": screen_y, "left": screen_x, "width": final_w, "height": final_h}
                    with mss.MSS() as fresh_sct:
                        fresh_shot = cv2.cvtColor(np.array(fresh_sct.grab(grid_config)), cv2.COLOR_BGRA2BGR)
                    
                    board_matrix = []
                    for r in range(rows):
                        row_states = []
                        for c in range(cols):
                            x1 = int(c * cell_w_step)
                            y1 = int(r * cell_h_step)
                            x2 = int((c + 1) * cell_w_step)
                            y2 = int((r + 1) * cell_h_step)
                            row_states.append(identify_cell_state(fresh_shot[y1:y2, x1:x2]))
                        board_matrix.append(row_states)

                    # Dynamic draw sequence fires only when board pixels shift
                    if board_matrix != last_board_matrix[0]:
                        last_board_matrix[0] = board_matrix
                        canvas.delete("overlay")
                        
                        solver_map = compute_solver_overlay(board_matrix, rows, cols)
                        for r in range(rows):
                            for c in range(cols):
                                color_hex = solver_map[r][c]
                                if color_hex:
                                    x1 = int(c * cell_w_step)
                                    y1 = int(r * cell_h_step)
                                    x2 = int((c + 1) * cell_w_step)
                                    y2 = int((r + 1) * cell_h_step)
                                    canvas.create_rectangle(
                                        x1 + 3, y1 + 3, x2 - 3, y2 - 3, 
                                        outline=color_hex, width=3, 
                                        tags="overlay", state="normal"
                                    )

                # Fixed 100ms cycle interval polling frame tick
                root.after(100, check_inputs_and_update)

            root.after(100, check_inputs_and_update)
            root.mainloop()

            if app_signals["terminate"]:
                break
            if app_signals["recapture"]:
                time.sleep(0.3)
                continue

if __name__ == "__main__":
    main()