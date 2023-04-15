import json
import os
import config

config.load_options()


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
    for col in config.optd["COLLECTIONS"]:
        col_dict[col] = load_col(col)
    return col_dict


# col_dict = main()
# lookup_date("1994-07-31", col_dict)
