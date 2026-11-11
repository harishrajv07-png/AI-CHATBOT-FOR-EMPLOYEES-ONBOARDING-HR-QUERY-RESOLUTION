"""Database-backed HR knowledge retrieval; no runtime dependency on intents.json."""
import re
from difflib import SequenceMatcher
import db

CONFIDENCE_THRESHOLD = 0.22

def clean_text(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())).strip()

def predict_intent(query):
    cleaned=clean_text(query)
    if not cleaned:
        return {"intent":"unknown","confidence":0.0,"response":"Please enter a question.","escalate":False}
    q_tokens=set(cleaned.split())
    best=None; best_score=0.0
    for faq in db.get_faqs(active_only=True):
        candidates=[faq["question"], faq["keywords"] or ""]
        candidates += (faq["keywords"] or "").split("|")
        for candidate in candidates:
            c=clean_text(candidate)
            if not c: continue
            ratio=SequenceMatcher(None,cleaned,c).ratio()
            t=set(c.split())
            overlap=len(q_tokens & t)/max(1,len(q_tokens | t))
            score=max(ratio, overlap*1.45)
            if score>best_score:
                best_score=score; best=faq
    if best and best_score>=CONFIDENCE_THRESHOLD:
        return {"intent":best["category"],"confidence":min(best_score,1.0),"response":best["answer"],"escalate":False}
    return {"intent":"unresolved","confidence":best_score,"response":"I couldn't confidently find an approved answer. I've sent this question to HR for review.","escalate":True}
