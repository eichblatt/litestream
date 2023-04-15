import json
import os
import Archivary
import config


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
        print(f"Collection {col}")
        a = Archivary.Archivary(collection_list=[col])
        ids_path = f"metadata/{col}_ids/tiny.json"
        data = {d: a.tape_dates[d][0].venue() for d in a.dates}
        with open(ids_path, "w") as f:
            json.dump(data, f)
        print(f"Collection {col} Written to {ids_path}")
        col_dict[col] = data
    return col_dict


col_dict = main()
lookup_date("1994-07-31", col_dict)
