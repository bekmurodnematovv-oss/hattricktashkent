import logging
import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from datetime import datetime, date

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8246944384:AAGnr7n4dzx4AEBip8GG5NXzu8HIV7B9-8E"
DIRECTOR_CHAT_ID = 7504925076
ADMIN_IDS = [6663841273]

MAX_SLOTS = 20
TEAM_MAX = 5
PRICE_UZS = 45.000

# ─── Stadiums ──────────────────────────────────────────────────────────────────
STADIUMS = {
    "s263": {
        "name_uz": "🏟 263-stadion (Yunusobod) — 18:00",
        "name_ru": "🏟 263 стадион (Юнусабад) — 18:00",
    },
    "s113": {
        "name_uz": "🏟 113-stadion (Sergeli) — 20:00",
        "name_ru": "🏟 113 стадион (Сергели) — 20:00",
    },
    "s311": {
        "name_uz": "🏟 311-stadion (Chilonzor) — 22:00",
        "name_ru": "🏟 311 стадион (Чиланзар) — 22:00",
    },
}

# ─── Teams ─────────────────────────────────────────────────────────────────────
TEAMS = {
    "blue":   {"name_uz": "🔵 Ko'k jamoa",    "name_ru": "🔵 Синяя команда"},
    "red":    {"name_uz": "🔴 Qizil jamoa",   "name_ru": "🔴 Красная команда"},
    "green":  {"name_uz": "🟢 Yashil jamoa",  "name_ru": "🟢 Зелёная команда"},
    "yellow": {"name_uz": "🟡 Sariq jamoa",   "name_ru": "🟡 Жёлтая команда"},
}

# ─── Conversation states ────────────────────────────────────────────────────────
LANG, NAME, PHONE, STADIUM, TEAM, SCREENSHOT = range(6)

# ─── Storage ───────────────────────────────────────────────────────────────────
players = {}            # uid -> player data
pending_payments = {}   # uid -> pending data
team_members = {"blue": [], "red": [], "green": [], "yellow": []}
player_game_date = {}   # uid -> "YYYY-MM-DD"

# ─── Texts ─────────────────────────────────────────────────────────────────────
TEXTS = {
    "welcome_uz": "⚽ <b>Futbol ligasiga xush kelibsiz!</b>\n\nTilni tanlang:",
    "welcome_ru": "⚽ <b>Добро пожаловать в футбольную лигу!</b>\n\nВыберите язык:",
    "ask_name_uz": "✏️ Ismingizni kiriting:",
    "ask_name_ru": "✏️ Введите ваше имя:",
    "ask_phone_uz": "📱 Telefon raqamingizni yuboring:",
    "ask_phone_ru": "📱 Отправьте ваш номер телефона:",
    "ask_stadium_uz": "🏟 Qaysi stadion sizga qulay?",
    "ask_stadium_ru": "🏟 Какой стадион вам больше подходит?",
    "ask_team_uz": "🎽 Qaysi jamoani tanlaysiz?",
    "ask_team_ru": "🎽 Выберите команду:",
    "team_full_uz": "❌ Bu jamoa to'lgan. Boshqa jamoani tanlang.",
    "team_full_ru": "❌ Эта команда заполнена. Выберите другую.",
    "no_slots_uz": "😔 Barcha o'rinlar band. Keyingi o'yin uchun kuting.",
    "no_slots_ru": "😔 Все места заняты. Ожидайте следующей игры.",
    "payment_uz": (
        "💳 <b>To'lov</b>\n\n"
        "Summa: <b>45.000 so'm</b>\n\n"
        "• Click: 8600 4904 1734 5204\n"
        "• Payme: 8600 4904 1734 5204\n\n"
        "✅ To'lovdan so'ng <b>skrinshot</b> yuboring."
    ),
    "payment_ru": (
        "💳 <b>Оплата</b>\n\n"
        "Сумма: <b>45.000 сум</b>\n\n"
        "• Click: 8600 4904 1734 5204\n"
        "• Payme: 8600 4904 1734 5204\n\n"
        "✅ После оплаты отправьте <b>скриншот</b>."
    ),
    "received_uz": "✅ Skrinshot qabul qilindi. Admin tasdiqlashini kuting...",
    "received_ru": "✅ Скриншот получен. Ожидайте подтверждения...",
    "confirmed_uz": "🎉 <b>Tabriklaymiz!</b> To'lovingiz tasdiqlandi va siz jamoaga qo'shildingiz!",
    "confirmed_ru": "🎉 <b>Поздравляем!</b> Ваш платёж подтверждён, вы добавлены в команду!",
    "rejected_uz": "❌ To'lov tasdiqlanmadi. Qayta urinib ko'ring yoki admin bilan bog'laning.",
    "rejected_ru": "❌ Платёж не подтверждён. Попробуйте снова или свяжитесь с администратором.",
    "already_uz": "ℹ️ Siz bugungi o'yin uchun allaqachon ro'yxatdan o'tgansiz.",
    "already_ru": "ℹ️ Вы уже зарегистрированы на сегодняшнюю игру.",
    "help_uz": (
        "ℹ️ <b>Yordam</b>\n\n"
        "/start — Ro'yxatdan o'tish\n"
        "/slots — Bo'sh o'rinlar\n"
        "/mystatus — Mening holatim\n"
        "/help — Yordam"
    ),
    "help_ru": (
        "ℹ️ <b>Помощь</b>\n\n"
        "/start — Регистрация\n"
        "/slots — Свободные места\n"
        "/mystatus — Мой статус\n"
        "/help — Помощь"
    ),
    "status_yes_uz": "✅ <b>Ro'yxatdan o'tgansiz</b>",
    "status_yes_ru": "✅ <b>Вы зарегистрированы</b>",
    "status_pending_uz": "⏳ To'lovingiz ko'rib chiqilmoqda...",
    "status_pending_ru": "⏳ Ваш платёж на рассмотрении...",
    "status_no_uz": "❌ Ro'yxatdan o'tmagansiz. /start yuboring.",
    "status_no_ru": "❌ Вы не зарегистрированы. Отправьте /start.",
    "screenshot_only_uz": "📸 Iltimos, to'lov skrinshot (rasm) yuboring.",
    "screenshot_only_ru": "📸 Пожалуйста, отправьте скриншот оплаты (фото).",
}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", "uz")

