#!/usr/bin/env python3
import lgpio
import time
import sys
import tty
import termios
import threading
import os

# GPIO Pin Definitions
PULSE_PIN = 17   
DIR_PIN = 23     
LIMIT_PIN = 22   # Active HIGH Input

# Motor Configuration
PULSE_WIDTH = 12 / 1_000_000
CONSTANT_SPEED = 1500  

class SmoothStepper:
    def __init__(self):
        # Open chip 4 for Pi 5
        self.h = lgpio.gpiochip_open(4)
        
        # Configure Outputs
        lgpio.gpio_claim_output(self.h, PULSE_PIN)
        lgpio.gpio_claim_output(self.h, DIR_PIN)
        
        # Configure Input: GPIO 22 with Internal Pull-Down
        lgpio.gpio_claim_input(self.h, LIMIT_PIN, lgpio.SET_PULL_DOWN)
        
        self.running = False
        self.direction = 1
        self.pulse_thread = None

    def is_limit_hit(self):
        """Returns True if GPIO 22 is receiving 3.3V (Active HIGH)"""
        return lgpio.gpio_read(self.h, LIMIT_PIN) == 1

    def _pulse_worker(self):
        """Background worker monitoring the limit switch"""
        delay = (1.0 / CONSTANT_SPEED) - PULSE_WIDTH
        while self.running:
            # STOP IMMEDIATELY if limit pin goes HIGH
            if self.is_limit_hit():
                print("\n[!] SAFETY STOP: Limit Switch Triggered.")
                self.running = False
                break
                
            lgpio.gpio_write(self.h, DIR_PIN, self.direction)
            lgpio.gpio_write(self.h, PULSE_PIN, 1)
            time.sleep(PULSE_WIDTH)
            lgpio.gpio_write(self.h, PULSE_PIN, 0)
            time.sleep(max(0, delay))

    def start_moving(self, direction):
        # Prevent starting if limit is already hit
        if self.is_limit_hit():
            print("\r[!] LIMIT ACTIVE: Clear switch to move.    ", end="")
            return

        if not self.running:
            self.direction = direction
            self.running = True
            self.pulse_thread = threading.Thread(target=self._pulse_worker)
            self.pulse_thread.daemon = True
            self.pulse_thread.start()

    def stop_moving(self):
        self.running = False
        if self.pulse_thread:
            self.pulse_thread.join()
            self.pulse_thread = None

    def cleanup(self):
        self.stop_moving()
        if hasattr(self, 'h'):
            lgpio.gpiochip_close(self.h)

def get_key():
    """Captures keypresses for terminal navigation"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            next_ch = sys.stdin.read(2)
            if next_ch == '[C': return "right"
            if next_ch == '[D': return "left"
            return "esc"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    motor = SmoothStepper()
    print("--- MOTOR CONTROL: LIMIT SWITCH ACTIVE ---")
    print("Right Arrow: CW | Left Arrow: CCW | Space: Stop | Q: Quit")
    print("-" * 50)

    try:
        while True:
            key = get_key()
            
            if key == "right":
                motor.start_moving(1)
                print("\r→ Moving CW          ", end="", flush=True)
            elif key == "left":
                motor.start_moving(0)
                print("\r← Moving CCW         ", end="", flush=True)
            elif key == " " or key == "s":
                motor.stop_moving()
                print("\rSTOPPED              ", end="", flush=True)
            elif key in ['q', 'esc', '\x03']:
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        motor.cleanup()
        # Correct command to restore terminal visibility and behavior
        os.system("stty echo icanon") 
        print("\nProgram Exited Successfully.")


