# pico_controller/main.py
import time
from machine import Pin, I2C, UART
import ssd1306

# --- 1. Hardware Setup ---
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# UART0 on GP0 (TX) and GP1 (RX) connected to Pi Zero GPIO 15 (RX) and GPIO 14 (TX)
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

# Input Pins (Active LOW with internal pull-ups)
pin_up_clk = Pin(14, Pin.IN, Pin.PULL_UP)
pin_dn_dt = Pin(15, Pin.IN, Pin.PULL_UP)
pin_select = Pin(16, Pin.IN, Pin.PULL_UP)

# --- 2. Controller State ---
presets = [(0, "Connecting...")]
selected_idx = 0
active_name = "None"
last_clk = pin_up_clk.value()
last_btn_time = 0


def draw_ui():
    oled.fill(0)
    # Header bar showing currently active matrix display
    oled.fill_rect(0, 0, 128, 12, 1)
    oled.text("NOW:" + active_name[:12], 2, 2, 0)

    # Draw scrollable list of 4 visible presets
    total = len(presets)
    start = max(0, min(selected_idx - 1, total - 4))
    for row, i in enumerate(range(start, min(start + 4, total))):
        y = 16 + (row * 12)
        p_id, p_name = presets[i]
        if i == selected_idx:
            oled.fill_rect(0, y - 1, 128, 11, 1)
            oled.text(">" + p_name[:15], 2, y, 0)
        else:
            oled.text(" " + p_name[:15], 2, y, 1)

    oled.show()


def parse_serial_line(line: str):
    global presets, selected_idx, active_name
    if line.startswith("PRESETS:"):
        raw_list = line.split(":", 1)[1]
        new_presets = []
        for item in raw_list.split("|"):
            if ":" in item:
                idx_str, name = item.split(":", 1)
                new_presets.append((int(idx_str), name))
        if new_presets:
            presets = new_presets
            selected_idx = min(selected_idx, len(presets) - 1)
            draw_ui()
    elif line.startswith("ACTIVE:"):
        active_name = line.split(":", 1)[1]
        draw_ui()


# Request initial list from Pi Zero on boot
draw_ui()
uart.write(b"LIST\n")
rx_buffer = ""

# --- 3. Main Event Loop ---
while True:
    # A. Check incoming UART data from Pi Zero
    if uart.any():
        chunk = uart.read().decode("utf-8", "ignore")
        rx_buffer += chunk
        while "\n" in rx_buffer:
            line, rx_buffer = rx_buffer.split("\n", 1)
            parse_serial_line(line.strip())

    # B. Poll Rotary Encoder / Up-Down Buttons
    clk_val = pin_up_clk.value()
    if clk_val != last_clk and clk_val == 0:
        if pin_dn_dt.value() != clk_val:
            selected_idx = (selected_idx + 1) % len(presets)
        else:
            selected_idx = (selected_idx - 1) % len(presets)
        draw_ui()
        time.sleep_ms(5)
    last_clk = clk_val

    # C. Poll Select Button (Debounced)
    if pin_select.value() == 0:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_btn_time) > 250:
            last_btn_time = now
            preset_id, preset_name = presets[selected_idx]
            active_name = "Loading..."
            draw_ui()
            uart.write(f"RUN:{preset_id}\n".encode("utf-8"))

    time.sleep_ms(2)