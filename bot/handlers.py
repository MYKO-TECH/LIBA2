import re
import json
import logging
from .knowledge_loader import text_summary
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import config
from .sessions import (
    get_session,
    update_session,
    check_rate_limit,
    log_security_event,
)
from .ai_service import AIService
from .knowledge_loader import get_knowledge

logger = logging.getLogger(__name__)
ai_service = AIService()


# ──────────────────────────────
# Helper – format outgoing text
# ──────────────────────────────
def format_message(header: str, content: str) -> str:
    return (
        "🎓 ACT-AI | ACT\n"
        + "-" * 30
        + f"\n🚩 {header}\n"
        + "-" * 30
        + f"\n{content}\n\n"
        "🔗 [www.act.edu.et](http://www.act.edu.et)"
    )


# ──────────────────────────────
# /start  and /help
# ──────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = format_message(
        "WELCOME TO ACT",
        (
            "Official digital assistant for American College of Technology\n"
            "• Student registration & payment assistance\n"
            "• Academic schedule management\n"
            "• Exam date notifications (Mid/Final)\n"
            "• Guidance on grade information access\n"
            "• School event announcements\n\n"
            "ℹ️ Services I can help with:\n"
            "1. Course Information & Fees\n"
            "2. Cybersecurity Training Details\n"
            "3. Master's Program Info\n"
            "4. Certificate Collection Info\n"
            "5. How to Access Grades (guidance)\n\n"
            "Type /help for assistance options or ask your question."
        ),
    )
    await update.message.reply_text(welcome_msg)
    await update_session(str(update.effective_user.id), {"new_user": True})


# ──────────────────────────────
# Pre‑defined “quick reply” handlers
# ──────────────────────────────
async def handle_cybersecurity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    knowledge = get_knowledge()
    cyber = knowledge["courses"]["cybersecurity_training"]
    response = format_message(
        "CYBERSECURITY TRAINING 🔒",
        (
            f"🗓️ Schedule: {cyber['schedule']}\n"
            f"📍 Location: {cyber['location']}\n"
            f"💰 Price: {cyber['price']} {cyber.get('currency', 'Br')}\n"
            f"📞 Contact: {knowledge['contacts']['phone']}\n\n"
            f"🔖 Discount: {cyber['discount']}\n"
            "📲 Paid students join: t.me/cyber_classes_act"
        ),
    )
    await update.message.reply_text(response)


# === NEW CODE START – extra quick‑reply handlers ===============================

async def handle_course_fees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show tuition / course fee table.
    Looks up `knowledge['courses']` and lists name + price.
    """
    knowledge = get_knowledge()
    output_lines = []
    for course_key, course in knowledge["courses"].items():
        price = course.get("price")
        if price:
            output_lines.append(f"• {course['title']}: {price} {course.get('currency', 'Br')}")
    content = "\n".join(output_lines) or "No fee data found."
    await update.message.reply_text(format_message("COURSE FEES 💰", content))


async def handle_certificates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Tell students how to collect certificates.
    """
    k = get_knowledge()
    cert = k.get("certificate_info", {})
    content = (
        f"🏢 Pick‑up office: {cert.get('office', 'Registrar')}\n"
        f"🕒 Hours: {cert.get('hours', 'Mon‑Fri 8 AM‑5 PM')}\n"
        f"📞 Call: {k['contacts']['phone']}"
    )
    await update.message.reply_text(format_message("CERTIFICATE COLLECTION 🎓", content))


