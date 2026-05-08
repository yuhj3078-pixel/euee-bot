import os
import logging
from datetime import datetime, date, timedelta, timezone
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from helpers import safe_user_ref

logger = logging.getLogger(__name__)

def _today():
    return str(date.today())

def _now():
    return datetime.now(timezone.utc).isoformat()

# SUPABASE SETTINGS are now loaded from config.py

_supabase: Client = None

def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in .env")
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase

# ── FEATURE GATING (TIER PERMISSIONS) ───────────────────────────────────────

TIER_FEATURES = {
    "free": ["practice_limited", "daily_tips", "streak"],
    "pro": [
        "practice_unlimited", "daily_tips", "streak", 
        "notes", "audio", "model_exam_5", 
        "textbooks", "mnemonic", "review_sheet"
    ],
    "max": [
        "practice_unlimited", "daily_tips", "streak", 
        "notes", "audio", "model_exam_5", 
        "textbooks", "mnemonic", "review_sheet",
        "flashcards", "boss_fight", "score_predictor", 
        "weak_radar", "parent_link"
    ]
}

def has_access(tier: str, feature: str) -> bool:
    """Checks if a normalized tier has permission for a specific feature."""
    if not tier: tier = "free"
    t = tier.lower()
    
    # Max tier has access to everything
    if t == "max": return True
    
    allowed = TIER_FEATURES.get(t, [])
    return feature in allowed

def get_user(telegram_id: int) -> dict | None:
    try:
        supabase = _get_supabase()
        response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error("Error fetching %s: %s", safe_user_ref(telegram_id), e)
        return None

def create_user(telegram_id: int, name: str, language: str = "en") -> bool:
    """Compatibility wrapper for create_user."""
    return update_user(telegram_id, {"name": name, "language": language})

def update_user(telegram_id: int, updates: dict) -> bool:
    try:
        supabase = _get_supabase()
        response = supabase.table("users").update(updates).eq("telegram_id", telegram_id).execute()
        
        # If no rows affected, upsert
        if not response.data:
            updates["telegram_id"] = telegram_id
            supabase.table("users").upsert(updates).execute()
        return True
    except Exception as e:
        logger.error("Error updating %s: %s", safe_user_ref(telegram_id), e)
        return False

def get_random_real_question(subject: str) -> dict | None:
    try:
        supabase = _get_supabase()
        # Note: Supabase REST doesn't have a direct RANDOM() order, 
        # but we can fetch a small batch and pick one.
        response = supabase.table("real_exam_questions").select("*").eq("subject", subject).limit(20).execute()
        if response.data:
            import random
            return random.choice(response.data)
        return None
    except Exception as e:
        logger.error(f"Error fetching question for {subject}: {e}")
        return None

def check_and_increment_questions(telegram_id: int, tier: str, limit: int) -> bool:
    if check_questions_limit_reached(telegram_id, tier, limit):
        return False

    user = get_user(telegram_id)
    if not user:
        return False

    questions_today = user.get("questions_today", 0)
    if str(user.get("last_question_date")) != _today():
        questions_today = 0

    update_user(telegram_id, {
        "questions_today": questions_today + 1,
        "questions_total": user.get("questions_total", 0) + 1,
        "last_question_date": _today()
    })
    return True

def check_questions_limit_reached(telegram_id: int, tier: str, limit: int = 10) -> bool:
    user = get_user(telegram_id)
    if not user: return False
    
    # If it's a new day, they haven't reached the limit yet
    if str(user.get("last_question_date")) != _today():
        return False
        
    return user.get("questions_today", 0) >= limit

def normalize_tier(tier: str) -> str:
    if not tier: return "free"
    t = tier.lower()
    if t.startswith("pro"): return "pro"
    if t.startswith("max"): return "max"
    return "free"

