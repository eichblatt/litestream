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