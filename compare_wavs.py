import logging
import argparse
import numpy as np
from matplotlib import pyplot as plt


parser = argparse.ArgumentParser()
parser.add_argument("--path_clicks", default="/home/steve/data/tuningwithheader.wav", help="path to first wav file")
parser.add_argument("--path_good", default="/home/steve/data/gd1976-06-29d1t01.wav", help="path to second wav file")
parser.add_argument("--debug", type=int, default=1, help="If > 0, don't run the main script on loading")
parms, remainder = parser.parse_known_args()

click = None
good = None

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(name)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def find_close(arr, seq, thresh=2):
    Na, Nseq = arr.size, seq.size

    # Range of sequence
    r_seq = np.arange(Nseq)

    # Create a 2D array of sliding indices across the entire length of input array.
    # Match up with the input sequence & get the matching starting indices.
    diffs = arr[np.arange(Na - Nseq + 1)[:, None] + r_seq] - seq

    measures = diffs.std(1)
    best_shift = np.where((measures <= thresh) & (measures == min(measures)))[0][0]
    return best_shift


def find_match(arr, seq):
    Na, Nseq = arr.size, seq.size

    # Range of sequence
    r_seq = np.arange(Nseq)

    # Create a 2D array of sliding indices across the entire length of input array.
    # Match up with the input sequence & get the matching starting indices.
    M = (arr[np.arange(Na - Nseq + 1)[:, None] + r_seq] == seq).all(1)

    # Get the range of those indices as final output
    if M.any() > 0:
        return np.where(np.convolve(M, np.ones((Nseq), dtype=int)) > 0)[0]
    else:
        return []  # No match found


def show_bytes(start, n=10, shift=0):
    good_start = start + shift
    logger.info(f"click[{start:6d}:] {click[start : start + n]}")
    logger.info(f"good [{good_start:6d}:] {good[good_start: good_start + n]}")


def load_data():
    global good
    global click
    click = np.fromfile(parms.path_clicks, dtype=np.int16)
    good = np.fromfile(parms.path_good, dtype=np.int16)
    # Find first signal after header + other bs.
    click_start = 1200 + np.where(click[1200:] > 10)[0][0]
    click = click[click_start:]
    good_start = 1200 + np.where(good[1200:] > 10)[0][0]
    good = good[good_start : good_start + len(click)]


def main(parms):
    logger.info("In Main")
    load_data()
    plt.hist(good - click)


for k in parms.__dict__.keys():
    logger.info(f"{k:20s} : {parms.__dict__[k]}")

if __name__ == "__main__" and parms.debug == 0:
    main(parms)
