import logging
import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from datetime import datetime
import json

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DIRECTOR_CHAT_ID = int(os.getenv("DIRECTOR_CHAT_ID", "0"))  # Director's Telegram ID
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x]

# League settings
MAX_SLOTS = 20          # Total players allowed
TEAM_MAX   = 5          # Max players per team
PRICE_UZS  = 150000     # Registration fee in UZS

TEAMS = {
    "blue":   {"name_uz": "🔵 Ko'k jamoa",   "name_ru": "🔵 Синяя команда",   "members": []},
    "red":    {"name_uz": "🔴 Qizil jamoa",  "name_ru": "🔴 Красная команда",  "members": []},
    "green":  {"name_uz": "🟢 Yashil jamoa", "name_ru": "🟢 Зелёная команда", "members": []},
    "yellow": {"name_uz": "🟡 Sariq jamoa",  "name_ru": "🟡 Жёлтая команда",  "members": []},
}

# Conversation states
LANG, NAME, PHONE, TEAM, PAYMENT, SCREENSHOT = range(6)

# In-memory storage (replace with a real DB for production)
players = {}       # user_id -> player data
pending_payments = {}  # user_id -> awaiting admin confirmation

# ─── Texts ─────────────────────────────────────────────────────────────────────
T = {
    "welcome": {
        "uz": "⚽ <b>Futbol ligasiga xush kelibsiz!</b>\n\nTilni tanlang:",
        "ru": "⚽ <b>Добро пожаловать в футбольную лигу!</b>\n\nВыберите язык:"
    },
    "ask_name": {
        "uz": "Ismingizni kiriting:",
        "ru": "Введите ваше имя:"
    },
    "ask_phone": {
        "uz": "Telefon raqamingizni yuboring:",
        "ru": "Отправьте ваш номер телефона:"
    },
    "ask_team": {
        "uz": "Qaysi jamoani tanlaysiz?",
        "ru": "Выберите команду:"
    },
    "team_full": {
        "uz": "❌ Bu jamoa to'lgan. Boshqa jamoani tanlang.",
        "ru": "❌ Эта команда заполнена. Выберите другую."
    },
    "no_slots": {
        "uz": "😔 Afsuski, barcha o'rinlar band.\n\nBo'sh o'rin chiqsa, sizga xabar beramiz!",
        "ru": "😔 К сожалению, все места заняты.\n\nМы уведомим вас, когда появятся свободные места!"
    },
    "ask_payment": {
        "uz": (
            f"💳 <b>To'lov ma'lumotlari</b>\n\n"
            f"Summa: <b>{PRICE_UZS:,} so'm</b>\n\n"
            f"To'lov usullari:\n"
            f"• <b>Click</b>: 9860 1234 5678 9012\n"
            f"• <b>Payme</b>: 8600 0987 6543 2109\n\n"
            f"To'lovni amalga oshirgach, skrinshot yuboring."
        ),
        "ru": (
            f"💳 <b>Данные для оплаты</b>\n\n"
            f"Сумма: <b>{PRICE_UZS:,} сум</b>\n\n"
            f"Способы оплаты:\n"
            f"• <b>Click</b>: 9860 1234 5678 9012\n"
            f"• <b>Payme</b>: 8600 0987 6543 2109\n\n"
            f"После оплаты отправьте скриншот."
        )
    },
    "payment_received": {
        "uz": "✅ Skrinshot qabul qilindi. Admin tasdiqlashini kuting...",
        "ru": "✅ Скриншот получен. Ожидайте подтверждения администратора..."
    },
    "payment_confirmed": {
        "uz": "🎉 <b>Tabriklaymiz!</b> To'lovingiz tasdiqlandi.\n\nSiz {team} ga qo'shildingiz!\n\nO'yin tafsilotlari keyinroq yuboriladi.",
        "ru": "🎉 <b>Поздравляем!</b> Ваш платёж подтверждён.\n\nВы добавлены в {team}!\n\nДетали матча будут отправлены позже."
    },
    "payment_rejected": {
        "uz": "❌ To'lov tasdiqlanmadi. Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning.",
        "ru": "❌ Платёж не подтверждён. Пожалуйста, попробуйте снова или свяжитесь с администратором."
    },
    "already_registered": {
        "uz": "ℹ️ Siz allaqachon ro'yxatdan o'tgansiz.",
        "ru": "ℹ️ Вы уже зарегистрированы."
    },
    "slots_info": {
        "uz": "📊 <b>Bo'sh o'rinlar:</b> {slots} ta\n\nJamoa holati:\n{teams}",
        "ru": "📊 <b>Свободные мест:</b> {slots}\n\nСостояние команд:\n{teams}"
    },
    "help": {
        "uz": (
            "ℹ️ <b>Yordam</b>\n\n"
            "/start — Ro'yxatdan o'tish\n"
            "/slots — Bo'sh o'rinlarni ko'rish\n"
            "/mystatus — Mening holatim\n"
            "/help — Yordam\n\n"
            "Savollar uchun: @admin_username"
        ),
        "ru": (
            "ℹ️ <b>Помощь</b>\n\n"
            "/start — Регистрация\n"
            "/slots — Свободные места\n"
            "/mystatus — Мой статус\n"
            "/help — Помощь\n\n"
            "По вопросам: @admin_username"
        )
    }
}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "uz")

