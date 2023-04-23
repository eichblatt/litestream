# Display driver: https://github.com/russhughes/st7789_mpy
import json
import os
import time
import network
import time
import mrequests

import config
import controls


config.load_options()


def connect_network():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    # wifi.scan()  # Scan for available access points
    if not wifi.isconnected():
        wifi.connect("fiosteve", "Fwest5%maini")  # Connect to an AP
    wifi.isconnected()  # Check for successful connection


print("Starting...")


def clear_area(controls, x, y, width, height):
    controls.tft.fill_rect(x, y, width, height, controls.st7789.BLACK)


def clear_screen(controls):
    clear_area(controls, 0, 0, 160, 128)


def set_date(controls, date):
    controls.y._value = int(date[:4])
    controls.m._value = int(date[5:7])
    controls.d._value = int(date[8:10])
    key_date = f"{controls.y.value()}-{controls.m.value():02d}-{controls.d.value():02d}"
    return key_date


def main_loop(col_dict):
    year_old = -1
    month_old = -1
    day_old = -1
    date_old = ""
    pPower_old = True
    pSelect_old = False
    pPlayPause_old = False
    pStop_old = False
    pRewind_old = False
    pFFwd_old = False
    pYSw_old = False
    pMSw_old = False
    pDSw_old = False
    stage_date_color = controls.st7789.color565(255, 255, 0)
    clear_screen(controls)

    while True:

        if pPower_old != controls.pPower.value():
            pPower_old = controls.pPower.value()
            controls.pLED.value(controls.PowerLED)
            controls.tft.off() if not controls.PowerLED else controls.tft.on()
            if pPower_old:
                controls.tft.fill_circle(5 + 8, 108 + 8, 8, controls.st7789.BLUE)
                print("Power UP")
            else:
                controls.PowerLED = not controls.PowerLED
                controls.tft.fill_circle(5 + 8, 108 + 8, 8, controls.st7789.WHITE)
                print("Power DOWN")

        if pSelect_old != controls.pSelect.value():
            pSelect_old = controls.pSelect.value()
            if pSelect_old:
                controls.tft.rect(105, 108, 16, 16, controls.st7789.BLUE)
                print("Select UP")
            else:
                controls.tft.rect(105, 108, 16, 16, controls.st7789.WHITE)
                print("Select DOWN")

        if pPlayPause_old != controls.pPlayPause.value():
            pPlayPause_old = controls.pPlayPause.value()
            if pPlayPause_old:
                controls.tft.fill_polygon(controls.PlayPausePoly, 130, 108, controls.st7789.BLUE)
                print("PlayPause UP")
            else:
                controls.tft.fill_polygon(controls.PlayPausePoly, 130, 108, controls.st7789.WHITE)
                print("PlayPause DOWN")

        if pStop_old != controls.pStop.value():
            pStop_old = controls.pStop.value()
            if pStop_old:
                controls.tft.fill_rect(55, 108, 16, 16, controls.st7789.BLUE)
                print("Stop UP")
            else:
                controls.tft.fill_rect(55, 108, 16, 16, controls.st7789.WHITE)
                print("Stop DOWN")

        if pRewind_old != controls.pRewind.value():
            pRewind_old = controls.pRewind.value()
            if pRewind_old:
                controls.tft.fill_polygon(controls.RewPoly, 30, 108, controls.st7789.BLUE)
                print("Rewind UP")
            else:
                controls.tft.fill_polygon(controls.RewPoly, 30, 108, controls.st7789.WHITE)
                print("Rewind DOWN")

        if pFFwd_old != controls.pFFwd.value():
            pFFwd_old = controls.pFFwd.value()
            if pFFwd_old:
                controls.tft.fill_polygon(controls.FFPoly, 80, 108, controls.st7789.BLUE)
                print("FFwd UP")
            else:
                controls.tft.fill_polygon(controls.FFPoly, 80, 108, controls.st7789.WHITE)
                print("FFwd DOWN")

        if pYSw_old != controls.pYSw.value():
            pYSw_old = controls.pYSw.value()
            if pYSw_old:
                controls.tft.text(controls.sfont, "Y", 60, 70, controls.st7789.WHITE, controls.st7789.BLUE)
                print("Year UP")
            else:
                # cycle through Today In History (once we know what today is!)
                controls.tft.text(controls.sfont, "Y", 60, 70, controls.st7789.BLUE, controls.st7789.WHITE)
                print("Year DOWN")

        if pMSw_old != controls.pMSw.value():
            pMSw_old = controls.pMSw.value()
            if pMSw_old:
                controls.tft.text(controls.sfont, "M", 0, 70, controls.st7789.WHITE, controls.st7789.BLUE)
                print("Month UP")
            else:
                controls.tft.text(controls.sfont, "M", 0, 70, controls.st7789.BLUE, controls.st7789.WHITE)
                print("Month DOWN")

        if pDSw_old != controls.pDSw.value():
            pDSw_old = controls.pDSw.value()
            if pDSw_old:
                controls.tft.text(controls.sfont, "D", 30, 70, controls.st7789.WHITE, controls.st7789.BLUE)
                print("Day UP")
            else:
                for date in sorted(col_dict["GratefulDead"].keys()):
                    if date > key_date:
                        key_date = set_date(controls, date)
                        break
                controls.tft.text(controls.sfont, "D", 30, 70, controls.st7789.BLUE, controls.st7789.WHITE)
                print("Day DOWN")

        year_new = controls.y.value()
        month_new = controls.m.value()
        day_new = controls.d.value()
        date_new = f"{month_new}-{day_new}-{year_new}"
        key_date = f"{year_new}-{month_new:02d}-{day_new:02d}"

        if year_old != year_new:
            year_old = year_new
            controls.tft.text(controls.font, f"{year_new}", 90, 0, stage_date_color, controls.st7789.BLACK)
            print("year =", year_new)

        if month_old != month_new:
            month_old = month_new
            controls.tft.text(controls.font, f"{month_new:2d}-", 0, 0, stage_date_color, controls.st7789.BLACK)
            print("month =", month_new)

        if day_old != day_new:
            day_old = day_new
            controls.tft.text(controls.font, f"{day_new:2d}-", 43, 0, stage_date_color, controls.st7789.BLACK)
            print("day =", day_new)

        if date_old != date_new:
            date_old = date_new
            print(f"date = {date_new} or {key_date}")
            try:
                vcs = col_dict["GratefulDead"][f"{key_date}"]
                print(vcs)
                clear_area(controls, 0, 25, 160, 32)
                vcs_len = controls.tft.draw(controls.roman_font, f"{vcs}", 0, 40, stage_date_color, 0.65)
                # controls.tft.write(controls.prop_font, f"{vcs}", 0, 30, stage_date_color, controls.st7789.BLACK)
                # controls.tft.text(controls.sfont, f"{vcs}", 0, 30, stage_date_color, controls.st7789.BLACK)
            except KeyError:
                clear_area(controls, 0, 25, 160, 32)
                pass
        # time.sleep_ms(50)


def load_col(col):
    ids_path = f"metadata/{col}_ids/tiny.json"
    print(f"Loading collection {col} from {ids_path}")
    data = json.load(open(ids_path, "r"))
    return data


def lookup_date(d, col_d):
    response = []
    for col, data in col_d.items():
        if d in data.keys():
            response.append([col, data[d]])
    return response


def main():
    """
    This script will load a super-compressed version of the
    date, artist, venue, city, state.
    """
    controls.tft.draw(controls.gothic_font, f"Grateful Dead", 0, 30, controls.st7789.color565(255, 255, 0), 0.8)
    controls.tft.draw(controls.gothic_font, f"Time Machine", 0, 60, controls.st7789.color565(255, 255, 0), 0.8)
    controls.tft.draw(controls.gothic_font, f"Loading", 0, 90, controls.st7789.color565(255, 255, 0), 1)
    col_dict = {}
    for col in config.optd["COLLECTIONS"]:
        col_dict[col] = load_col(col)

    print(f"Loaded collections {col_dict.keys()}")

    main_loop(col_dict)


# col_dict = main()
# lookup_date("1994-07-31", col_dict)
main()
