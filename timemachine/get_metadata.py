from mrequests import mrequests as requests
import time

"""get_metadata.py
This is an example script which uses the mrequests package to get some metadata from archive.org.
I used this example to confirm that mrequests was working, and I learned a few gotchas here. 
NOTE I had to incread the MAX_READ_SIZE in order to pull the entire results. I'm not sure how
this will scale when we pull larger amounts of data.
"""


def make_parmstring(parms):
    parmstring = "&".join([f"{k}={v}" for k, v in parms.items()])
    parmstring = parmstring.replace(" ", "%20")
    parmstring = parmstring.replace(",", "%2C")
    parmstring = parmstring.replace(":", "%3A")
    return parmstring


api = "https://archive.org/services/search/v1/scrape"
parms = {
    "debug": "false",
    "xvar": "production",
    "total_only": "true",
    "count": "100",
    "fields": "identifier,item_count,collection_size,downloads,num_favorites",
    "q": "collection:etree AND mediatype:collection",
}
parmstring = make_parmstring(parms)

# true_url = "https://archive.org/services/search/v1/scrape?debug=false&xvar=production&total_only=true&count=100&fields=identifier%2Citem_count%2Ccollection_size%2Cdownloads%2Cnum_favorites&q=collection%3Detree%20AND%20mediatype%3Acollection"
# From https://archive.org/services/swagger/
url = api + "?" + parmstring
print(f"URL is {url}")
r = requests.get(url)

print(r.json())

r.close()

parms["q"] = "collection:GratefulDead"
parms["fields"] = "identifier"
parms["total_only"] = "false"
parmstring = make_parmstring(parms)
url = f"{api}?{parmstring}"
print(f"URL is {url}")

requests.MAX_READ_SIZE = 16 * 1024  # Could I avoid this by setting chunked to true (in the header)?
print(f"Max read size is {requests.MAX_READ_SIZE}")

r = requests.get(url)

json_text = ""
try:
    json_text = r.json()
except:
    print("Failed to parse json. Probably because the MAX_READ_SIZE limited the output")
    content = r.content
    print(content)

r.close()