def t(key: str, context: ContextTypes.DEFAULT_TYPE, **kwargs) -> str:
    lang = get_lang(context)
    text = T[key][lang]
    return text.format(**kwargs) if kwargs else text

def total_registered() -> int:
    return sum(len(v["members"]) for v in TEAMS.values())

def available_slots() -> int:
    return MAX_SLOTS - total_registered()

def team_status_text(lang: str) -> str:
    lines = []
    for key, team in TEAMS.items():
        name = team[f"name_{lang}"]
        count = len(team["members"])
        bar = "🟩" * count + "⬜" * (TEAM_MAX - count)
        lines.append(f"{name}: {bar} {count}/{TEAM_MAX}")
    return "\n".join(lines)

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
         InlineKeyboardButton("🇷🇺 Русский",   callback_data="lang_ru")]
    ])

def team_keyboard(lang: str):
    buttons = []
    for key, team in TEAMS.items():
        count = len(team["members"])
        if count < TEAM_MAX:
            label = f"{team[f'name_{lang}']}  ({count}/{TEAM_MAX})"
            buttons.append([InlineKeyboardButton(label, callback_data=f"team_{key}")])
        else:
            label = f"{team[f'name_{lang}']}  ✗ FULL"
            buttons.append([InlineKeyboardButton(label, callback_data="team_full")])
    return InlineKeyboardMarkup(buttons)

