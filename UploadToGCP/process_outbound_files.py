import logging
import os
import json
import requests
import msal
from azure.storage.blob import BlobServiceClient
from google.cloud import storage
from google.oauth2 import service_account
import azure.functions as func

# =================================================================================================
#  CONFIGURATION - Reads all settings from the Function App's environment variables.
# =================================================================================================

# Azure Storage Configuration
connect_str = os.environ.get('AzureWebJobsStorage')
source_container_name = 'outbound'
archive_container_name = 'archive'
source_directories = ['marketing/', 'engineering/', 'finance/', 'shipping/']

# Google Cloud Storage Configuration
gcs_bucket_name = os.environ.get('GCS_BUCKET_NAME')
gcp_creds_string = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
gcs_base_path = 'upload/'

# Microsoft Graph API (Email) Configuration
graph_tenant_id = os.environ.get('GRAPH_TENANT_ID')
graph_client_id = os.environ.get('GRAPH_CLIENT_ID')
graph_client_secret = os.environ.get('GRAPH_CLIENT_SECRET')
mail_from_address = os.environ.get('MAIL_FROM')
mail_to_address = os.environ.get('MAIL_TO')


# =================================================================================================
#  CLIENT INITIALIZATION - Sets up reusable clients for Azure and Google Cloud.
# =================================================================================================

# Initialize the Google Cloud Storage client using service account credentials.
if not gcp_creds_string:
    raise ValueError("The GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
gcp_creds_info = json.loads(gcp_creds_string)
gcp_credentials = service_account.Credentials.from_service_account_info(gcp_creds_info)
gcs_storage_client = storage.Client(credentials=gcp_credentials)

# Initialize the Azure Blob Storage client from a connection string.
azure_blob_service_client = BlobServiceClient.from_connection_string(connect_str)


# =================================================================================================
#  MAIN FUNCTION - The primary entry point triggered by the timer.
# =================================================================================================

def main(timer: func.TimerRequest) -> None:
    """
    Main function triggered by a timer(see UploadToGCP/function.json). It processes files from multiple source directories
    in an Azure container, uploads them to GCS, moves them to a separate 'archive' container,
    and sends a summary email.
    """
    logging.info('Python timer trigger function executed.')
    
    processed_files = []

    try:
        source_container_client = azure_blob_service_client.get_container_client(source_container_name)
        archive_container_client = azure_blob_service_client.get_container_client(archive_container_name)
        
        # Loop through each specified source directory to find files.
        for source_dir in source_directories:
            logging.info(f"Checking for files in source directory: '{source_dir}'")
            blob_list = source_container_client.list_blobs(name_starts_with=source_dir)
            
            for blob in blob_list:
                # Skip any items that are just directory markers.
                if blob.name.endswith('/'):
                    continue
                
                logging.info(f"Processing blob: {blob.name}")

                source_blob_client = source_container_client.get_blob_client(blob.name)

                # Download blob data into memory.
                blob_data = source_blob_client.download_blob().readall()

                # Construct the destination path in GCS and upload the file.
                gcs_object_name = gcs_base_path + blob.name
                gcs_bucket = gcs_storage_client.bucket(gcs_bucket_name)
                gcs_blob = gcs_bucket.blob(gcs_object_name)
                gcs_blob.upload_from_string(blob_data)
                
                logging.info(f"Successfully uploaded '{blob.name}' to GCS as '{gcs_object_name}'.")

                # "Move" the original file by copying it to the archive container, then deleting the source.
                archive_blob_client = archive_container_client.get_blob_client(blob.name)
                archive_blob_client.start_copy_from_url(source_blob_client.url)
                source_blob_client.delete_blob()
                logging.info(f"Archived '{blob.name}' to container '{archive_container_name}'.")
                
                processed_files.append(blob.name)

        # After processing all directories, send a summary email if files were moved.
        if not processed_files:
            logging.info("No new files found in any source directory to process.")
        else:
            logging.info(f"Successfully processed and archived {len(processed_files)} files in total.")
            send_summary_email(processed_files)

    except Exception as e:
        logging.error(f"An error occurred during file processing: {e}", exc_info=True)


# =================================================================================================
#  HELPER FUNCTION - Contains the logic for sending the email notification.
# =================================================================================================

def send_summary_email(file_list):
    """
    Constructs and sends a summary email using the Microsoft Graph API.
    """
    if not all([graph_tenant_id, graph_client_id, graph_client_secret, mail_from_address, mail_to_address]):
        logging.warning("Graph API environment variables are not configured. Skipping email.")
        return

    # Authenticate to Azure AD to get an access token for Microsoft Graph.
    authority = f"https://login.microsoftonline.com/{graph_tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=graph_client_id, authority=authority, client_credential=graph_client_secret)
    
    scopes = ["https://graph.microsoft.com/.default"]
    result = app.acquire_token_for_client(scopes=scopes)
    
    if "access_token" not in result:
        logging.error(f"Failed to acquire Graph API access token: {result.get('error_description')}")
        return

    # Prepare and send the email via the Graph API REST endpoint.
    access_token = result['access_token']
    url = f"https://graph.microsoft.com/v1.0/users/{mail_from_address}/sendMail"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}

    file_html_list = "".join([f"<li>{file}</li>" for file in file_list])
    html_body = f"""
    <h3>Azure to GCS File Transfer Report</h3>
    <p>The following {len(file_list)} files were successfully transferred and archived:</p>
    <ul>{file_html_list}</ul>
    """

    email_payload = {
        'message': {
            'subject': 'File Transfer to GCS Successful',
            'body': {'contentType': 'HTML', 'content': html_body},
            'toRecipients': [{'emailAddress': {'address': mail_to_address}}]
        },
        'saveToSentItems': 'true'
    }

    try:
        response = requests.post(url, headers=headers, json=email_payload)
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
        logging.info(f"Summary email sent successfully via Graph API! Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Failed to send summary email via Graph API: {e}", exc_info=True)
