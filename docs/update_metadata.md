# Update Metadata

## Source the Environment

```{}
: ~/projects/deadstream ; source /home/steve/myenv/bin/activate
: /home/steve/myenv ~/projects/deadstream ; ipython
In [1]: import os
   ...: import time
   ...: from threading import Event
   ...: 
   ...: from timemachine import Archivary
   ...: from timemachine import config
   ...: from timemachine import GD
In [2]: aa = Archivary.Archivary(collection_list=["GratefulDead"],reload_ids=True)
```

This will write the metadata to the folder `/home/steve/projects/deadstream/timemachine/metadata/GratefulDead_ids`

Upload this to the Google Cloud in the browser.

## Artists to Update

- BillyStrings
- JoeRussosAlmostDead
- Phish
- DeadAndCompany
- TedeschiTrucksBand

`aa = Archivary.Archivary(collection_list=["JoeRussosAlmostDead","Phish","BillyStrings","DeadAndCompany"],reload_ids=True)`

## Other requirments on updating Metadata

In case the metadata is stale, ie, the URLs are no longer valid, we need to delete the files in the `tapes` cloud folder:
<https://console.cloud.google.com/storage/browser/spertilo-data/tapes>

## Bash script

: (myenv) /home/steve/myenv ~/projects/deadstream ; bash ./update_cloud_meta.sh -c "Phish DeadAndCompany BillyStrings TedeschiTrucksBand"

## Regenerate the vcs files

For example <https://storage.googleapis.com/spertilo-data/vcs/Phish_vcs.json> contains the list of shows Phish has done. It is constructed from the metadata uploaded in the previous step (the _ids files).

We can delete the `*_vcs.json` files in order to force the server to re-generate them the next time someone looks for it.

Or, we can force the server to refresh them using the service at <https://gratefuldeadtimemachine.com/vcs/Phish>
