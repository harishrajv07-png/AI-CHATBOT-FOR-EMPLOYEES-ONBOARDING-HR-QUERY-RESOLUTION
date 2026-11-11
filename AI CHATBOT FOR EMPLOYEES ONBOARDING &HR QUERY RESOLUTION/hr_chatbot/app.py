import json, os, re, secrets
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import db
from nlp.classifier import predict_intent

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__)
app.secret_key=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

@app.before_request
def setup():
    db.init_db()

def login_required(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        if "user_email" not in session: return redirect(url_for("login"))
        return view(*args,**kwargs)
    return wrapped

def hr_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args,**kwargs):
        if session.get("role")!="hr_admin":
            flash("HR administrator access is required.","error")
            return redirect(url_for("chat_page"))
        return view(*args,**kwargs)
    return wrapped

def load_checklist():
    with open(os.path.join(BASE_DIR,"data","onboarding_checklist.json"),encoding="utf-8") as f:
        return json.load(f)["checklist"]

@app.route("/")
def login():
    if "user_email" in session:
        return redirect(url_for("admin_page" if session.get("role")=="hr_admin" else "chat_page"))
    return render_template("login.html")

@app.route("/login",methods=["POST"])
def do_login():
    email=request.form.get("email","").strip().lower()
    password=request.form.get("password","")
    login_type=request.form.get("login_type","employee")
    if login_type not in ("employee", "hr_admin"):
        login_type="employee"
    user=db.authenticate(email,password)
    if not user or user["role"] != login_type:
        message = "Invalid email or password for the selected sign-in option."
        return render_template("login.html",error=message,login_type=login_type),401
    session.clear()
    session.update(user_email=user["email"],user_name=user["name"],role=user["role"])
    return redirect(url_for("admin_page" if user["role"]=="hr_admin" else "chat_page"))

@app.route("/register",methods=["POST"])
def register():
    name=request.form.get("name","").strip()
    email=request.form.get("email","").strip().lower()
    password=request.form.get("password","")
    if not name or not email or len(password)<8:
        return render_template("login.html",error="Enter your name, a valid email, and a password of at least 8 characters."),400
    try: user=db.create_user(name,email,password)
    except Exception:
        return render_template("login.html",error="That email may already be registered. Try signing in."),400
    session.clear()
    session.update(user_email=user["email"],user_name=user["name"],role=user["role"])
    return redirect(url_for("chat_page"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Obvious spam, threats, profanity, solicitation and repeated garbage are blocked before chatbot retrieval.
BLOCK_PATTERNS=[
 r"\b(?:buy now|click here|free money|crypto giveaway|casino bonus|make money fast)\b",
 r"\b(?:fuck|fucking|bitch|asshole|motherfucker|kill you|i will hurt)\b",
 r"(.)\1{7,}", r"https?://\S+",
]
def moderation_reason(message):
    low=message.lower().strip()
    if len(low)<2: return "Empty or too-short message"
    if len(low)>1000: return "Message exceeds the 1000-character limit"
    if sum(ch.isalpha() for ch in low)<2: return "Non-text or meaningless message"
    if any(re.search(p,low) for p in BLOCK_PATTERNS): return "Potential spam, abusive, threatening, or unsafe content"
    words=re.findall(r"[a-zA-Z0-9]+",low)
    if len(words)>=5 and len(set(words))/len(words)<0.25: return "Repeated or spam-like text"
    return None

@app.route("/chat")
@login_required
def chat_page(): return render_template("chat.html",name=session["user_name"])

@app.route("/api/chat",methods=["POST"])
@login_required
def api_chat():
    data=request.get_json(silent=True) or {}
    query=(data.get("message") or "").strip()
    reason=moderation_reason(query)
    if reason:
        db.create_report(session["user_email"],query,reason)
        return jsonify({"blocked":True,"response":"This message was blocked by the safety filter and reported to HR for review. Please send a relevant, respectful workplace question."}),422
    result=predict_intent(query)
    db.log_chat(session["user_email"],query,result)
    return jsonify({"response":result["response"],"intent":result["intent"],"confidence":round(result["confidence"],2),"escalated":result["escalate"]})

@app.route("/history")
@login_required
def history_page():
    return render_template("history.html",history=db.get_history(session["user_email"]),name=session["user_name"])

@app.route("/onboarding")
@login_required
def onboarding_page():
    checklist=load_checklist(); progress=db.get_onboarding_progress(session["user_email"])
    for item in checklist: item["completed"]=progress.get(item["id"],False)
    done=sum(1 for i in checklist if i["completed"])
    return render_template("onboarding.html",checklist=checklist,percent=int(done/len(checklist)*100) if checklist else 0,name=session["user_name"])

@app.route("/api/onboarding/toggle",methods=["POST"])
@login_required
def api_onboarding_toggle():
    data=request.get_json(silent=True) or {}
    try: item_id=int(data.get("item_id"))
    except (TypeError,ValueError): return jsonify({"error":"Invalid item"}),400
    db.toggle_onboarding_item(session["user_email"],item_id,bool(data.get("completed")))
    return jsonify({"status":"ok"})

@app.route("/admin")
@hr_required
def admin_page():
    return render_template("admin.html",escalations=db.get_all_escalations(),reports=db.get_reports(),faqs=db.get_faqs(),name=session["user_name"])

@app.route("/api/admin/faq",methods=["POST"])
@hr_required
def api_save_faq():
    data=request.get_json(silent=True) or {}
    category=(data.get("category") or "").strip()
    question=(data.get("question") or "").strip()
    answer=(data.get("answer") or "").strip()
    keywords=(data.get("keywords") or "").strip()
    if not category or not question or not answer:
        return jsonify({"error":"Category, question and answer are required."}),400
    if len(question)>250 or len(answer)>3000 or len(keywords)>1500:
        return jsonify({"error":"One or more fields are too long."}),400
    faq_id=data.get("id")
    try: faq_id=int(faq_id) if faq_id else None
    except (TypeError,ValueError): return jsonify({"error":"Invalid FAQ id."}),400
    db.save_faq(faq_id,category,question,answer,keywords,session["user_email"])
    return jsonify({"status":"ok"})

@app.route("/api/admin/faq/delete",methods=["POST"])
@hr_required
def api_delete_faq():
    data=request.get_json(silent=True) or {}
    try: db.delete_faq(int(data.get("id")))
    except (TypeError,ValueError): return jsonify({"error":"Invalid FAQ id"}),400
    return jsonify({"status":"ok"})

@app.route("/api/admin/report/resolve",methods=["POST"])
@hr_required
def api_resolve_report():
    data=request.get_json(silent=True) or {}
    try: db.resolve_report(int(data.get("id")),session["user_email"])
    except (TypeError,ValueError): return jsonify({"error":"Invalid report id"}),400
    return jsonify({"status":"ok"})

@app.route("/api/admin/resolve",methods=["POST"])
@hr_required
def api_admin_resolve():
    data=request.get_json(silent=True) or {}
    try: db.resolve_escalation(int(data.get("escalation_id")))
    except (TypeError,ValueError): return jsonify({"error":"Invalid escalation id"}),400
    return jsonify({"status":"ok"})

if __name__=="__main__":
    db.init_db()
    app.run(debug=False,host="127.0.0.1",port=5000)
