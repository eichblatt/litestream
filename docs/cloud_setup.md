# Cloud setup

spertilo
cloud.google.com

```{}
install gcloud 

sudo apt-get install apt-transport-https ca-certificates gnupg curl sudo
```

<https://cloud.google.com/sdk/docs/install#deb>

then gcloud init

## Usage

```{}
(env) steve@prim:~/deadstream$ gcloud storage buckets list

(env) steve@prim:~$ gcloud storage cp GratefulDead_vcs.json gs://spertilo-data/vcs/GratefulDead_vcs.json
```

## App Engine

A product that runs the flask app.

### Deploying the service

First, authenticate:

`(env) : ~/projects/deadstream/cloud_server ; gcloud auth application-default login`

 This opened a browser, which I needed to log into to authenticate. Will this work without authentication from within the google cloud?

Install the app locally in a tmp folder (so that we don't upload the _entire repository_ to the google cloud)

`(env) : ~/projects/deadstream/ ; cp -R cloud_server tmp`
`(env) : ~/projects/deadstream/ ; cd tmp`
`(env) : ~/projects/deadstream/tmp ; pip install -r requirements.txt`

Test the local version, if you want to make sure it does what it is supposed to:

`(env) : ~/projects/deadstream/tmp ; flask run`

Go back to the cloud_server folder and deploy from there.
Then deploy (this takes forever, but it works)

`: ~/projects/deadstream/cloud_server ; gcloud app deploy [--version=<name> --verbosity=info]`

#### NOTE it seems like I need to authenticate and keep the browser open to run this?

See the server at <https://console.cloud.google.com/appengine/services?serviceId=default&versionId=20230826t203020&authuser=1&project=able-folio-397115>

also, gcloud app browse should open the server in the browser.

## Deleting the Staging bucket (by mistake)

I deleted the staging bucket, and had to re-create it before I could deploy the app again.
This is the command to repair it:

`: ~/projects/deadstream/cloud_server ; gcloud beta app repair`
Whew!

## Note

Location of bucket in cloud
<https://console.cloud.google.com/storage/browser/spertilo-data;tab=objects?project=able-folio-397115&prefix=&forceOnObjectsSortingFiltering=false>

## Public URL

<https://storage.googleapis.com/spertilo-data/vcs/GratefulDead_vcs.json>

## Credentials

saved to /home/steve/.config/gcloud/application_default_credentials.json

## Running the app

I want to move the app.py and app.yaml into a sub-folder. Also include requirements.txt in that folder. The requirements will include the deadstream project (api_server branch if necessary).

it is running on <https://able-folio-397115.ue.r.appspot.com/>

API = "<https://able-folio-397115.ue.r.appspot.com>"

## Google cloud python module

See <https://github.com/googleapis/python-storage/blob/main/samples/snippets/storage_activate_hmac_key.py>

`pip install google-cloud-storage`

## Authentication

`(env) : ~/projects/deadstream/cloud_server ; gcloud auth application-default login`

 This opened a browser, which I needed to log into to authenticate. Will this work without authentication from within the google cloud?

within python:

```{}
In [8]: from google.cloud import storage
In [7]: storage_client = storage.Client(project='able-folio-397115')
```

## Example of copying a file

<https://github.com/googleapis/python-storage/blob/main/samples/snippets/storage_copy_file.py>

## Functions I will probably need

### Download a blob (file)

```{}
# [START storage_download_file]
from google.cloud import storage


def download_blob(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"

    # The ID of your GCS object
    # source_blob_name = "storage-object-name"

    # The path to which the file should be downloaded
    # destination_file_name = "local/path/to/file"

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)

    # Construct a client side representation of a blob.
    # Note `Bucket.blob` differs from `Bucket.get_blob` as it doesn't retrieve
    # any content from Google Cloud Storage. As we don't need additional data,
    # using `Bucket.blob` is preferred here.
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)

    print(
        "Downloaded storage object {} from bucket {} to local file {}.".format(
            source_blob_name, bucket_name, destination_file_name
        )
    )


# [END storage_download_file]
```

### Write a blob

```{}
# [START storage_file_upload_from_memory]
from google.cloud import storage


def upload_blob_from_memory(bucket_name, contents, destination_blob_name):
    """Uploads a file to the bucket."""

    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"

    # The contents to upload to the file
    # contents = "these are my contents"

    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_string(contents)

    print(
        f"{destination_blob_name} with contents {contents} uploaded to {bucket_name}."
    )

# [END storage_file_upload_from_memory]
```

### Delete a blob (file)

```{}
# [START storage_delete_file]
from google.cloud import storage


def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    # bucket_name = "your-bucket-name"
    # blob_name = "your-object-name"

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    generation_match_precondition = None

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to delete is aborted if the object's
    # generation number does not match your precondition.
    blob.reload()  # Fetch blob metadata to use in generation_match_precondition.
    generation_match_precondition = blob.generation

    blob.delete(if_generation_match=generation_match_precondition)

    print(f"Blob {blob_name} deleted.")


# [END storage_delete_file]
```

### Make a file publicly available

```{}
# [START storage_make_public]
from google.cloud import storage

def make_blob_public(bucket_name, blob_name):
    """Makes a blob publicly accessible."""
    # bucket_name = "your-bucket-name"
    # blob_name = "your-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.make_public()

    print(
        f"Blob {blob.name} is publicly accessible at {blob.public_url}"
    )


# [END storage_make_public]
```

### Move a file (to a new bucket, optionally)

```{}
# [START storage_move_file]
from google.cloud import storage

def move_blob(bucket_name, blob_name, destination_bucket_name, destination_blob_name,):
    """Moves a blob from one bucket to another with a new name."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The ID of your GCS object
    # blob_name = "your-object-name"
    # The ID of the bucket to move the object to
    # destination_bucket_name = "destination-bucket-name"
    # The ID of your new GCS object (optional)
    # destination_blob_name = "destination-object-name"

    storage_client = storage.Client()

    source_bucket = storage_client.bucket(bucket_name)
    source_blob = source_bucket.blob(blob_name)
    destination_bucket = storage_client.bucket(destination_bucket_name)

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request is aborted if the object's
    # generation number does not match your precondition. For a destination
    # object that does not yet exist, set the if_generation_match precondition to 0.
    # If the destination object already exists in your bucket, set instead a
    # generation-match precondition using its generation number.
    # There is also an `if_source_generation_match` parameter, which is not used in this example.
    destination_generation_match_precondition = 0

    blob_copy = source_bucket.copy_blob(
        source_blob, destination_bucket, destination_blob_name, if_generation_match=destination_generation_match_precondition,
    )
    source_bucket.delete_blob(blob_name)

    print(
        "Blob {} in bucket {} moved to blob {} in bucket {}.".format(
            source_blob.name,
            source_bucket.name,
            blob_copy.name,
            destination_bucket.name,
        )
    )


# [END storage_move_file]
```

### List all files in a bucket

```{}
# [START storage_list_files]
from google.cloud import storage


def list_blobs(bucket_name):
    """Lists all the blobs in the bucket."""
    # bucket_name = "your-bucket-name"

    storage_client = storage.Client()

    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket_name)

    # Note: The call returns a response only when the iterator is consumed.
    for blob in blobs:
        print(blob.name)


# [END storage_list_files]
```

### List all files in a bucket using a prefix filter

See <https://cloud.google.com/storage/docs/samples/storage-list-files-with-prefix>

```{}
def list_blobs_with_prefix(bucket_name, prefix, delimiter=None):
    """Lists all the blobs in the bucket that begin with the prefix.

    This can be used to list all blobs in a "folder", e.g. "public/".

    The delimiter argument can be used to restrict the results to only the
    "files" in the given "folder". Without the delimiter, the entire tree under
    the prefix is returned. For example, given these blobs:

        a/1.txt
        a/b/2.txt

    If you specify prefix ='a/', without a delimiter, you'll get back:

        a/1.txt
        a/b/2.txt

    However, if you specify prefix='a/' and delimiter='/', you'll get back
    only the file directly under 'a/':

        a/1.txt

    As part of the response, you'll also get back a blobs.prefixes entity
    that lists the "subfolders" under `a/`:

        a/b/
    """

    storage_client = storage.Client()

    # Note: Client.list_blobs requires at least package version 1.17.0.
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=delimiter)

    # Note: The call returns a response only when the iterator is consumed.
    print("Blobs:")
    for blob in blobs:
        print(blob.name)

    if delimiter:
        print("Prefixes:")
        for prefix in blobs.prefixes:
            print(prefix)
    
```

### Delete a bucket (entire "filesystem")

```{}
# [START storage_delete_bucket]
from google.cloud import storage

def delete_bucket(bucket_name):
    """Deletes a bucket. The bucket must be empty."""
    # bucket_name = "your-bucket-name"

    storage_client = storage.Client()

    bucket = storage_client.get_bucket(bucket_name)
    bucket.delete()

    print(f"Bucket {bucket.name} deleted")


# [END storage_delete_bucket]
```

## Also

github copilot extension in vscode

## Cloud Run

The App Engine service worked great, but it runs 24/7 and costs about $1.50/day to keep it up.
Most of the time, the server doesn't actually need to be running. It only needs to populate the files on the cloud when a new collection is added.

I _think_ that using CloudRun instead would enable the server to spin up and take requests only when a request for a URL is not available, for example when a new collection is needed.

Instructions on how to set up a CloudRun job are pretty good. See

<https://console.cloud.google.com/run?tutorial=run--quickstart-github-repo&project=able-folio-397115>

I have created a new github repo, <https://github.com/eichblatt/cloud_template> which creates all this "docker" stuff. I'm not really sure what it is. But I _think_ that if I add my app.py to this repository, and put the dev branch of the deadstream repo as a requirement, (in requirements.txt), that it will do what I want.

Derek also tells me that I want to use https triggering:
<https://cloud.google.com/run/docs/triggering/https-request>

Similary, I could use this: <https://cloud.google.com/functions/docs/calling/http> which is even simpler.

Also see this: <https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service>

Running gcloud command: run deploy hello-world-1 --project able-folio-397115 --image gcr.io/able-folio-397115/hello-world-1 --client-name Cloud Code for VS Code --client-version 2.2.0 --platform managed --region us-central1 --allow-unauthenticated --port 8080 --cpu 1 --memory 256Mi --concurrency 80 --timeout 300 --clear-env-vars

### repos docker must be in google cloud

I am unable to put a github link in the requirements.txt file, so I think I'll need to port the entire repo over to google cloud.
See <https://cloud.google.com/artifact-registry/docs/python/store-python>

### creating a wheel

```{}
:  ~/projects/deadstream ; python3 setup.py bdist_wheel
```

This put the wheel in the dist folder.

```{}
: /home/steve/env ~/python-quickstart ; cp ~/projects/deadstream/dist/* dist/.
: /home/steve/env ~/python-quickstart ; python3 -m twine upload --repository-url https://us-central1-python.pkg.dev/able-folio-397115/quickstart-python-repo/ dist/*
```

## USING CLOUD RUN

I _think_ that I just got it working by going to cloud run (<https://console.cloud.google.com/run?hl=en&project=able-folio-397115>)
and clicking "Create Service"
Then, "Deploy one revision from an existing container image", Select:
Choose one of the _old-style services_ and it (might) work.

<https://cloud.google.com/storage/docs/samples/storage-list-files-with-prefix>

Note: When specifying the capacity of the machine, take a look at the app.yaml file  in my cloud_server folder:

```{}
runtime: python
env: flex
entrypoint: gunicorn -b :$PORT app:app

runtime_config:
  operating_system: ubuntu22
  runtime_version: "3.10"


manual_scaling:
  instances: 1
resources:
  cpu: 1
  memory_gb: .5
  disk_size_gb: 10
```

This is **working**!!!
Go to the run console. The service using the cloud deployment docker does the trick.
<https://console.cloud.google.com/run?hl=en&project=able-folio-397115>

Make sure and **turn off** the appengine app <https://console.cloud.google.com/appengine/versions?serviceId=default&hl=en&project=able-folio-397115>
because it costs $1.50/day to run.

## Linking the service to a custom domain

Following instructions on this page, <https://cloud.google.com/run/docs/integrate/custom-domain-load-balancer> ,I pointed the service (running at <https://deadstream-api-3pqgajc26a-uc.a.run.app>) to the domain <http://gratefuldeadtimemachine.com> that I own.

I was not sure if pointing it to spertilo.net (which I would prefer) would interfere with the site.

See <https://domains.google.com/registrar/gratefuldeadtimemachine.com>
Where I had to add a custom record on (<https://domains.google.com/registrar/gratefuldeadtimemachine.com/dns>)
Type: A
TTL: 1 hour
Data: 34.36.180.121

Now I can put into the livemusic program API = <https://gratefuldeadtimemachine.com>

I don't know if this is going to end up costing a lot of money, though.