def t(key: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    return TEXTS[key + "_" + get_lang(context)]

def total_registered() -> int:
    return sum(len(v) for v in team_members.values())

def available_slots() -> int:
    return MAX_SLOTS - total_registered()

def today_str() -> str:
    return date.today().isoformat()

def is_registered_today(uid: int) -> bool:
    """Returns True only if the player registered TODAY and is confirmed."""
    if uid not in players:
        return False
    if not players[uid].get("confirmed"):
        return False
    return player_game_date.get(uid) == today_str()

def reset_player_if_new_day(uid: int):
    """If the player's last registration was a previous day, clear their data."""
    if uid in players and player_game_date.get(uid, "") != today_str():
        team = players[uid].get("team")
        if team and uid in team_members.get(team, []):
            team_members[team].remove(uid)
        del players[uid]
        player_game_date.pop(uid, None)
        pending_payments.pop(uid, None)
        logger.info(f"Player {uid} reset for new day.")

def team_status(lang: str) -> str:
    lines = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        bar = "🟩" * count + "⬜" * (TEAM_MAX - count)
        lines.append(f"{team['name_' + lang]}: {bar} {count}/{TEAM_MAX}")
    return "\n".join(lines)

# ─── Keyboards ─────────────────────────────────────────────────────────────────

def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский",   callback_data="lang_ru"),
    ]])