async def handle_masters_programs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Describe available master’s programs.
    """
    k = get_knowledge()
    masters = k.get("masters_programs", [])
    if not masters:
        await update.message.reply_text(format_message("MASTER’S PROGRAMS", "No programs listed yet."))
        return

    lines = [f"• {m['title']} ({m['duration']})" for m in masters]
    await update.message.reply_text(format_message("MASTER’S PROGRAMS 🎓", "\n".join(lines)))


async def handle_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Explain how to view grades on the portal.
    """
    content = (
        "1️⃣ Log in to the student portal → portal.act.edu.et\n"
        "2️⃣ Click **Academics → Grades**\n"
        "3️⃣ Choose the semester and press **View**\n\n"
        "If you have trouble logging in, contact the registrar."
    )
    await update.message.reply_text(format_message("VIEWING GRADES 📊", content))


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send campus location.
    """
    k = get_knowledge()
    loc = k.get("location", {})
    google_maps = loc.get("maps_link", "https://maps.app.goo.gl/...")

    content = (
        f"📍 Address: {loc.get('address','ACT Main Campus')}\n"
        f"🌐 Google Maps: {google_maps}"
    )
    await update.message.reply_text(format_message("ACT LOCATION 🗺️", content))

# === NEW CODE END ==============================================================


# ──────────────────────────────
# General incoming text handler
# ──────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text.lower()
    session = await get_session(user_id)

    logger.info(f"Message from {user_id}: {user_message[:50]}...")

    # Rate‑limit check
    if not await check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Too many requests. Please wait 1 minute.")
        return

    # ID verification flow
    if session.get("awaiting_id"):
        await handle_id_verification(update, context, user_message, user_id)
        return

    # Keywords → handler
    handlers = [
        (["cybersecurity", "cyber security training"], handle_cybersecurity),
        (["course fee", "price", "cost"], handle_course_fees),
        (["certificate", "completion"], handle_certificates),
        (["master", "postgraduate"], handle_masters_programs),
        (["grade", "result", "mark"], handle_grades),
        (["location", "address"], handle_location),
        (["contact", "phone", "call"], handle_contact_request),
    ]

    for triggers, handler in handlers:
        if any(trigger in user_message for trigger in triggers):
            await handler(update, context)
            return

    # Fallback to GPT
    await handle_ai_fallback(update, user_message)


# ──────────────────────────────
# GPT fallback
# ──────────────────────────────
async def handle_ai_fallback(update: Update, user_message: str):
    knowledge = text_summary(get_knowledge())
    try:
        response = await ai_service.get_response(user_message, knowledge)
        await update.message.reply_text(format_message("ACT RESPONSE 📌", response))
    except Exception as e:
        logger.error(f"AI Fallback Error: {str(e)}")
        contacts = get_knowledge()["contacts"]
        await update.message.reply_text(
            format_message(
                "SYSTEM ERROR ⚠️",
                f"Technical difficulty. Please contact: {contacts['phone']}",
            )
        )

async def handle_contact_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    knowledge = get_knowledge()
    contacts = knowledge['contacts']
    response = format_message(
        "CONTACT ACT 📞",
        f"📱 General: {contacts['phone']}\n"
        f"📞 Office: {contacts['office_phone']}\n"
        f"📧 Email: {contacts['email']}"
    )
    await update.message.reply_text(response)
# ──────────────────────────────
# ID verification helper
# ──────────────────────────────
async def handle_id_verification(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
    user_id: str,
):
    if re.fullmatch(r"^ACT-\d{4}-\d{2}$", user_message, re.IGNORECASE):
        await update_session(
            user_id,
            {"student_id": user_message.upper(), "id_verified": True, "awaiting_id": False},
        )
        await update.message.reply_text(format_message("ID VALIDATED ✅", "How can I assist you?"))
    else:
        await update.message.reply_text(
            format_message(
                "INVALID ID FORMAT ❌",
                "Correct format: ACT-1234-56\n"
                f"Contact: {get_knowledge()['contacts']['phone']}",
            )
        )
        log_security_event(user_id, "Invalid ID format attempted")


# ──────────────────────────────
# Admin-only knowledge update
# ──────────────────────────────
async def update_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != config.ADMIN_ID:
        log_security_event(user_id, "Unauthorized knowledge update attempt")
        await update.message.reply_text("❌ Administrator authorization required")
        return

    try:
        new_data = json.loads(update.message.text.split(" ", 1)[1])
        current_knowledge = get_knowledge()
        updated = current_knowledge.deep_merge(new_data)
        save_knowledge(updated)

        await update.message.reply_text(
            format_message("KNOWLEDGE UPDATED ✅", f"Updated: {', '.join(new_data.keys())}")
        )
        logger.info(f"Knowledge updated by {user_id}")

    except (IndexError, json.JSONDecodeError) as e:
        await update.message.reply_text(format_message("UPDATE FAILED ❌", f"Invalid format: {e}"))
    except Exception as e:
        await update.message.reply_text(format_message("UPDATE FAILED ❌", f"Error: {e}"))
        logger.error(f"Knowledge update error: {e}")


# ──────────────────────────────
# Export list of handlers
# ──────────────────────────────
def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("help", start),
        CommandHandler("update_knowledge", update_knowledge),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
    ]
