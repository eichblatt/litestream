# Display driver: https://github.com/russhughes/st7789_mpy
import json
import os
import time

import config as TMB

TMB.load_options()


print("Starting...")


def main_loop(col_dict):
    year_old = -1
    month_old = -1
    day_old = -1
    date_old = ""
    pPower_old = False
    pSelect_old = False
    pPlayPause_old = False
    pStop_old = False
    pRewind_old = False
    pFFwd_old = False
    pYSw_old = False
    pMSw_old = False
    pDSw_old = False
    stage_date_color = TMB.st7789.color565(255, 255, 0)

    while True:

        if pPower_old != TMB.pPower.value():
            pPower_old = TMB.pPower.value()
            TMB.pLED.value(TMB.PowerLED)
            if pPower_old:
                TMB.tft.fill_circle(5 + 8, 108 + 8, 8, TMB.st7789.BLUE)
                print("Power UP")
            else:
                TMB.PowerLED = not TMB.PowerLED
                TMB.tft.fill_circle(5 + 8, 108 + 8, 8, TMB.st7789.WHITE)
                print("Power DOWN")

        if pSelect_old != TMB.pSelect.value():
            pSelect_old = TMB.pSelect.value()
            if pSelect_old:
                TMB.tft.rect(105, 108, 16, 16, TMB.st7789.BLUE)
                print("Select UP")
            else:
                TMB.tft.rect(105, 108, 16, 16, TMB.st7789.WHITE)
                print("Select DOWN")

        if pPlayPause_old != TMB.pPlayPause.value():
            pPlayPause_old = TMB.pPlayPause.value()
            if pPlayPause_old:
                TMB.tft.fill_polygon(TMB.PlayPausePoly, 130, 108, TMB.st7789.BLUE)
                print("PlayPause UP")
            else:
                TMB.tft.fill_polygon(TMB.PlayPausePoly, 130, 108, TMB.st7789.WHITE)
                print("PlayPause DOWN")

        if pStop_old != TMB.pStop.value():
            pStop_old = TMB.pStop.value()
            if pStop_old:
                TMB.tft.fill_rect(55, 108, 16, 16, TMB.st7789.BLUE)
                print("Stop UP")
            else:
                TMB.tft.fill_rect(55, 108, 16, 16, TMB.st7789.WHITE)
                print("Stop DOWN")

        if pRewind_old != TMB.pRewind.value():
            pRewind_old = TMB.pRewind.value()
            if pRewind_old:
                TMB.tft.fill_polygon(TMB.RewPoly, 30, 108, TMB.st7789.BLUE)
                print("Rewind UP")
            else:
                TMB.tft.fill_polygon(TMB.RewPoly, 30, 108, TMB.st7789.WHITE)
                print("Rewind DOWN")

        if pFFwd_old != TMB.pFFwd.value():
            pFFwd_old = TMB.pFFwd.value()
            if pFFwd_old:
                TMB.tft.fill_polygon(TMB.FFPoly, 80, 108, TMB.st7789.BLUE)
                print("FFwd UP")
            else:
                TMB.tft.fill_polygon(TMB.FFPoly, 80, 108, TMB.st7789.WHITE)
                print("FFwd DOWN")

        if pYSw_old != TMB.pYSw.value():
            pYSw_old = TMB.pYSw.value()
            if pYSw_old:
                TMB.tft.text(TMB.sfont, "Y", 60, 60, TMB.st7789.WHITE, TMB.st7789.BLUE)
                print("Year UP")
            else:
                TMB.tft.text(TMB.sfont, "Y", 60, 60, TMB.st7789.BLUE, TMB.st7789.WHITE)
                print("Year DOWN")

        if pMSw_old != TMB.pMSw.value():
            pMSw_old = TMB.pMSw.value()
            if pMSw_old:
                TMB.tft.text(TMB.sfont, "M", 0, 60, TMB.st7789.WHITE, TMB.st7789.BLUE)
                print("Month UP")
            else:
                TMB.tft.text(TMB.sfont, "M", 0, 60, TMB.st7789.BLUE, TMB.st7789.WHITE)
                print("Month DOWN")

        if pDSw_old != TMB.pDSw.value():
            pDSw_old = TMB.pDSw.value()
            if pDSw_old:
                TMB.tft.text(TMB.sfont, "D", 30, 60, TMB.st7789.WHITE, TMB.st7789.BLUE)
                print("Day UP")
            else:
                TMB.tft.text(TMB.sfont, "D", 30, 60, TMB.st7789.BLUE, TMB.st7789.WHITE)
                print("Day DOWN")

        year_new = TMB.y.value()
        month_new = TMB.m.value()
        day_new = TMB.d.value()
        date_new = f"{month_new}-{day_new}-{year_new}"

        if year_old != year_new:
            year_old = year_new
            TMB.tft.text(TMB.font, f"{year_new}", 90, 0, stage_date_color, TMB.st7789.BLACK)
            print("year =", year_new)

        if month_old != month_new:
            month_old = month_new
            TMB.tft.text(TMB.font, f"{month_new:2d}-", 0, 0, stage_date_color, TMB.st7789.BLACK)
            print("month =", month_new)

        if day_old != day_new:
            day_old = day_new
            TMB.tft.text(TMB.font, f"{day_new:2d}-", 43, 0, stage_date_color, TMB.st7789.BLACK)
            print("day =", day_new)

        if date_old != date_new:
            date_old = date_new
            key_date = f"{year_new}-{month_new:02d}-{day_new:02d}"
            print(f"date = {date_new} or {key_date}")
            try:
                vcs = col_dict["GratefulDead"][f"{year_new}-{month_new:02d}-{day_new:02d}"]
                print(vcs)
                TMB.tft.text(TMB.sfont, f"{vcs}", 0, 30, stage_date_color, TMB.st7789.BLACK)
            except KeyError:
                TMB.tft.text(TMB.sfont, f"               ", 0, 30, stage_date_color, TMB.st7789.BLACK)
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
    col_dict = {}
    for col in TMB.optd["COLLECTIONS"]:
        col_dict[col] = load_col(col)

    print(f"Loaded collections {col_dict.keys()}")

    main_loop(col_dict)


# col_dict = main()
# lookup_date("1994-07-31", col_dict)
main()