def is_subscription_active(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    if not user: return False
    expires = user.get("subscription_expires_at")
    if not expires: return True # Free tier doesn't expire
    
    expiry_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
    return datetime.now(timezone.utc) < expiry_dt

# ── SOCIAL & COMPETITION ───────────────────────────────────────────────────

def get_leaderboard(limit: int = 10) -> list:
    try:
        supabase = _get_supabase()
        response = supabase.table("users").select("name, questions_total, streak").order("questions_total", desc=True).limit(limit).execute()
        return response.data
    except Exception:
        return []

def _normalize_battle_record(record: dict | None) -> dict | None:
    if not record:
        return None

    normalized = dict(record)
    status = str(normalized.get("status", "waiting")).lower()
    normalized["status"] = status
    normalized.setdefault("battle_id", normalized.get("battle_id"))
    normalized.setdefault("challenger_id", normalized.get("challenger_id"))
    normalized.setdefault("opponent_id", normalized.get("opponent_id"))
    return normalized

def get_active_battles(telegram_id: int) -> list:
    try:
        supabase = _get_supabase()
        response = (
            supabase.table("battles")
            .select("*")
            .or_(f"challenger_id.eq.{telegram_id},opponent_id.eq.{telegram_id}")
            .eq("status", "active")
            .execute()
        )
        return [_normalize_battle_record(row) for row in response.data]
    except Exception:
        return []

def create_battle(challenger_id: int, subject: str, question_payload: dict, opponent_id: int | None = None) -> str | None:
    try:
        supabase = _get_supabase()
        payload = {
            "challenger_id": challenger_id,
            "opponent_id": opponent_id,
            "subject": subject,
            "question": question_payload.get("question", ""),
            "options": question_payload.get("options", {}) or {},
            "correct_answer": question_payload.get("answer", ""),
            "explanation": question_payload.get("explanation", ""),
            "status": "waiting",
        }
        resp = supabase.table("battles").insert(payload).execute()
        return resp.data[0]["battle_id"] if resp.data else None
    except Exception as e:
        logger.error(f"Error creating battle: {e}")
        return None

def get_battle(battle_id: str) -> dict | None:
    try:
        supabase = _get_supabase()
        resp = supabase.table("battles").select("*").eq("battle_id", battle_id).execute()
        return _normalize_battle_record(resp.data[0]) if resp.data else None
    except Exception:
        return None

def join_battle(battle_id: str, user2_id: int) -> dict | None:
    try:
        supabase = _get_supabase()
        battle = get_battle(battle_id)
        if not battle:
            return None
        if battle.get("status") == "done":
            return None
        if battle.get("opponent_id") and battle.get("opponent_id") != user2_id:
            return None

        status = "active" if battle.get("challenger_id") != user2_id else battle.get("status", "waiting")
        updates = {
            "opponent_id": user2_id if battle.get("challenger_id") != user2_id else battle.get("opponent_id"),
            "status": status,
        }
        supabase.table("battles").update(updates).eq("battle_id", battle_id).execute()
        return get_battle(battle_id)
    except Exception as e:
        logger.error(f"Error joining battle {battle_id}: {e}")
        return None

def submit_battle_answer(battle_id: str, user_id: int, answer: str, time_taken: float, is_correct: bool) -> dict | None:
    try:
        battle = get_battle(battle_id)
        if not battle:
            return None

        updates = {}
        if user_id == battle.get("challenger_id"):
            updates.update({
                "challenger_answer": answer,
                "challenger_correct": is_correct,
                "challenger_time": time_taken,
                "status": "active",
            })
        elif user_id == battle.get("opponent_id"):
            updates.update({
                "opponent_answer": answer,
                "opponent_correct": is_correct,
                "opponent_time": time_taken,
                "status": "active",
            })
        else:
            return None

        _get_supabase().table("battles").update(updates).eq("battle_id", battle_id).execute()
        return get_battle(battle_id)
    except Exception as e:
        logger.error(f"Error saving battle answer for {battle_id}: {e}")
        return None

def finalize_battle(battle_id: str, winner_id: int | None, challenger_correct: bool, opponent_correct: bool) -> bool:
    try:
        _get_supabase().table("battles").update({
            "winner_id": winner_id,
            "challenger_correct": challenger_correct,
            "opponent_correct": opponent_correct,
            "status": "done",
            "finished_at": _now(),
        }).eq("battle_id", battle_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error finalizing battle {battle_id}: {e}")
        return False

def check_transaction_exists(tx_id: str) -> bool:
    try:
        supabase = _get_supabase()
        resp = supabase.table("payment_attempts").select("tx_id").eq("tx_id", tx_id).execute()
        return len(resp.data) > 0
    except Exception: return False

def save_payment_attempt(telegram_id: int, username: str, tx_id: str, plan_requested: str, screenshot_url: str, status: str = "PENDING", **kwargs) -> bool:
    try:
        if check_transaction_exists(tx_id): return False
        supabase = _get_supabase()
        data = {
            "tx_id": tx_id,
            "transaction_id": tx_id,
            "telegram_id": telegram_id,
            "username": username,
            "plan_requested": plan_requested,
            "screenshot_url": screenshot_url,
            "status": status.upper(),
            "created_at": _now()
        }
        # Map extra fields from kwargs to table columns
        if "amount" in kwargs: data["amount"] = kwargs["amount"]
        if "source" in kwargs: data["source"] = kwargs["source"]
        
        supabase.table("payment_attempts").insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Error saving payment attempt: {e}")
        return False

def update_payment_attempt(tx_id: str, updates: dict) -> bool:
    try:
        supabase = _get_supabase()
        supabase.table("payment_attempts").update(updates).eq("tx_id", tx_id).execute()
        return True
    except Exception: return False

def user_telebirr_rate_limit_exceeded(telegram_id: int) -> bool:
    try:
        supabase = _get_supabase()
        # Check if user has more than 5 attempts in the last hour
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = supabase.table("payment_attempts").select("tx_id").eq("telegram_id", telegram_id).gt("created_at", hour_ago).execute()
        return len(resp.data) >= 5
    except Exception: return False

# Add other necessary mock-compat layers if needed
def _collection_order_column(table_name: str) -> str | None:
    return {
        "users": "telegram_id",
        "payment_attempts": "tx_id",
        "battles": "battle_id",
        "boss_fights": "id",
        "parent_reports": "created_at",
    }.get(table_name, "created_at")

def _row_identifier(table_name: str, row: dict) -> str:
    for key in ("battle_id", "tx_id", "telegram_id", "id", "cache_key", "date", "parent_token"):
        value = row.get(key)
        if value is not None:
            return str(value)
    return f"{table_name}:{hash(str(sorted(row.items())))}"

class CollectionRef:
    def __init__(self, name, filters=None, limit_count=None, offset=0):
        self.name = name
        self._filters = list(filters or [])
        self._limit_count = limit_count
        self._offset = offset

    def _clone(self):
        return CollectionRef(
            self.name,
            filters=self._filters,
            limit_count=self._limit_count,
            offset=self._offset,
        )

    def add(self, data):
        supabase = _get_supabase()
        return supabase.table(self.name).insert(data).execute()

    def where(self, field, op, value):
        if op != "==":
            raise NotImplementedError(f"Unsupported where operator: {op}")
        clone = self._clone()
        clone._filters.append((field, value))
        return clone

    def limit(self, count):
        clone = self._clone()
        clone._limit_count = count
        return clone

    def start_after(self, _last_doc):
        clone = self._clone()
        clone._offset += clone._limit_count or 0
        return clone

    def stream(self):
        supabase = _get_supabase()
        query = supabase.table(self.name).select("*")
        for field, value in self._filters:
            query = query.eq(field, value)
        order_col = _collection_order_column(self.name)
        if order_col:
            query = query.order(order_col)
        if self._limit_count is not None:
            end = self._offset + self._limit_count - 1
            query = query.range(self._offset, end)
        elif self._offset:
            query = query.range(self._offset, self._offset + 999)
        resp = query.execute()
        for r in resp.data:
            yield DocumentSnapshot(r, _row_identifier(self.name, r))

class DocumentSnapshot:
    def __init__(self, data, doc_id):
        self._data = data
        self.id = doc_id
    def to_dict(self): return self._data

class DocumentDB:
    def collection(self, name): return CollectionRef(name)
    def batch(self): return BatchRef()

class BatchRef:
    def __init__(self): self.ops = []
    def set(self, doc_ref, data): self.ops.append(("set", doc_ref, data))
    def update(self, doc_ref, data): self.ops.append(("update", doc_ref, data))
    def commit(self):
        supabase = _get_supabase()
        for op, ref, data in self.ops:
            if op == "set": supabase.table(ref.collection).upsert(data).execute()
            elif op == "update": supabase.table(ref.collection).update(data).eq(ref.id_field, ref.id_val).execute()

db = DocumentDB()

def get_pending_payments() -> list:
    try:
        supabase = _get_supabase()
        response = supabase.table("payment_attempts").select("*").eq("status", "PENDING").execute()
        return response.data
    except Exception:
        return []

def approve_payment(tx_id: str) -> bool:
    try:
        supabase = _get_supabase()
        # Get payment record
        resp = supabase.table("payment_attempts").select("*").eq("tx_id", tx_id).execute()
        if not resp.data: return False
        payment = resp.data[0]
        
        # Determine tier and duration
        plan = str(payment.get("plan_requested", "pro")).lower()
        tier = "max" if "max" in plan else "pro"
        days = 365 if "year" in plan else 30
        expiry = datetime.now(timezone.utc) + timedelta(days=days)
        
        update_user(payment["telegram_id"], {
            "tier": tier,
            "subscription_active": True,
            "subscription_expires_at": expiry.isoformat(),
            "tier_updated_at": _now()
        })
        
        # Mark payment approved
        supabase = _get_supabase()
        supabase.table("payment_attempts").update({"status": "APPROVED"}).eq("tx_id", tx_id).execute()
        return True
    except Exception:
        return False

def reject_payment(tx_id: str) -> bool:
    try:
        supabase = _get_supabase()
        supabase.table("payment_attempts").update({"status": "REJECTED"}).eq("tx_id", tx_id).execute()
        return True
    except Exception:
        return False

def upgrade_user_chapa(telegram_id: int, plan_id: str, tx_id: str) -> bool:
    """Automated upgrade for Chapa payments."""
    try:
        # 1. Normalize plan and duration
        clean_plan = "pro" if "pro" in plan_id.lower() else "max"
        days = 365 if "yearly" in plan_id.lower() else 30
        expiry = datetime.now(timezone.utc) + timedelta(days=days)
        
        # 2. Update user
        update_user(telegram_id, {
            "tier": clean_plan,
            "subscription_active": True,
            "subscription_expires_at": expiry.isoformat()
        })
        
        # 3. Log attempt
        supabase = _get_supabase()
        supabase.table("payment_attempts").upsert({
            "tx_id": tx_id,
            "transaction_id": tx_id,
            "telegram_id": telegram_id,
            "plan_requested": plan_id,
            "status": "APPROVED",
            "source": "chapa_automated",
            "created_at": _now()
        }).execute()
        
        return True
    except Exception as e:
        logger.error("Failed to upgrade %s via Chapa: %s", safe_user_ref(telegram_id), e)
        return False

def get_payment_attempt(tx_id: str) -> dict | None:
    try:
        supabase = _get_supabase()
        resp = supabase.table("payment_attempts").select("*").eq("tx_id", tx_id).execute()
        return resp.data[0] if resp.data else None
    except Exception: return None

def get_feature_suggestions() -> list:
    try:
        supabase = _get_supabase()
        response = supabase.table("feature_suggestions").select("*").limit(50).execute()
        return response.data
    except Exception:
        return []

def get_user_by_parent_token(token: str) -> dict | None:
    try:
        supabase = _get_supabase()
        response = supabase.table("users").select("*").eq("parent_token", token).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None

def update_streak(telegram_id: int):
    user = get_user(telegram_id)
    if not user: return
    last_active = user.get("last_active_date")
    today = date.today()
    
    if last_active == str(today - timedelta(days=1)):
        new_streak = user.get("streak", 0) + 1
    elif last_active == str(today):
        new_streak = user.get("streak", 0)
    else:
        new_streak = 1
        
    update_user(telegram_id, {"streak": new_streak, "last_active_date": str(today)})

def record_answer(telegram_id: int, subject: str, is_correct: bool, topic: str = "General", question_data: dict = None):
    try:
        if not is_correct:
            # Save to wrong_questions table for review
            supabase = _get_supabase()
            data = {
                "telegram_id": telegram_id,
                "subject": subject,
                "topic": topic,
                "question": (question_data.get("question") if question_data else "Unknown")[:500],
                "options": question_data.get("options") if question_data else {},
                "answer": question_data.get("answer") if question_data else "",
                "explanation": (question_data.get("explanation") if question_data else "")[:1000]
            }
            try:
                supabase.table("wrong_questions").insert(data).execute()
            except Exception as e:
                logger.warning(f"Could not save wrong question (table might not exist): {e}")
        # Also update aggregate counters on the user record so Progress shows real data
        user = get_user(telegram_id) or {}

        score_by_subject = user.get("score_by_subject", {}) or {}
        subject_correct = user.get("subject_correct", {}) or {}
        subject_wrong = user.get("subject_wrong", {}) or {}
        subject_attempts = user.get("subject_attempts", {}) or {}
        topic_perf = user.get("topic_performance", {}) or {}

        score_by_subject[subject] = score_by_subject.get(subject, 0) + (1 if is_correct else 0)
        subject_correct[subject] = subject_correct.get(subject, 0) + (1 if is_correct else 0)
        subject_wrong[subject] = subject_wrong.get(subject, 0) + (0 if is_correct else 1)
        subject_attempts[subject] = subject_attempts.get(subject, 0) + 1

        safe_topic = (topic or "General").replace(".", "-")
        subject_topic = topic_perf.setdefault(subject, {})
        topic_row = subject_topic.setdefault(safe_topic, {"correct": 0, "attempts": 0})
        topic_row["correct"] = topic_row.get("correct", 0) + (1 if is_correct else 0)
        topic_row["attempts"] = topic_row.get("attempts", 0) + 1

        updates = {
            "score_by_subject": score_by_subject,
            "subject_correct": subject_correct,
            "subject_wrong": subject_wrong,
            "subject_attempts": subject_attempts,
            "topic_performance": topic_perf,
            "correct_total": user.get("correct_total", 0) + (1 if is_correct else 0),
            "wrong_total": user.get("wrong_total", 0) + (0 if is_correct else 1),
            "study_minutes_today": user.get("study_minutes_today", 0) + 2,
            "study_minutes_total": user.get("study_minutes_total", 0) + 2,
            "updated_at": _now(),
        }

        # Persist aggregates back to the users table
        try:
            update_user(telegram_id, updates)
        except Exception:
            logger.exception("Failed to update user aggregates for %s", safe_user_ref(telegram_id))
    except Exception as e:
        logger.error(f"Error recording answer: {e}")

def get_wrong_questions(telegram_id: int, subject: str = None, limit: int = 20) -> list:
    try:
        supabase = _get_supabase()
        query = supabase.table("wrong_questions").select("*").eq("telegram_id", telegram_id)
        if subject:
            query = query.eq("subject", subject)
        response = query.limit(limit).execute()
        return response.data
    except Exception:
        return []

def clear_wrong_questions(telegram_id: int, subject: str = None):
    try:
        supabase = _get_supabase()
        query = supabase.table("wrong_questions").delete().eq("telegram_id", telegram_id)
        if subject:
            query = query.eq("subject", subject)
        query.execute()
    except Exception:
        pass

def save_exam_result(telegram_id: int, subject: str, score: int, total: int, weak_topics: list | None = None) -> bool:
    try:
        supabase = _get_supabase()
        percentage = round((score / total) * 100, 2) if total else 0
        supabase.table("exam_results").insert({
            "telegram_id": telegram_id,
            "subject": subject,
            "score": score,
            "total": total,
            "percentage": percentage,
            "weak_topics": weak_topics or [],
            "taken_at": _now(),
        }).execute()

        user = get_user(telegram_id) or {}
        update_user(telegram_id, {
            "exams_taken": user.get("exams_taken", 0) + 1,
            "updated_at": _now(),
        })
        return True
    except Exception as e:
        logger.error(f"Error saving exam result for user {telegram_id}: {e}")
        return False

def add_feature_suggestion(telegram_id: int, suggestion: str):
    try:
        supabase = _get_supabase()
        supabase.table("feature_suggestions").insert({
            "telegram_id": telegram_id,
            "suggestion": suggestion
        }).execute()
    except Exception:
        pass

def save_feature_suggestion(telegram_id: int, username: str = "", text: str = "", suggestion: str = "", language: str = "en"):
    # Compatibility wrapper for handlers
    add_feature_suggestion(telegram_id, suggestion or text)

def get_user_by_parent_token(token: str) -> dict | None:
    try:
        supabase = _get_supabase()
        resp = supabase.table("users").select("*").eq("parent_token", token).execute()
        return resp.data[0] if resp.data else None
    except Exception: return None

def get_weak_subjects(telegram_id: int) -> dict:
    user = get_user(telegram_id)
    if not user: return {}
    attempts = user.get("subject_attempts", {}) or {}
    correct = user.get("subject_correct", {}) or {}
    result = {}
    for subj, total in attempts.items():
        c = correct.get(subj, 0)
        result[subj] = round(c / total * 100) if total > 0 else 0
    return result

def check_feature_rate_limit(telegram_id: int, feature_name: str, hours: int = 24) -> bool:
    try:
        user = get_user(telegram_id)
        if not user: return False
        last_used = user.get(f"last_{feature_name}_at")
        if last_used:
            now = datetime.now(timezone.utc)
            last_dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
            if now - last_dt < timedelta(hours=hours):
                return False
        update_user(telegram_id, {f"last_{feature_name}_at": _now()})
        return True
    except Exception: return False

def save_confession(telegram_id: int, topic: str):
    # Optional: save to a confessions table if it exists
    pass

def get_boss_fight_week() -> dict | None:
    try:
        supabase = _get_supabase()
        week = datetime.now(timezone.utc).isocalendar()[1]
        year = datetime.now(timezone.utc).year
        resp = supabase.table("boss_fights").select("*").eq("week", week).eq("year", year).execute()
        return resp.data[0] if resp.data else None
    except Exception: return None

def save_boss_fight(question: str, subject: str, model_answer: str | None = None, explanation: str | None = None):
    try:
        supabase = _get_supabase()
        now_dt = datetime.now(timezone.utc)
        week = now_dt.isocalendar()[1]
        year = now_dt.year
        data = {
            "id": f"{year}_{week}",
            "question": question,
            "subject": subject,
            "week": week,
            "year": year,
            "completers": [],
            "created_at": _now()
        }
        if model_answer: data["model_answer"] = model_answer
        if explanation: data["explanation"] = explanation
        supabase.table("boss_fights").upsert(data).execute()
    except Exception as e:
        logger.error(f"Error saving boss fight: {e}")

def complete_boss_fight(telegram_id: int):
    try:
        boss = get_boss_fight_week()
        if not boss: return
        completers = set(boss.get("completers", []) or [])
        completers.add(telegram_id)
        supabase = _get_supabase()
        supabase.table("boss_fights").update({"completers": list(completers)}).eq("id", boss["id"]).execute()
        
        user = get_user(telegram_id)
        if user:
            badges = user.get("badges", []) or []
            if "🏆 Champion" not in badges:
                badges.append("🏆 Champion")
                update_user(telegram_id, {"badges": badges})
    except Exception as e:
        logger.error(f"Error completing boss fight: {e}")

def save_parent_report(telegram_id: int, report_text: str, parent_token: str):
    try:
        supabase = _get_supabase()
        supabase.table("parent_reports").insert({
            "report": report_text,
            "parent_token": parent_token,
            "week": datetime.now(timezone.utc).isocalendar()[1],
            "created_at": _now()
        }).execute()
    except Exception:
        pass

# ── RAG & CACHING HELPERS ───────────────────────────────────────────────────

def get_cached_content(key: str) -> dict | None:
    try:
        supabase = _get_supabase()
        resp = supabase.table("content_cache").select("*").eq("cache_key", key).execute()
        return resp.data[0].get("data") if resp.data else None
    except Exception: return None

def set_cached_content(key: str, data: dict):
    try:
        supabase = _get_supabase()
        supabase.table("content_cache").upsert({"cache_key": key, "data": data, "updated_at": _now()}).execute()
    except Exception: pass

def get_chunks_for_subject(subject: str, limit: int = 10) -> list:
    try:
        supabase = _get_supabase()
        resp = supabase.table("textbook_chunks").select("*").eq("subject", subject).limit(limit).execute()
        return resp.data
    except Exception: return []

def clear_subject_notes_cache(subject: str):
    try:
        supabase = _get_supabase()
        supabase.table("content_cache").delete().ilike("cache_key", f"%{subject}%").execute()
    except Exception: pass

# ── ADMIN & UTILS ──────────────────────────────────────────────────────────

def add_real_question(subject: str, q_data: dict) -> bool:
    try:
        supabase = _get_supabase()
        q_data["subject"] = subject
        supabase.table("real_exam_questions").insert(q_data).execute()
        return True
    except Exception: return False

def save_daily_tip(tip_text: str):
    try:
        supabase = _get_supabase()
        supabase.table("daily_tips").upsert({
            "date": _today(),
            "tip": tip_text,
            "created_at": _now(),
        }).execute()
    except Exception: pass

def is_panic_mode() -> bool:
    # Panic mode is usually 30 days before EUEE. For now, manual toggle or false.
    return False

def check_and_expire_subscriptions(bot_app=None):
    """Scan all users and expire those whose time is up."""
    try:
        supabase = _get_supabase()
        now = _now()
        # Find active subscribers that have expired
        resp = supabase.table("users").select("*")\
            .eq("subscription_active", True)\
            .neq("tier", "free")\
            .lt("subscription_expires_at", now)\
            .execute()
        
        expired_users = resp.data
        for u in expired_users:
            tid = u["telegram_id"]
            old_tier = u["tier"]
            update_user(tid, {
                "tier": "free",
                "subscription_active": False,
                "tier_updated_at": now
            })
            # Log the change
            supabase.table("tier_change_log").insert({
                "telegram_id": tid,
                "old_tier": old_tier,
                "new_tier": "free",
                "reason": "Subscription expired",
                "created_at": now
            }).execute()
            
            logger.info("Subscription expired for %s (was %s)", safe_user_ref(tid), old_tier)
            
            # Notify user if bot app is provided
            if bot_app:
                lang = u.get("language", "en")
                msg = (
                    "🚨 **Subscription Expired**\n\n"
                    "Your premium access has expired. You have been reverted to the free tier.\n"
                    "Upgrade again to keep using premium features! 🚀"
                ) if lang == "en" else (
                    "🚨 **የደንበኝነት ምዝገባዎ አብቅቷል**\n\n"
                    "የፕሪሚየም አገልግሎትዎ አብቅቷል። ወደ ነፃ አገልግሎት ተመልሰዋል።\n"
                    "ፕሪሚየም አገልግሎቶችን መጠቀሙን ለመቀጠል ድጋሚ ያሳድጉ! 🚀"
                )
                import asyncio
                try:
                    asyncio.create_task(bot_app.bot.send_message(chat_id=tid, text=msg, parse_mode="Markdown"))
                except Exception: pass
    except Exception as e:
        logger.error(f"Error in check_and_expire_subscriptions: {e}")

def init_database():
    """REST API doesn't need pool initialization."""
    logger.info("DONE: Supabase REST Client initialized")
    return True
