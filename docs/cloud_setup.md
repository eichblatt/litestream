# Cloud setup

spertilo
cloud.google.com
install gcloud 

sudo apt-get install apt-transport-https ca-certificates gnupg curl sudo

https://cloud.google.com/sdk/docs/install#deb


# Usage
(env) steve@prim:~/deadstream$ gcloud storage buckets list

(env) steve@prim:~$ gcloud storage cp GratefulDead_vcs.json gs://spertilo-data/vcs/GratefulDead_vcs.json

# App Engine
A product that _might_ run the flask app

# Note

Locatiuon of bucket in cloud 
https://console.cloud.google.com/storage/browser/spertilo-data;tab=objects?project=able-folio-397115&prefix=&forceOnObjectsSortingFiltering=false

#Public URL 
https://storage.googleapis.com/spertilo-data/vcs/GratefulDead_vcs.json

# Running the app

I want to move the app.py and app.yaml into a sub-folder. Also include requirements.txt in that folder. The requirements will include the deadstream project (api_server branch if necessary).

it is running on https://able-folio-397115.ue.r.appspot.com/

# Google cloud python module


# Also
github copilot extension in vscode
