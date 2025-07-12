#
import machine
from machine import Pin, reset, Timer
import micropython

import time

micropython.alloc_emergency_exception_buf(100)

IGNORE_RESET = False
last_time_called = time.ticks_ms()

pPower = Pin(21, Pin.IN, Pin.PULL_UP)
pSelect = Pin(47, Pin.IN, Pin.PULL_UP)
print("Testing power button IRQ")


def power_cb(pin):
    global IGNORE_RESET
    global last_time_called
    print("In Power callback")

    if time.ticks_diff(time.ticks_ms(), last_time_called) < 1000:
        last_time_called = time.ticks_ms()
        return
    last_time_called = time.ticks_ms()
    for i in range(30):
        time.sleep_us(10)  # Wait for button to be released
        if pin.value() == 0:  # Button still pressed
            print("Button still pressed. Not rebooting")
            IGNORE_RESET = True

    if IGNORE_RESET:
        print("Ignoring reset ..... ")
        IGNORE_RESET = False
        return

    reset()


def allow_reset(_):
    global IGNORE_RESET
    IGNORE_RESET = True
    print("Reset will be ignored")
    # button_window.deinit()


pp_old = pPower.value()
ps_old = pSelect.value()
pPower.irq(power_cb, wake=machine.SLEEP | machine.DEEPSLEEP, trigger=Pin.IRQ_RISING)
button_window = Timer(1)
try:
    while True:
        if pPower.value() != pp_old:  # Power button state changed
            pp_old = not pp_old
            if pp_old == 0:  # Power button pressed
                print("Power button pressed")
                button_window.init(period=1_000, mode=Timer.ONE_SHOT, callback=allow_reset)
            elif pp_old == 1:  # Power button released
                print("Power button released")
                IGNORE_RESET = False

        if pSelect.value() != ps_old:  # Power button state changed
            raise RuntimeError("Select button pressed, exiting")

finally:
    IGNORE_RESET = False
