# HR Assist — upgraded MCA project

## Features
- Employee account registration and email/password login.
- HR administrator login with server-side role checks (employees cannot select the HR role).
- SQLite database-backed knowledge base. HR can add, edit, and deactivate FAQs in the dashboard; changes apply immediately without editing `intents.json` or retraining a model.
- Seeded IT-office topics: password reset, VPN, phishing, software installs, lost devices, shared-folder access, Wi-Fi, security incidents, Git/Jira/repository access, approved file storage, outages and development environments, plus HR questions.
- Chat history and unknown-question escalation.
- Basic safety moderation blocks likely spam, URLs, repeated garbage, and a limited list of abusive/threatening phrases before answering, then records a report for HR review.
- HR can review reports and mark them reviewed.

## Run on Windows (PowerShell)
1. Extract the ZIP.
2. Open PowerShell in the `hr_chatbot` folder (the folder containing `app.py`).
3. Create and activate a virtual environment:
   ```powershell
   py -m venv venv
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   .\venv\Scripts\Activate.ps1
   ```
4. Install packages:
   ```powershell
   python -m pip install -r requirements.txt
   ```
5. Start:
   ```powershell
   python app.py
   ```
6. Open `http://127.0.0.1:5000` in your browser. This is a local application address, not a public website link.

## Demo credentials
- HR email: `hr.admin@company.com`
- HR password: `Admin@12345`

Change this demo password before using real employee information. You can set a different bootstrap HR account before the first run:
```powershell
$env:HR_ADMIN_EMAIL="your-hr@company.com"
$env:HR_ADMIN_PASSWORD="Use-A-Strong-Password"
$env:FLASK_SECRET_KEY="a-long-random-secret"
python app.py
```
The default HR account is created only if the email does not already exist. For a production system, add a proper HR provisioning process, password reset, CSRF protection, rate limiting, HTTPS, audit logging, company identity provider/SSO, and a managed database. This sample is intended for local MCA demonstration, not deployment with real employee records as-is.

## How HR adds knowledge (no JSON editing)
1. Sign in with the HR account.
2. In **Knowledge base**, fill in Category, Question, Approved answer, and alternative keywords separated by `|`.
3. Click **Save FAQ**. To change an answer, click **Edit** on the existing FAQ and save. To remove it from bot search, click **Deactivate**.
4. Test the question in the employee chat. The FAQ is read from SQLite at request time, so changes take effect immediately.
5. Check **Questions needing HR answers** for questions the bot cannot match. Write an approved FAQ for repeated questions.
6. Check **Blocked messages reported to HR** to review messages rejected by the basic safety filter.

## Database
`data/hr_chatbot.db` is created automatically. Main tables: `users`, `faqs`, `chat_history`, `reports`, `escalations`, and `onboarding_progress`. `intents.json` is used only to seed the database on a fresh install; normal answers come from the database. If you have an older demo database, back it up before upgrading. To start with a clean demo database, stop the app and remove `data/hr_chatbot.db`, then restart; this deletes local demo users/history/FAQ edits.

## Important limitations
- Login is local to this demo; it is not connected to your company's identity provider.
- The moderation rules are a simple starter filter, not a complete AI safety classifier. They may miss harmful content or flag legitimate text. HR should review reports; do not use this as the sole security control.
- Seeded sample HR policy wording from the original demo may not match a real employer. Replace it with approved company policies before presenting it as real-time company guidance.
