# 🛠️ Google API Setup Guide for Fable Cog

To use the Google Sheets and Docs sync features, a Google Cloud service account key is required. Follow these steps to set up your credentials securely:

---

## 1. Create a Google Cloud Project

- Visit: https://console.cloud.google.com/
- Click the project dropdown (top left) and select **New Project**
- Enter a name and create the project

## 2. Enable Google APIs

- With your project selected, go to **APIs & Services > Library**
- Search for and enable:
  - **Google Sheets API**
  - **Google Docs API**

## 3. Create a Service Account

- Go to **APIs & Services > Credentials**
- Click **Create Credentials > Service Account**
- Enter a name and click **Create and Continue**
- (Optional) Assign roles if needed, then click **Done**

## 4. Create and Download a Service Account Key

- In the Service Accounts list, click your new account
- Go to the **Keys** tab
- Click **Add Key > Create new key**
- Choose **JSON** and click **Create**
- Download and save the JSON file securely (do not share this file)

## 5. Store or Configure the Key for Fable

- **Never share your key publicly!**
- You can store the JSON key as a file or copy its contents as a string
- When using the Fable cog, provide the key as a string (or load from a secure location)
- Example usage:
  - Paste the JSON string into your bot's config or a secure environment variable
  - Pass it to the cog's commands or config as needed

---

## 🔒 Security Tips

- Treat your service account key like a password
- Rotate keys regularly and delete unused ones
- Restrict the service account's permissions to only what is needed

For more help, see the [Google Cloud documentation](https://cloud.google.com/iam/docs/creating-managing-service-account-keys) or ask in the Red-DiscordBot support channels.