def phone_keyboard(lang: str):
    btn_text = "📱 Raqamni yuborish" if lang == "uz" else "📱 Отправить номер"
    return ReplyKeyboardMarkup(
        [[KeyboardButton(btn_text, request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

async def notify_director(app: Application, player: dict):
    if not DIRECTOR_CHAT_ID:
        return
    team_key = player.get("team", "—")
    team_name = TEAMS[team_key]["name_uz"] if team_key in TEAMS else "—"
    msg = (
        f"🆕 <b>Yangi o'yinchi ro'yxatdan o'tdi!</b>\n\n"
        f"👤 Ism: {player['name']}\n"
        f"📱 Tel: {player['phone']}\n"
        f"🎽 Jamoa: {team_name}\n"
        f"💰 To'lov: ✅ Tasdiqlangan\n"
        f"🕐 Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📊 Jami ro'yxatdan o'tganlar: {total_registered()}/{MAX_SLOTS}"
    )
    try:
        await app.bot.send_message(DIRECTOR_CHAT_ID, msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify director: {e}")

# ─── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id in players and players[user_id].get("confirmed"):
        await update.message.reply_text(t("already_registered", context), parse_mode="HTML")
        return ConversationHandler.END

    if available_slots() <= 0:
        await update.message.reply_text(t("no_slots", context), parse_mode="HTML")
        return ConversationHandler.END

    await update.message.reply_text(
        T["welcome"]["uz"] + "\n\n" + T["welcome"]["ru"],
        reply_markup=lang_keyboard(), parse_mode="HTML"
    )
    return LANG


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    await query.edit_message_text(t("ask_name", context), parse_mode="HTML")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text(t("ask_name", context))
        return NAME
    context.user_data["name"] = name
    lang = get_lang(context)
    await update.message.reply_text(
        t("ask_phone", context),
        reply_markup=phone_keyboard(lang)
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()
    context.user_data["phone"] = phone

    from telegram import ReplyKeyboardRemove
    await update.message.reply_text(
        t("ask_team", context),
        reply_markup=ReplyKeyboardRemove()
    )
    lang = get_lang(context)
    await update.message.reply_text(
        team_status_text(lang),
        reply_markup=team_keyboard(lang),
        parse_mode="HTML"
    )
    return TEAM


async def choose_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "team_full":
        await query.message.reply_text(t("team_full", context))
        return TEAM

    team_key = query.data.split("_")[1]
    if len(TEAMS[team_key]["members"]) >= TEAM_MAX:
        await query.message.reply_text(t("team_full", context))
        return TEAM

    context.user_data["team"] = team_key
    await query.edit_message_text(t("ask_payment", context), parse_mode="HTML")
    return PAYMENT


async def handle_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # User acknowledged payment instructions — ask for screenshot
    await update.message.reply_text(t("ask_payment", context), parse_mode="HTML")
    return SCREENSHOT


async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = user.id

    # Accept photo or document as proof
    if not (update.message.photo or update.message.document):
        await update.message.reply_text(
            "📸 Iltimos, to'lov skrinshot sifatida yuboring.\n"
            "Пожалуйста, отправьте скриншот оплаты."
        )
        return SCREENSHOT

    # Store pending
    pending_payments[user_id] = {
        "name":  context.user_data.get("name"),
        "phone": context.user_data.get("phone"),
        "team":  context.user_data.get("team"),
        "lang":  get_lang(context),
        "user_id": user_id,
        "username": user.username or "—"
    }

    await update.message.reply_text(t("payment_received", context), parse_mode="HTML")

    # Forward screenshot + confirm/reject buttons to admins
    caption = (
        f"💰 <b>To'lov skrinshoti</b>\n\n"
        f"👤 {pending_payments[user_id]['name']}\n"
        f"📱 {pending_payments[user_id]['phone']}\n"
        f"🎽 {TEAMS[pending_payments[user_id]['team']]['name_uz']}\n"
        f"🔗 @{pending_payments[user_id]['username']}"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{user_id}"),
            InlineKeyboardButton("❌ Rad etish",  callback_data=f"reject_{user_id}")
        ]
    ])

    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await update.get_bot().send_photo(
                    admin_id,
                    update.message.photo[-1].file_id,
                    caption=caption, parse_mode="HTML",
                    reply_markup=buttons
                )
            else:
                await update.get_bot().send_document(
                    admin_id,
                    update.message.document.file_id,
                    caption=caption, parse_mode="HTML",
                    reply_markup=buttons
                )
        except Exception as e:
            logger.error(f"Failed to forward to admin {admin_id}: {e}")

    return ConversationHandler.END


# ─── Admin: confirm / reject payment ──────────────────────────────────────────

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = update.effective_user.id

    if admin_id not in ADMIN_IDS:
        await query.answer("❌ Ruxsat yo'q.", show_alert=True)
        return

    action, uid = query.data.split("_", 1)
    uid = int(uid)

    if uid not in pending_payments:
        await query.edit_message_caption("⚠️ Bu so'rov allaqachon ko'rib chiqilgan.")
        return

    player = pending_payments.pop(uid)

    if action == "confirm":
        # Add to team
        TEAMS[player["team"]]["members"].append(uid)
        players[uid] = {**player, "confirmed": True, "confirmed_at": datetime.now().isoformat()}

        lang = player["lang"]
        team_name = TEAMS[player["team"]][f"name_{lang}"]
        msg = T["payment_confirmed"][lang].format(team=team_name)
        await context.bot.send_message(uid, msg, parse_mode="HTML")
        await query.edit_message_caption(f"✅ Tasdiqlandi — {player['name']}")

        # Notify director
        await notify_director(context.application, players[uid])

        # Broadcast slot update if running low
        if available_slots() <= 3:
            await broadcast_slots_warning(context.application)

    else:
        msg = T["payment_rejected"][player["lang"]]
        await context.bot.send_message(uid, msg, parse_mode="HTML")
        await query.edit_message_caption(f"❌ Rad etildi — {player['name']}")


async def broadcast_slots_warning(app: Application):
    slots = available_slots()
    for uid, p in players.items():
        if not p.get("confirmed"):
            continue
    # Notify admins too
    msg = f"⚠️ Faqat <b>{slots} ta</b> bo'sh o'rin qoldi!\n⚠️ Осталось всего <b>{slots} мест</b>!"
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.send_message(admin_id, msg, parse_mode="HTML")
        except Exception:
            pass


# ─── Public commands ───────────────────────────────────────────────────────────

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    slots = available_slots()
    teams_text = team_status_text(lang)
    msg = T["slots_info"][lang].format(slots=slots, teams=teams_text)
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(context)
    if uid in players and players[uid].get("confirmed"):
        p = players[uid]
        team_name = TEAMS[p["team"]][f"name_{lang}"]
        msg = (
            f"✅ <b>Ro'yxatdan o'tgansiz</b>\n\n"
            f"👤 {p['name']}\n"
            f"📱 {p['phone']}\n"
            f"🎽 {team_name}"
        ) if lang == "uz" else (
            f"✅ <b>Вы зарегистрированы</b>\n\n"
            f"👤 {p['name']}\n"
            f"📱 {p['phone']}\n"
            f"🎽 {team_name}"
        )
    elif uid in pending_payments:
        msg = "⏳ To'lovingiz ko'rib chiqilmoqda..." if lang == "uz" else "⏳ Ваш платёж на рассмотрении..."
    else:
        msg = "❌ Siz ro'yxatdan o'tmagansiz.\n/start buyrug'ini yuboring." if lang == "uz" \
              else "❌ Вы не зарегистрированы.\nОтправьте /start."
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(T["help"][lang], parse_mode="HTML")


async def cmd_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not players:
        await update.message.reply_text("Hozircha hech kim ro'yxatdan o'tmagan.")
        return
    lines = ["📋 <b>Ro'yxatdan o'tganlar:</b>\n"]
    for i, (uid, p) in enumerate(players.items(), 1):
        team_name = TEAMS[p["team"]]["name_uz"]
        lines.append(f"{i}. {p['name']} | {p['phone']} | {team_name}")
    lines.append(f"\n<b>Jami:</b> {total_registered()}/{MAX_SLOTS}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    msg = (
        "❓ Tushunmadim. /help buyrug'ini yuboring."
        if lang == "uz" else
        "❓ Не понял. Отправьте /help."
    )
    await update.message.reply_text(msg)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG:       [CallbackQueryHandler(set_language, pattern="^lang_")],
            NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE:      [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_phone)],
            TEAM:       [CallbackQueryHandler(choose_team, pattern="^team_")],
            PAYMENT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_info)],
            SCREENSHOT: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_screenshot)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(confirm|reject)_"))
    app.add_handler(CommandHandler("slots",   cmd_slots))
    app.add_handler(CommandHandler("mystatus", cmd_mystatus))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("list",    cmd_admin_list))
    app.add_handler(MessageHandler(filters.ALL, fallback))

    logger.info("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
