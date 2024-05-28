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

import json
import os
import re
import sys
import time
import utils
from mrequests import mrequests as requests

STOP_CHAR = "$StoP$"


def get_collection_query(collection, startdate, enddate):
    query = f"q=collection:({collection}) AND date:[{startdate} TO {enddate}]"
    query = query.replace(" ", "%20").replace(":", "%3A").replace("[", "%5B").replace("]", "%5D")
    return query


def get_collection_metadata(fields, collection, startdate, enddate, count=1000):
    base_url = "https://archive.org/services/search/v1/scrape"
    query = get_collection_query(collection, startdate, enddate)
    url = f"{base_url}?debug=false&xvar=production&total_only=false&count={count}&fields={fields}&q={query}"
    print(url)
    resp = None
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Error in request from {url}. Status code {resp.status_code}")
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
