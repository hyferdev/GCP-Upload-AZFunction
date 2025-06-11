# Automated Azure to GCS File Transfer Function

![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)
![Azure Functions](https://img.shields.io/badge/Azure-Functions-blue?logo=azure-functions)
![Google Cloud Storage](https://img.shields.io/badge/Google_Cloud-Storage-blue?logo=google-cloud)
![Microsoft Graph](https://img.shields.io/badge/Microsoft-Graph-blue?logo=microsoft)

---

### **Summary**

This project contains a serverless, time-triggered Azure Function designed to automate the transfer of data from an Azure Blob Storage container to a Google Cloud Storage (GCS) bucket.

It runs on a daily schedule, processes files from multiple predefined source directories, archives them upon successful transfer, and sends a comprehensive status report via email using the Microsoft Graph API.

---

### **Key Features**

-   **🤖 Fully Automated:** Runs on a daily schedule without any manual intervention.
-   **☁️ Serverless & Scalable:** Built on Azure Functions, ensuring cost-efficiency and automatic scaling based on workload.
-   **🗂️ Multi-Directory Processing:** Monitors several source directories (`marketing/`, `engineering/`, `finance/`, `shipping/`) within a single run.
-   **🔄 Cross-Cloud Integration:** Seamlessly connects to both Azure Blob Storage and Google Cloud Storage using secure, modern authentication methods.
-   **🗄️ Robust Archiving:** Moves processed files from the source (`outbound`) container to a separate `archive` container, maintaining a clean processing queue.
-   **📧 Email Notifications:** Uses the Microsoft Graph API to send a detailed HTML report of all transferred files to designated recipients.

---

### **Workflow Diagram**

The function executes the following workflow on its schedule:

```
      +-----------------------------+
      |  Azure Function (Timer)     |
      |   Triggers at 7 AM EDT      |
      +--------------+--------------+
                     |
                     v
      +-----------------------------+
      |  1. List Blobs in Azure     |
      |  Container: 'outbound'      |
      |  Dirs: [marketing/, engineering/, finance/, shipping/] |
      +--------------+--------------+
                     |
           +--------------------+
           | For Each File Found|
           +--------------------+
                     |
       +-------------v-------------+   +----------------------------+
       | 2. Upload to GCS Bucket   |-->|  GCS Bucket                |
       | path: 'upload/[dir]/...'  |   |  'upload/marketing/...'    |
       +-------------+-------------+   +----------------------------+
                     | (Success)
                     v
       +-------------+-------------+   +----------------------------+
       | 3. Move to Archive        |-->|  Azure 'archive' Container |
       | copy source -> archive    |   |  '[dir]/...'               |
       | delete source             |   |                            |
       +-------------+-------------+   +----------------------------+
                     |
                     v
      +-----------------------------+
      |  4. Consolidate File List   |
      +--------------+--------------+
                     | (If files were processed)
                     v
      +-----------------------------+   +----------------------------+
      |  5. Send Summary Email      |-->|  Recipient's Inbox         |
      |   (via Microsoft Graph API) |   |                            |
      +-----------------------------+   +----------------------------+

```

---

### **Technical Stack**

-   **Platform:** Azure Functions (Python 3.11 Runtime)
-   **Source Storage:** Azure Blob Storage
-   **Destination Storage:** Google Cloud Storage
-   **Email Service:** Microsoft Graph API
-   **Key Python Libraries:**
    -   `azure-storage-blob`
    -   `google-cloud-storage`
    -   `msal` (Microsoft Authentication Library for Graph API)
    -   `requests`

---

### **Setup & Deployment**

#### **1. Prerequisites**

-   An **Azure Subscription** with permissions to create resources.
-   A **Google Cloud Project** with billing enabled.
-   **Python 3.11** and the **Azure Functions Core Tools** installed locally.

#### **2. Service Configuration**

Before deploying, you must configure the following services:

**A. Google Cloud Project:**
1.  Enable the **Cloud Storage API**.
2.  Create a **Service Account**.
3.  Assign the `Storage Object Creator` role to the service account.
4.  Generate and download the **JSON private key** for this service account.

**B. Azure Active Directory (for Email):**
1.  Create a new **App Registration**.
2.  Note the **Application (client) ID** and **Directory (tenant) ID**.
3.  Create a **Client Secret** and securely store its value.
4.  Under **API Permissions**, grant the `Mail.Send` **Application** permission for **Microsoft Graph**.
5.  An administrator must **Grant Admin Consent** for this permission.

**C. Azure Storage:**
1.  Create a Storage Account.
2.  Create two blob containers: `outbound` and `archive`.

#### **3. Deployment**

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Set Up Virtual Environment:**
    ```bash
    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Deploy to Azure:**
    Deploy the project using the Azure Functions Core Tools or the VS Code extension.

4.  **Configure Application Settings:**
    After deploying, navigate to your Function App in the Azure Portal and go to `Settings -> Configuration`. Add the following application settings:

    | Key                               | Description                                        | Example Value                                  |
    | --------------------------------- | -------------------------------------------------- | ---------------------------------------------- |
    | `AzureWebJobsStorage`             | Connection string for your Azure Storage Account.  | `DefaultEndpointsProtocol=...`                 |
    | `GCS_BUCKET_NAME`                 | The name of your destination GCS bucket.           | `my-company-data-bucket`                       |
    | `GOOGLE_APPLICATION_CREDENTIALS`  | The **entire JSON content** of your GCS key file.  | `{ "type": "service_account", ... }`           |
    | `GRAPH_TENANT_ID`                 | Your Azure AD Directory (tenant) ID.               | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`         |
    | `GRAPH_CLIENT_ID`                 | The Application (client) ID of your App Reg.       | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`         |
    | `GRAPH_CLIENT_SECRET`             | The **value** of the client secret you created.    | `A1b~C2d...`                                   |
    | `MAIL_FROM`                       | The verified email address to send from.           | `noreply@yourcompany.com`                      |
    | `MAIL_TO`                         | The recipient's email address for the report.      | `data-team@yourcompany.com`                    |

---

### **Project Structure**

```
.
├── host.json                           # Global Function App configuration
├── requirements.txt                    # Python package dependencies
└── upload_to_gcp/                      # Function-specific folder
    ├── process_outbound_files.py       # Main Python script with all logic
    └── function.json                   # Trigger configuration (Timer)
