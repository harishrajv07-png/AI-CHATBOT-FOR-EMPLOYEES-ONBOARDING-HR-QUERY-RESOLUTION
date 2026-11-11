import os, sqlite3, json, re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "hr_chatbot.db")
INTENTS_PATH = os.path.join(DATA_DIR, "intents.json")

def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'employee', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS faqs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
          question TEXT NOT NULL, answer TEXT NOT NULL, keywords TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1, updated_by TEXT, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chat_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT NOT NULL, query TEXT NOT NULL,
          intent TEXT, confidence REAL, response TEXT, escalated INTEGER DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reports(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT NOT NULL, message TEXT NOT NULL,
          reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
          resolved_by TEXT, resolved_at TEXT);
        CREATE TABLE IF NOT EXISTS escalations(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT NOT NULL, query TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS onboarding_progress(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT NOT NULL, item_id INTEGER NOT NULL,
          completed INTEGER DEFAULT 0, UNIQUE(user_email, item_id));
        """)
        # Seed the initial FAQ library once; after this, HR manages content in the dashboard.
        count = c.execute("SELECT COUNT(*) n FROM faqs").fetchone()["n"]
        if count == 0 and os.path.exists(INTENTS_PATH):
            try:
                intents = json.load(open(INTENTS_PATH, encoding="utf-8")).get("intents", [])
                for item in intents:
                    patterns = item.get("patterns", [])
                    c.execute("INSERT INTO faqs(category,question,answer,keywords,updated_by,updated_at) VALUES(?,?,?,?,?,?)",
                              (item.get("tag","General").replace("_"," ").title(),
                               patterns[0] if patterns else item.get("tag","Question"),
                               item.get("response","Please contact HR for assistance."),
                               " | ".join(patterns), "system-seed", datetime.utcnow().isoformat()))
            except (OSError, ValueError, KeyError):
                pass
        # Seed practical IT-office FAQs if not already present.
        seeds = [
          ("IT Support","How do I reset my company password?","Use the company identity portal's password-reset option. Verify your identity and never share your password or OTP. If locked out, raise an IT helpdesk ticket.","password reset | forgot password | account locked | password expired"),
          ("IT Support","How do I request VPN access?","Submit a VPN access request through the IT service desk with your business reason and manager approval. Use only the approved company VPN.","vpn access | remote access | connect vpn"),
          ("IT Support","How do I report a phishing email?","Do not click links or open attachments. Use the email client's Report Phishing option or forward it to your company's security team according to policy.","phishing | suspicious email | scam email | malicious link"),
          ("IT Support","How do I request software installation?","Raise a software-installation ticket with the application name, business justification, device details, and manager approval if required. Install only licensed, approved software.","install software | application access | software request"),
          ("IT Support","What should I do if my laptop is lost or stolen?","Immediately contact IT Helpdesk and your manager, and follow the company's security incident process so access can be protected. Do not attempt to track or access the device yourself.","lost laptop | stolen laptop | missing device"),
          ("IT Support","How do I request access to a shared folder or application?","Submit an access request naming the folder/application, required access level, and business reason. Your manager or data owner may need to approve it.","shared drive access | folder permission | application access | access request"),
          ("IT Support","My internet or Wi-Fi is not working. What should I do?","Check the approved network instructions and restart your connection once. If the issue continues, raise a ticket with your location, device, error, and time observed.","wifi not working | internet issue | network problem"),
          ("IT Support","How do I report a security incident?","Report suspected data exposure, malware, lost devices, or unauthorized access immediately through the official IT/security incident channel. Include facts and avoid sharing sensitive data in chat.","security incident | malware | data breach | unauthorized access"),
          ("Workplace Tools","How do I get access to Git, Jira, or the code repository?","Request the specific project and role through the IT/service desk or project owner. Access should follow least-privilege rules and manager approval.","git access | jira access | github access | repository permission"),
          ("Workplace Tools","Where should I store company files?","Use company-approved storage such as the managed shared drive or document platform. Do not store confidential company data in personal email, personal cloud accounts, or unapproved USB devices.","file storage | share documents | company files | cloud storage"),
          ("Security","Can I share my password or OTP with IT/HR?","No. Never share passwords, MFA codes, or OTPs with anyone, including someone claiming to be IT or HR. Use official password-reset and support channels.","share password | otp | mfa code | password safety"),
          ("Workplace","How do I report an outage?","Check the official IT status channel first, then report the affected service, business impact, start time, error message, and your contact details in the service desk ticket.","system outage | application down | service unavailable"),
          ("Development","How do I request a new development environment?","Raise a request with the project, required tools/resources, environment type, business purpose, and manager/project-owner approval. Follow company security and data-handling standards.","development environment | dev server | test environment"),
          ("HR","How do I update my emergency contact details?","Use the employee self-service/HR portal to update emergency contacts, then verify the saved details. Contact HR if you cannot access the profile page.","emergency contact | update employee details"),
          ("HR","How do I contact HR about a confidential issue?","Use the official HR support channel or request a private meeting with HR. Avoid posting sensitive personal or employee information in a general chatbot.","confidential hr issue | private hr meeting")
        ]
        for category,q,a,kw in seeds:
            exists=c.execute("SELECT 1 FROM faqs WHERE lower(question)=lower(?)",(q,)).fetchone()
            if not exists:
                c.execute("INSERT INTO faqs(category,question,answer,keywords,updated_by,updated_at) VALUES(?,?,?,?,?,?)",
                          (category,q,a,kw,"system-seed",datetime.utcnow().isoformat()))
        # default HR account, intended for local demo; change password after first login.
        admin_email=os.environ.get("HR_ADMIN_EMAIL","hr.admin@company.com").lower()
        admin_password=os.environ.get("HR_ADMIN_PASSWORD","Admin@12345")
        if not c.execute("SELECT 1 FROM users WHERE email=?",(admin_email,)).fetchone():
            c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                      ("HR Administrator",admin_email,generate_password_hash(admin_password),"hr_admin",datetime.utcnow().isoformat()))

def create_user(name,email,password):
    with get_conn() as c:
        c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                  (name,email,generate_password_hash(password),"employee",datetime.utcnow().isoformat()))
        return dict(c.execute("SELECT id,name,email,role FROM users WHERE email=?",(email,)).fetchone())

def authenticate(email,password):
    with get_conn() as c:
        u=c.execute("SELECT * FROM users WHERE email=?",(email.lower().strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"],password):
            return {k:u[k] for k in ("id","name","email","role")}
    return None

def get_faqs(active_only=False):
    with get_conn() as c:
        sql="SELECT * FROM faqs" + (" WHERE active=1" if active_only else "") + " ORDER BY category, question"
        return [dict(x) for x in c.execute(sql).fetchall()]

def save_faq(faq_id,category,question,answer,keywords,editor):
    now=datetime.utcnow().isoformat()
    with get_conn() as c:
        if faq_id:
            c.execute("UPDATE faqs SET category=?,question=?,answer=?,keywords=?,updated_by=?,updated_at=?,active=1 WHERE id=?",
                      (category,question,answer,keywords,editor,now,faq_id))
        else:
            c.execute("INSERT INTO faqs(category,question,answer,keywords,updated_by,updated_at) VALUES(?,?,?,?,?,?)",
                      (category,question,answer,keywords,editor,now))

def delete_faq(faq_id):
    with get_conn() as c:
        c.execute("UPDATE faqs SET active=0 WHERE id=?",(faq_id,))

def log_chat(user_email,query,result):
    with get_conn() as c:
        c.execute("INSERT INTO chat_history(user_email,query,intent,confidence,response,escalated,created_at) VALUES(?,?,?,?,?,?,?)",
                  (user_email,query,result["intent"],result["confidence"],result["response"],int(result["escalate"]),datetime.utcnow().isoformat()))
        if result["escalate"]:
            c.execute("INSERT INTO escalations(user_email,query,status,created_at) VALUES(?,?,'open',?)",
                      (user_email,query,datetime.utcnow().isoformat()))

def create_report(user_email,message,reason):
    with get_conn() as c:
        c.execute("INSERT INTO reports(user_email,message,reason,status,created_at) VALUES(?,?,?,'open',?)",
                  (user_email,message,reason,datetime.utcnow().isoformat()))

def get_reports():
    with get_conn() as c: return [dict(x) for x in c.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()]

def resolve_report(report_id,hr_email):
    with get_conn() as c:
        c.execute("UPDATE reports SET status='resolved',resolved_by=?,resolved_at=? WHERE id=?",
                  (hr_email,datetime.utcnow().isoformat(),report_id))

def get_history(email,limit=50):
    with get_conn() as c:
        return [dict(x) for x in c.execute("SELECT * FROM chat_history WHERE user_email=? ORDER BY id DESC LIMIT ?",(email,limit)).fetchall()]

def get_all_escalations():
    with get_conn() as c: return [dict(x) for x in c.execute("SELECT * FROM escalations ORDER BY id DESC").fetchall()]

def resolve_escalation(escalation_id):
    with get_conn() as c: c.execute("UPDATE escalations SET status='resolved' WHERE id=?",(escalation_id,))

def toggle_onboarding_item(user_email,item_id,completed):
    with get_conn() as c:
        c.execute("INSERT INTO onboarding_progress(user_email,item_id,completed) VALUES(?,?,?) ON CONFLICT(user_email,item_id) DO UPDATE SET completed=excluded.completed",
                  (user_email,item_id,int(completed)))

def get_onboarding_progress(user_email):
    with get_conn() as c:
        return {r["item_id"]:bool(r["completed"]) for r in c.execute("SELECT item_id,completed FROM onboarding_progress WHERE user_email=?",(user_email,)).fetchall()}
