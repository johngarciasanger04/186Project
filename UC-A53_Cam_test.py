#!/usr/bin/env python3
import cv2
import mediapipe as mp
import lgpio
import time
import threading
import sys
import tty
import termios
import os
import select

# --- SYSTEM FIXES ---
os.environ["QT_QPA_PLATFORM"] = "xcb"

# GPIO Pins
X_PULSE, X_DIR, X_LIMIT = 17, 23, 22
Y_PULSE, Y_DIR, Y_LIMIT = 27, 24, 25

# Movement Settings
CONSTANT_SPEED = 1500 
PULSE_WIDTH = 12 / 1_000_000
DEADZONE = 20 
STEP_SIZE = 10 

class SmartTurret:
    def __init__(self):
        print("[DEBUG] Initializing GPIO...")
        try:
            self.h = lgpio.gpiochip_open(4) 
        except:
            self.h = lgpio.gpiochip_open(0)
            
        for pin in [X_PULSE, X_DIR, Y_PULSE, Y_DIR]:
            lgpio.gpio_claim_output(self.h, pin)
        for pin in [X_LIMIT, Y_LIMIT]:
            lgpio.gpio_claim_input(self.h, pin, lgpio.SET_PULL_DOWN)

        print("[DEBUG] Initializing AI Model...")
        self.detector = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.9)
        self.keep_running = True
        self.manual_active = False

    def move_axis(self, axis, direction):
        p_pin = X_PULSE if axis == 'x' else Y_PULSE
        d_pin = X_DIR if axis == 'x' else Y_DIR
        l_pin = X_LIMIT if axis == 'x' else Y_LIMIT

        if lgpio.gpio_read(self.h, l_pin): return

        lgpio.gpio_write(self.h, d_pin, direction)
        for _ in range(STEP_SIZE):
            lgpio.gpio_write(self.h, p_pin, 1)
            time.sleep(PULSE_WIDTH)
            lgpio.gpio_write(self.h, p_pin, 0)
            time.sleep(1.0/CONSTANT_SPEED)

    def cleanup(self):
        self.keep_running = False
        time.sleep(0.3)
        lgpio.gpiochip_close(self.h)

def keyboard_listener(turret):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while turret.keep_running:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    next_ch = sys.stdin.read(2)
                    turret.manual_active = True
                    if next_ch == '[C': turret.move_axis('x', 1) 
                    elif next_ch == '[D': turret.move_axis('x', 0) 
                    # --- MANUAL Y INVERSION ---
                    elif next_ch == '[A': turret.move_axis('y', 1) # Changed from 0 to 1
                    elif next_ch == '[B': turret.move_axis('y', 0) # Changed from 1 to 0
                    turret.manual_active = False
                elif ch in ['q', '\x03']:
                    turret.keep_running = False
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    os.system("stty echo icanon")
    turret = SmartTurret()

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened(): cap = cv2.VideoCapture(1, cv2.CAP_V4L2)
    
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    key_thread = threading.Thread(target=keyboard_listener, args=(turret,))
    key_thread.daemon = True
    key_thread.start()

    print("\n[SYSTEM ONLINE] AI Tracking Active. Y-Axis Inverted.")

    try:
        while cap.isOpened() and turret.keep_running:
            ret, frame = cap.read()
            if not ret: break
            
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = turret.detector.process(rgb)

            cv2.line(frame, (320,0), (320,480), (0,255,0), 1)
            cv2.line(frame, (0,240), (640,240), (0,255,0), 1)

            if results.detections and not turret.manual_active:
                for det in results.detections:
                    box = det.location_data.relative_bounding_box
                    cx, cy = int((box.xmin + box.width/2)*640), int((box.ymin + box.height/2)*480)
                    cv2.circle(frame, (cx, cy), 12, (0,0,255), 2)

                    err_x = cx - 320
                    err_y = cy - 240
                    
                    if err_x > DEADZONE: turret.move_axis('x', 1)
                    elif err_x < -DEADZONE: turret.move_axis('x', 0)

                    # --- AI Y INVERSION ---
                    if err_y > DEADZONE: 
                        turret.move_axis('y', 0) # Flipped logic
                    elif err_y < -DEADZONE: 
                        turret.move_axis('y', 1) # Flipped logic
            
            cv2.imshow('Turret Tracking', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

    except KeyboardInterrupt:
        pass
    finally:
        turret.keep_running = False
        if 'cap' in locals(): cap.release()
        cv2.destroyAllWindows()
        turret.cleanup()
        os.system("stty echo icanon")
