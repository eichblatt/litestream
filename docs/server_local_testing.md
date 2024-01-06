# Testing the Server Locally Before Deploying to the Cloud

## Running the app

app.py and app.yaml are in the cloud_server sub-folder of the deadstream repository.

in order to run them, first create a virtual python env in ~/projects/cld_srv folder, and activate it

```{}
: /home/steve/projects/cld_srv/env ~/projects/cld_srv ; python3 -m venv env
: /home/steve/projects/cld_srv/env ~/projects/cld_srv ; source env/bin/activate
: /home/steve/projects/cld_srv/env ~/projects/cld_srv ; pip install -r requirements.txt 
: /home/steve/projects/cld_srv/env ~/projects/cld_srv ; cp ../deadstream/cloud_server/app.py .
: /home/steve/projects/cld_srv/env ~/projects/cld_srv ; flask run
```
