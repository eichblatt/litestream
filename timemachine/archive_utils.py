"""
litestream
Copyright (C) 2023  spertilo.net

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import gc
import json
import math
import random
import utils
from mrequests import mrequests as requests

STOP_CHAR = "$StoP$"


def count_collection(collection, date_range, other_conds=[]):
    print(f"in count_collection {collection}, {date_range}")
    date_range_string = f"[{date_range[0]} TO {date_range[1]}]"
    base_url = "https://archive.org/services/search/v1/scrape"
    query = get_collection_query(collection, date_range_string, other_conds)
    url = f"{base_url}?debug=false&xvar=production&total_only=true&q={query}"
    print(url)
    result = _get_collection_year_chunk(url)
    return result["total"]


def get_collection_query(collection, year, other_conds=[]):
    query = f"mediatype:audio AND collection:({collection}) AND year:{year}"
    for cond in other_conds:
        query += f" AND {cond}"
    query = (
        query.replace(" ", "%20")
        .replace(":", "%3A")
        .replace("[", "%5B")
        .replace("]", "%5D")
        .replace(",", "%2C")
        .replace('"', "%22")
        .replace("?", "%3F")
        .replace("^", "%5E")
        .replace("~", "%7E")
        .replace("&", "%26")
        .replace("$", "%24")
        .replace("<", "%3C")
        .replace(">", "%3E")
    )
    return query


def _get_data_from_archive(fields, query, count=None):
    if isinstance(fields, str):
        fields = [fields]
    field_str = "%2C".join(fields)
    n_items = 0
    total = 1
    cursor = ""
    result = {}
    batch_size = 10000 if count is None else min(count, 10000)
    base_url = "https://archive.org/services/search/v1/scrape"
    if isinstance(fields, str):
        fields = [fields]
    field_str = "%2C".join(fields)
    while n_items < total:
        if len(cursor) > 0:
            url = f"{base_url}?debug=false&xvar=production&total_only=false&count={batch_size}&cursor={cursor}&fields={field_str}&q={query}"
        else:
            url = f"{base_url}?debug=false&xvar=production&total_only=false&count={batch_size}&fields={field_str}&q={query}"
        print(url)
        j = _get_collection_year_chunk(url)
        n_items += int(j["count"])
        total = j["total"] if (count is None) else min(j["total"], count)
        cursor = j.get("cursor", "")
        print(f"{n_items}/{total} items downloaded")
        for item in j["items"]:
            for field in fields:
                if not field in result.keys():
                    result[field] = []
                result[field].append(item.get(field, None))
    return result


class ArchiveDownError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def _get_collection_year_chunk(url):
    resp = None
    try:
        resp = requests.get(url)
        if resp.status_code == 503:
            raise ArchiveDownError("Download Error from Archive.org")
        if resp.status_code != 200:
            print(f"Error in request from {url}. Status code {resp.status_code}")
            raise Exception("Unsuccessful download")
        if not resp.chunked:
            j = resp.json()
        else:
            resp.save("/tmp.json")
            j = json.load(open("/tmp.json", "r"))
    finally:
        utils.remove_file("/tmp.json")
        if resp is not None:
            resp.close()
    return j


def get_alphabet_bounds(center, radius):
    radius = abs(radius)
    print(f"alphabet_bounds {center}, {radius}")
    start_pos = max(center - radius, 0)
    end_pos = min(start_pos + 2 * radius, 1)
    if end_pos >= 1:
        end_pos = 0.999999
        start_pos = 0.999999 - 2 * radius

    def letters(f, n):
        return chr(97 + int(f * math.pow(26, n + 1) % 26))

    start_chars = "".join([letters(start_pos, i) for i in range(5)])
    end_chars = "".join([letters(end_pos, i) for i in range(5)])
    return start_chars, end_chars


def subset_collection(fields, collection, date_range, N_to_select, prefix=""):
    print("in subset_collection")
    date_range_string = f"[{date_range[0]} TO {date_range[1]}]"
    collection_size = count_collection(collection, date_range)
    print(f"in subset_collection -- size {collection_size}")
    max_size_to_pull = 10_000
    n_subsets = 5
    result_dict = {}
    if collection_size <= max_size_to_pull:
        query = get_collection_query(collection, date_range_string)
        data = _get_data_from_archive(fields, query)
        result_dict = data
    else:  # choose n_subsets, alphabetically, and combine them together.
        max_size_to_pull = 200 + max_size_to_pull // n_subsets
        min_size_to_pull = min(N_to_select * 5, max_size_to_pull - 100)
        for i in range(n_subsets):
            print(f"Looping, i is {i}")
            radius = 0.5 * max_size_to_pull / (collection_size + 1)
            center = random.random()
            start_chars, end_chars = get_alphabet_bounds(center, radius)
            start = f"{prefix}{start_chars if start_chars >= 'aa' else ''}"
            end = f"{prefix}{end_chars}"
            cond = f"identifier:[{start} TO {end}]"
            size = count_collection(collection, date_range, [cond])
            print(f"cond: {cond}. Size is {size}")
            i_tries = 0
            while ((size > max_size_to_pull) or (size < min_size_to_pull)) & (i_tries < 5):
                # radius = radius * max(min((max_size_to_pull / (2 * size + 1)), 2), math.pow(0.9, i_tries + 1))
                radius = radius * max(min((max_size_to_pull / (2 * size + 1)), 2), 0.8)
                start_chars, end_chars = get_alphabet_bounds(center, radius)
                start = f"{prefix}{start_chars if start_chars >= 'aa' else ''}"
                end = f"{prefix}{end_chars}"
                cond = f"identifier:[{start} TO {end}]"
                size = count_collection(collection, date_range, [cond])
                print(f"try {i_tries}. cond: {cond}. Size is {size}.")
                i_tries = i_tries + 1
            if size < N_to_select:
                print(f"WARNING only {size} ids match, skipping!")
                continue
            query = get_collection_query(collection, date_range_string, [cond])
            print(f"query: {query}")
            data = _get_data_from_archive(fields, query, count=min(size, max_size_to_pull))
            for key in data.keys():
                result_dict[key] = result_dict.get(key, []) + data[key]

    indices = utils.deal_n(list(range(len(result_dict[fields[0]]))), N_to_select)
    for key in result_dict.keys():
        result_dict[key] = [result_dict[key][i] for i in indices]
    return result_dict


def get_tape_metadata(identifier):
    url_metadata = f"https://archive.org/metadata/{identifier}"
    print(url_metadata)
    resp = None
    try:
        resp = requests.get(url_metadata)
        if resp.status_code != 200:
            print(f"Error in request from {url_metadata}. Status code {resp.status_code}")
            raise Exception("Download Error")
        if not resp.chunked:
            j = resp.json()
        else:
            resp.save("/tmp.json")
            j = json.load(open("/tmp.json", "r"))
    finally:
        utils.remove_file("/tmp.json")
        if resp is not None:
            resp.close()

    return j


def get_request(url, outpath="/tmp.json"):
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Failed to load from {url}")
        return {}
    if resp.chunked:
        print(f"saving json to {outpath}")
        resp.save(outpath)
        resp.close()
        gc.collect()
        metadata = json.load(open(outpath, "r"))
    elif len(resp.text) > 1_000_000:
        print("saving json to /tmp.json")
        with open("/tmp.json", "w") as f:
            f.write(resp.text)
        resp.close()
        gc.collect()
        metadata = utils.read_json("/tmp.json")
        utils.remove_file("/tmp.json")
    else:
        metadata = resp.json()

    return metadata
