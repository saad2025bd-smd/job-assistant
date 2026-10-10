# Deploy Job Assistant as a free website (Streamlit Cloud)

Follow these steps carefully. Takes about 10–15 minutes the first time.

## 1. Create a free GitHub account
Go to: https://github.com/signup  
Sign up and verify your email.

## 2. Create a new repository
1. Go to: https://github.com/new
2. Repository name: `job-assistant` (or any name you like)
3. Set it to **Public**
4. Do NOT check "Add a README"
5. Click **Create repository**

## 3. Upload the project files
On the new empty repository page:

1. Click **uploading an existing file**
2. Drag and drop **all files and folders** from the `job_assistant` folder  
   (app.py, requirements.txt, sources folder, profile.yaml, etc.)
3. Scroll down → click **Commit changes**

Important: Upload the *contents* of the job_assistant folder, not the folder itself as a single zip.

## 4. Deploy on Streamlit Community Cloud
1. Go to: https://share.streamlit.io
2. Click **Sign in** → choose **Continue with GitHub**
3. Authorize Streamlit
4. Click **New app**
5. Fill in:
   - Repository: select the `job-assistant` repo you just created
   - Branch: `main`
   - Main file path: `app.py`
6. Click **Deploy**

Wait 1–3 minutes while it builds.

## 5. Your website is ready
You will get a public link like:

https://yourname-job-assistant.streamlit.app

Bookmark it. You can open it from any phone or computer.

## Optional: make the app private
In Streamlit Cloud → your app → Settings → you can restrict access to only your email.

## Notes
- The free plan is enough for personal use.
- Data (saved jobs, profile) is stored on the server and may reset if the app sleeps for a long time. For serious long-term use you can later add a proper database.
- Never put passwords or private API keys in the public repo.
