from flask import Flask, request, jsonify, render_template, send_from_directory
import cv2
import numpy as np
from PIL import Image
import io
import base64

app = Flask(__name__)

# Basic Minesweeper solver (logic-based, not full CSP)
def solve_minesweeper(board, rows, cols):
    # board: 2D list, -1=unknown, 0-8=numbers, 9=mine (flagged)
    moves = []
    for i in range(rows):
        for j in range(cols):
            if board[i][j] == -1:  # unknown
                # Simple heuristic: check neighbors
                # For demo, suggest clicking unknowns with no flagged neighbors first
                flagged = sum(1 for di in [-1,0,1] for dj in [-1,0,1] 
                            if 0<=i+di<rows and 0<=j+dj<cols and board[i+di][j+dj]==9)
                if flagged == 0:
                    moves.append((i, j, "safe"))
    return moves[:5]  # top suggestions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/process', methods=['POST'])
def process_image():
    try:
        # Get image from base64
        data = request.json['image']
        img_data = base64.b64decode(data.split(',')[1])
        image = Image.open(io.BytesIO(img_data))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # TODO: Advanced CV here - grid detection, tile recognition
        # For starter: placeholder
        height, width = frame.shape[:2]
        
        # Dummy board for demo (replace with real CV)
        rows, cols = 9, 9
        board = [[-1 for _ in range(cols)] for _ in range(rows)]
        
        # Example: detect some numbers (you need to tune templates)
        # Use template matching for flags, numbers 1-8, closed tiles
        
        suggestions = solve_minesweeper(board, rows, cols)
        
        return jsonify({
            'status': 'success',
            'board_size': (rows, cols),
            'suggestions': suggestions,
            'message': 'Processed! Point camera at full board clearly.'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)