import lgpio
import time

# GPIO Pin Definitions
X_PULSE, X_DIR, X_LIMIT = 17, 23, 22
Y_PULSE, Y_DIR, Y_LIMIT = 27, 24, 25

class SmartTurret:
    def __init__(self):
        try:
            self.h = lgpio.gpiochip_open(4) # Pi 5
        except:
            self.h = lgpio.gpiochip_open(0)
            
        for pin in [X_PULSE, X_DIR, Y_PULSE, Y_DIR]:
            lgpio.gpio_claim_output(self.h, pin)
        for pin in [X_LIMIT, Y_LIMIT]:
            lgpio.gpio_claim_input(self.h, pin, lgpio.SET_PULL_DOWN)

    def move_axis(self, axis, direction, steps=30):
        p_pin = X_PULSE if axis == 'x' else Y_PULSE
        d_pin = X_DIR if axis == 'x' else Y_DIR
        l_pin = X_LIMIT if axis == 'x' else Y_LIMIT

        if lgpio.gpio_read(self.h, l_pin): return

        lgpio.gpio_write(self.h, d_pin, direction)
        for _ in range(steps):
            lgpio.gpio_write(self.h, p_pin, 1)
            time.sleep(12/1_000_000)
            lgpio.gpio_write(self.h, p_pin, 0)
            time.sleep(1.0/1800)

    def cleanup(self):
        lgpio.gpiochip_close(self.h)
