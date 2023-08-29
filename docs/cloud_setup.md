# Cloud setup

spertilo
cloud.google.com

install gcloud 

sudo apt-get install apt-transport-https ca-certificates gnupg curl sudo

https://cloud.google.com/sdk/docs/install#deb

then gcloud init

# Usage
(env) steve@prim:~/deadstream$ gcloud storage buckets list

(env) steve@prim:~$ gcloud storage cp GratefulDead_vcs.json gs://spertilo-data/vcs/GratefulDead_vcs.json

# App Engine
A product that runs the flask app.

## Deploying the service
First, authenticate:
(env) : ~/projects/deadstream/cloud_server ; gcloud auth application-default login

 This opened a browser, which I needed to log into to authenticate. Will this work without authentication from within the google cloud?

Then deploy
: ~/projects/deadstream/cloud_server ; gcloud app deploy  # This takes forever, but it works.

See the server at https://console.cloud.google.com/appengine/services?serviceId=default&versionId=20230826t203020&authuser=1&project=able-folio-397115

also, gcloud app browse should open the server in the browser.

# Note

Location of bucket in cloud 
https://console.cloud.google.com/storage/browser/spertilo-data;tab=objects?project=able-folio-397115&prefix=&forceOnObjectsSortingFiltering=false

#Public URL 
https://storage.googleapis.com/spertilo-data/vcs/GratefulDead_vcs.json

# Running the app

I want to move the app.py and app.yaml into a sub-folder. Also include requirements.txt in that folder. The requirements will include the deadstream project (api_server branch if necessary).

it is running on https://able-folio-397115.ue.r.appspot.com/

API = "https://able-folio-397115.ue.r.appspot.com"

# Google cloud python module

See https://github.com/googleapis/python-storage/blob/main/samples/snippets/storage_activate_hmac_key.py

pip install google-cloud-storage
## Authentication
(env) : ~/projects/deadstream/cloud_server ; gcloud auth application-default login

 This opened a browser, which I needed to log into to authenticate. Will this work without authentication from within the google cloud?

within python:
In [8]: from google.cloud import storage
In [7]: storage_client = storage.Client(project='able-folio-397115')

## Example of copying a file

https://github.com/googleapis/python-storage/blob/main/samples/snippets/storage_copy_file.py

## Functions I will probably need

### Download a blob (file)
```
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

```
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
```
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
```
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
```
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
```
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
### Delete a bucket (entire "filesystem")
```
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
# Also
github copilot extension in vscode