def stadium_kb(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, stadium in STADIUMS.items():
        buttons.append([InlineKeyboardButton(stadium["name_" + lang], callback_data="stad_" + key)])
    return InlineKeyboardMarkup(buttons)

def team_kb(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        name = team["name_" + lang]
        if count < TEAM_MAX:
            buttons.append([InlineKeyboardButton(f"{name}  ({count}/{TEAM_MAX})", callback_data="team_" + key)])
        else:
            buttons.append([InlineKeyboardButton(f"{name}  ✗ FULL", callback_data="team_full")])
    return InlineKeyboardMarkup(buttons)

def phone_kb(lang: str) -> ReplyKeyboardMarkup:
    label = "📱 Raqamni yuborish" if lang == "uz" else "📱 Отправить номер"
    return ReplyKeyboardMarkup(
        [[KeyboardButton(label, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ─── Conversation Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    reset_player_if_new_day(uid)

    if is_registered_today(uid):
        lang = get_lang(context)
        await update.message.reply_text(TEXTS["already_" + lang], parse_mode="HTML")
        return ConversationHandler.END

    if available_slots() <= 0:
        lang = get_lang(context)
        await update.message.reply_text(TEXTS["no_slots_" + lang], parse_mode="HTML")
        return ConversationHandler.END

    # Clear stale user_data from previous incomplete session
    context.user_data.clear()

    await update.message.reply_text(
        TEXTS["welcome_uz"] + "\n\n" + TEXTS["welcome_ru"],
        reply_markup=lang_kb(),
        parse_mode="HTML"
    )
    return LANG


async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lang"] = query.data.split("_")[1]
    await query.edit_message_text(t("ask_name", context), parse_mode="HTML")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text(t("ask_name", context))
        return NAME
    context.user_data["name"] = name
    lang = get_lang(context)
    await update.message.reply_text(
        t("ask_phone", context),
        reply_markup=phone_kb(lang),
        parse_mode="HTML"
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ✅ FIX: Accept both contact share and manual text input
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    else:
        context.user_data["phone"] = update.message.text.strip()

    lang = get_lang(context)

    # ✅ FIX: Single message — removes reply keyboard AND shows stadium inline keyboard together
    await update.message.reply_text(
        t("ask_stadium", context),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    # Send stadium inline keyboard as a separate follow-up message
    await update.message.reply_text(
        "👇",
        reply_markup=stadium_kb(lang)
    )
    return STADIUM


async def choose_stadium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # ✅ FIX: Properly parse stadium key (split on first underscore only)
    stad_key = query.data.split("_", 1)[1]

    if stad_key not in STADIUMS:
        await query.answer("❌ Noto'g'ri stadion.", show_alert=True)
        return STADIUM

    context.user_data["stadium"] = stad_key
    lang = get_lang(context)
    stad_name = STADIUMS[stad_key]["name_" + lang]

    await query.edit_message_text(
        f"{'✅ Tanlandi' if lang == 'uz' else '✅ Выбрано'}: {stad_name}\n\n{t('ask_team', context)}",
        reply_markup=team_kb(lang),
        parse_mode="HTML"
    )
    return TEAM


async def choose_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "team_full":
        await query.answer(t("team_full", context), show_alert=True)
        return TEAM

    team_key = query.data.split("_", 1)[1]

    if team_key not in TEAMS:
        await query.answer("❌ Noto'g'ri jamoa.", show_alert=True)
        return TEAM

    if len(team_members[team_key]) >= TEAM_MAX:
        await query.answer(t("team_full", context), show_alert=True)
        return TEAM

    context.user_data["team"] = team_key
    await query.edit_message_text(t("payment", context), parse_mode="HTML")
    return SCREENSHOT


async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    # ✅ FIX: Only accept photos, reject other file types with clear message
    if not update.message.photo:
        await update.message.reply_text(t("screenshot_only", context))
        return SCREENSHOT

    lang = get_lang(context)
    stad_key = context.user_data.get("stadium", "")
    stad_name = STADIUMS[stad_key]["name_" + lang] if stad_key in STADIUMS else "—"
    team_key = context.user_data.get("team", "")
    team_name = TEAMS[team_key]["name_" + lang] if team_key in TEAMS else "—"

    pending_payments[uid] = {
        "name":     context.user_data.get("name", "—"),
        "phone":    context.user_data.get("phone", "—"),
        "team":     team_key,
        "stadium":  stad_key,
        "lang":     lang,
        "user_id":  uid,
        "username": user.username or "—",
    }

    await update.message.reply_text(t("received", context), parse_mode="HTML")

    p = pending_payments[uid]
    caption = (
        f"💰 <b>Yangi to'lov / Новый платёж</b>\n\n"
        f"👤 {p['name']}\n"
        f"📱 {p['phone']}\n"
        f"🏟 {stad_name}\n"
        f"🎽 {team_name}\n"
        f"🔗 @{p['username']} (ID: {uid})"
    )
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_" + str(uid)),
        InlineKeyboardButton("❌ Rad etish",  callback_data="reject_"  + str(uid)),
    ]])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id,
                update.message.photo[-1].file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=buttons
            )
        except Exception as e:
            logger.error(f"Admin notify error (admin {admin_id}): {e}")

    return ConversationHandler.END

# ─── Admin: Confirm / Reject ───────────────────────────────────────────────────

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    # ✅ FIX: Safely split action and uid
    parts = query.data.split("_", 1)
    if len(parts) != 2:
        return
    action, uid_str = parts
    try:
        uid = int(uid_str)
    except ValueError:
        return

    if uid not in pending_payments:
        await query.edit_message_caption("⚠️ Bu to'lov allaqachon ko'rib chiqilgan.")
        return

    player = pending_payments.pop(uid)
    lang = player["lang"]
    stad_key = player.get("stadium", "")
    stad_name = STADIUMS[stad_key]["name_" + lang] if stad_key in STADIUMS else "—"

    if action == "confirm":
        team_key = player["team"]
        # ✅ FIX: Double-check team isn't full before confirming
        if len(team_members.get(team_key, [])) >= TEAM_MAX:
            await context.bot.send_message(
                uid,
                TEXTS["team_full_" + lang],
                parse_mode="HTML"
            )
            await query.edit_message_caption(f"⚠️ Jamoa to'lgan, tasdiqlab bo'lmadi: {player['name']}")
            return

        team_members[team_key].append(uid)
        players[uid] = {**player, "confirmed": True, "confirmed_at": datetime.now().isoformat()}
        player_game_date[uid] = today_str()

        team_name = TEAMS[team_key]["name_" + lang]
        msg = (
            TEXTS["confirmed_" + lang] +
            f"\n\n🎽 {team_name}\n🏟 {stad_name}"
        )
        await context.bot.send_message(uid, msg, parse_mode="HTML")
        await query.edit_message_caption(f"✅ Tasdiqlandi: {player['name']}")

        # Notify director
        if DIRECTOR_CHAT_ID:
            director_msg = (
                f"🆕 <b>Yangi o'yinchi!</b>\n\n"
                f"👤 {player['name']}\n"
                f"📱 {player['phone']}\n"
                f"🏟 {stad_name}\n"
                f"🎽 {TEAMS[team_key]['name_uz']}\n"
                f"📊 Jami: {total_registered()}/{MAX_SLOTS}\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            try:
                await context.bot.send_message(DIRECTOR_CHAT_ID, director_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Director notify error: {e}")
    else:
        await context.bot.send_message(uid, TEXTS["rejected_" + lang], parse_mode="HTML")
        await query.edit_message_caption(f"❌ Rad etildi: {player['name']}")

# ─── Public Commands ───────────────────────────────────────────────────────────

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    slots = available_slots()
    header = (
        f"📊 <b>Bo'sh o'rinlar: {slots}/{MAX_SLOTS}</b>"
        if lang == "uz" else
        f"📊 <b>Свободных мест: {slots}/{MAX_SLOTS}</b>"
    )
    await update.message.reply_text(header + "\n\n" + team_status(lang), parse_mode="HTML")


async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(context)
    reset_player_if_new_day(uid)

    if uid in players and players[uid].get("confirmed"):
        p = players[uid]
        team_name = TEAMS[p["team"]]["name_" + lang]
        stad_key = p.get("stadium", "")
        stad_name = STADIUMS[stad_key]["name_" + lang] if stad_key in STADIUMS else "—"
        msg = (
            TEXTS["status_yes_" + lang] +
            f"\n\n👤 {p['name']}\n📱 {p['phone']}\n🏟 {stad_name}\n🎽 {team_name}"
        )
    elif uid in pending_payments:
        msg = TEXTS["status_pending_" + lang]
    else:
        msg = TEXTS["status_no_" + lang]

    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(TEXTS["help_" + lang], parse_mode="HTML")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: list all registered players per team."""
    if update.effective_user.id not in ADMIN_IDS:
        return

    total = total_registered()
    lines = [f"📋 <b>Jamoalar ro'yxati</b>  |  Jami: {total}/{MAX_SLOTS}\n"]

    for team_key, team in TEAMS.items():
        members_uids = team_members[team_key]
        team_name = team["name_uz"]
        count = len(members_uids)
        bar = "🟩" * count + "⬜" * (TEAM_MAX - count)
        lines.append(f"{team_name}  {bar}  <b>{count}/{TEAM_MAX}</b>")

        if members_uids:
            for i, uid in enumerate(members_uids, 1):
                p = players.get(uid)
                if p:
                    stad_key = p.get("stadium", "")
                    stad_name = STADIUMS[stad_key]["name_uz"] if stad_key in STADIUMS else "—"
                    lines.append(f"  {i}. {p['name']}  |  {p['phone']}  |  {stad_name}")
        else:
            lines.append("  — (bo'sh)")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(
        "/help yuboring." if lang == "uz" else "Отправьте /help."
    )

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG:       [CallbackQueryHandler(set_lang,       pattern="^lang_")],
            NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE:      [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_phone)],
            STADIUM:    [CallbackQueryHandler(choose_stadium, pattern="^stad_")],
            TEAM:       [CallbackQueryHandler(choose_team,    pattern="^team_")],
            SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
        conversation_timeout=600,  # 10-minute timeout per session
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(confirm|reject)_"))
    app.add_handler(CommandHandler("slots",    cmd_slots))
    app.add_handler(CommandHandler("mystatus", cmd_mystatus))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("list",     cmd_list))
    app.add_handler(MessageHandler(filters.ALL, fallback))

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
