#!/usr/bin/python3
import json
import logging
import optparse
import os
from pympler import asizeof

from timemachine import Archivary
from timemachine import config


parser = optparse.OptionParser()
parser.add_option("--debug", type="int", default=0, help="If > 0, don't run the main script on loading")
parser.add_option("--verbose", action="store_true", default=False, help="Print more verbose information")

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(name)s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

config.load_options()


def load_col(col):
    ids_path = os.path.join(config.ROOT_DIR, "metadata", f"{col}_ids", "tiny.json")
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
    This script will load an archive collection and save a super-compressed version of the
    date, artist, venue, city, state
    which can be loaded by the player to save memory.
    """
    col_dict = {}
    for col in config.optd["COLLECTIONS"]:
        logger.info(f"Collection {col}")
        a = Archivary.Archivary(collection_list=[col])
        ids_path = os.path.join(config.ROOT_DIR, "metadata", f"{col}_ids", "tiny.json")
        data = {d: a.tape_dates[d][0].venue() for d in a.dates}
        logger.info(f"Size of data for {col} is {asizeof.asizeof(data)/(1024*1024):.2f} MB")
        with open(ids_path, "w") as f:
            json.dump(data, f)
        logger.info(f"Collection {col} Written to {ids_path}")
        col_dict[col] = data
    return col_dict


if __name__ == "__main__":
    parms, remainder = parser.parse_args()
    for k in parms.__dict__.keys():
        logger.info(f"{k:20s} : {parms.__dict__[k]}")
    if parms.debug > 0:
        logger.setLevel(logging.DEBUG)

    col_dict = main()
    lookup_date("1994-07-31", col_dict)
