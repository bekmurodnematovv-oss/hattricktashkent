import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from datetime import datetime, date, time
import pytz

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8246944384:AAGnr7n4dzx4AEBip8GG5NXzu8HIV7B9-8E"
DIRECTOR_CHAT_ID = 7504925076
ADMIN_IDS = [6663841273]

MAX_SLOTS = 20
TEAM_MAX = 5
PRICE_UZS = 45000

TIMEZONE = pytz.timezone("Asia/Tashkent")

# ─── Stadiums ──────────────────────────────────────────────────────────────────
STADIUMS = {
    "s263": {
        "name_uz": "🏟 263-stadion (Yunusobod) — 18:00",
        "name_ru": "🏟 263 стадион (Юнусабад) — 18:00",
        "hour": 18,
    },
    "s113": {
        "name_uz": "🏟 113-stadion (Sergeli) — 20:00",
        "name_ru": "🏟 113 стадион (Сергели) — 20:00",
        "hour": 20,
    },
    "s311": {
        "name_uz": "🏟 311-stadion (Chilonzor) — 22:00",
        "name_ru": "🏟 311 стадион (Чиланзар) — 22:00",
        "hour": 22,
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
BROADCAST_MSG = 10
CANCEL_CONFIRM = 11

# ─── Storage ───────────────────────────────────────────────────────────────────
players = {}            # uid -> player data
pending_payments = {}   # uid -> pending data
team_members = {"blue": [], "red": [], "green": [], "yellow": []}
player_game_date = {}   # uid -> "YYYY-MM-DD"
daily_stats = {}        # "YYYY-MM-DD" -> {"total": int, "teams": {...}, "stadiums": {...}}

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
        "Summa: <b>45,000 so'm</b>\n\n"
        "• Click: 8600 4904 1734 5204\n"
        "• Payme: 8600 4904 1734 5204\n\n"
        "✅ To'lovdan so'ng <b>skrinshot</b> yuboring."
    ),
    "payment_ru": (
        "💳 <b>Оплата</b>\n\n"
        "Сумма: <b>45,000 сум</b>\n\n"
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
        "/cancel — Ro'yxatdan chiqish\n"
        "/help — Yordam"
    ),
    "help_ru": (
        "ℹ️ <b>Помощь</b>\n\n"
        "/start — Регистрация\n"
        "/slots — Свободные места\n"
        "/mystatus — Мой статус\n"
        "/cancel — Отменить регистрацию\n"
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
    # Cancellation
    "cancel_confirm_uz": (
        "⚠️ <b>Ro'yxatdan chiqmoqchimisiz?</b>\n\n"
        "❗ Diqqat: <b>To'lov qaytarilmaydi.</b>\n\n"
        "Baribir chiqmoqchimisiz?"
    ),
    "cancel_confirm_ru": (
        "⚠️ <b>Хотите отменить регистрацию?</b>\n\n"
        "❗ Внимание: <b>Оплата не возвращается.</b>\n\n"
        "Вы уверены?"
    ),
    "cancel_yes_uz": "✅ Ro'yxatingiz bekor qilindi. O'rin bo'shatildi.",
    "cancel_yes_ru": "✅ Ваша регистрация отменена. Место освобождено.",
    "cancel_no_uz": "👍 Bekor qilinmadi. Siz hali ham ro'yxatdasiz.",
    "cancel_no_ru": "👍 Отмена не выполнена. Вы всё ещё зарегистрированы.",
    "cancel_not_registered_uz": "ℹ️ Siz ro'yxatdan o'tmagansiz.",
    "cancel_not_registered_ru": "ℹ️ Вы не зарегистрированы.",
    # Reminders
    "reminder_uz": "⏰ <b>Eslatma!</b> O'yiningiz <b>1 soatdan so'ng</b> boshlanadi!\n\n🏟 {stad}\n🎽 {team}\n\nO'yinga tayyor bo'ling! 💪⚽",
    "reminder_ru": "⏰ <b>Напоминание!</b> Ваша игра начнётся <b>через 1 час!</b>\n\n🏟 {stad}\n🎽 {team}\n\nГотовьтесь к игре! 💪⚽",
    # Broadcast
    "broadcast_ask_uz": "📢 Barcha o'yinchilarga yuboriladigan xabarni kiriting:",
    "broadcast_ask_ru": "📢 Введите сообщение для всех игроков:",
    "broadcast_done_uz": "✅ Xabar {count} ta o'yinchiga yuborildi.",
    "broadcast_done_ru": "✅ Сообщение отправлено {count} игрокам.",
    "broadcast_empty_uz": "⚠️ Xabar bo'sh bo'lishi mumkin emas.",
    "broadcast_empty_ru": "⚠️ Сообщение не может быть пустым.",
    # Admin removal
    "removed_by_admin_uz": "ℹ️ Siz admin tomonidan ro'yxatdan chiqarildingiz.",
    "removed_by_admin_ru": "ℹ️ Вы были удалены из списка администратором.",
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
    if uid not in players:
        return False
    if not players[uid].get("confirmed"):
        return False
    return player_game_date.get(uid) == today_str()

def remove_player(uid: int):
    """Remove a player from all storage dicts and free their team slot."""
    if uid in players:
        team = players[uid].get("team")
        if team and uid in team_members.get(team, []):
            team_members[team].remove(uid)
        del players[uid]
    player_game_date.pop(uid, None)
    pending_payments.pop(uid, None)

def reset_player_if_new_day(uid: int):
    if uid in players and player_game_date.get(uid, "") != today_str():
        remove_player(uid)
        logger.info(f"Player {uid} reset for new day.")

def save_daily_stats():
    """Save a snapshot of today's registrations into daily_stats."""
    today = today_str()
    daily_stats[today] = {
        "total": total_registered(),
        "revenue": total_registered() * PRICE_UZS,
        "teams": {k: len(v) for k, v in team_members.items()},
        "stadiums": {},
    }
    # Count per stadium
    for uid, p in players.items():
        if p.get("confirmed") and player_game_date.get(uid) == today:
            stad = p.get("stadium", "unknown")
            daily_stats[today]["stadiums"][stad] = daily_stats[today]["stadiums"].get(stad, 0) + 1

def team_status(lang: str) -> str:
    lines = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        bar = "🟩" * count + "⬜" * (TEAM_MAX - count)
        lines.append(f"{team['name_' + lang]}: {bar} {count}/{TEAM_MAX}")
    return "\n".join(lines)

def get_all_registered_uids() -> list:
    today = today_str()
    return [uid for uid, p in players.items() if p.get("confirmed") and player_game_date.get(uid) == today]

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

def cancel_confirm_kb(lang: str) -> InlineKeyboardMarkup:
    yes = "✅ Ha, chiqaman" if lang == "uz" else "✅ Да, отменить"
    no  = "❌ Yo'q, qolaman" if lang == "uz" else "❌ Нет, остаться"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes, callback_data="cancel_yes"),
        InlineKeyboardButton(no,  callback_data="cancel_no"),
    ]])

# ─── Scheduled Jobs ────────────────────────────────────────────────────────────

async def job_midnight_reset(context: ContextTypes.DEFAULT_TYPE):
    """Runs at midnight: save stats then reset all player data."""
    logger.info("Midnight reset triggered.")
    save_daily_stats()

    # Send daily stats to director
    yesterday = today_str()
    stats = daily_stats.get(yesterday, {})
    if stats and DIRECTOR_CHAT_ID:
        team_lines = "\n".join(
            f"  {TEAMS[k]['name_uz']}: {v} o'yinchi"
            for k, v in stats.get("teams", {}).items()
        )
        stad_lines = "\n".join(
            f"  {STADIUMS[k]['name_uz']}: {v} o'yinchi"
            for k, v in stats.get("stadiums", {}).items()
            if k in STADIUMS
        )
        msg = (
            f"📊 <b>Kunlik hisobot — {yesterday}</b>\n\n"
            f"👥 Jami o'yinchilar: {stats['total']}/{MAX_SLOTS}\n"
            f"💰 Jami daromad: {stats['revenue']:,} so'm\n\n"
            f"🎽 <b>Jamoalar:</b>\n{team_lines}\n\n"
            f"🏟 <b>Stadionlar:</b>\n{stad_lines}"
        )
        try:
            await context.bot.send_message(DIRECTOR_CHAT_ID, msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Stats send error: {e}")

    # Clear all data for the new day
    players.clear()
    pending_payments.clear()
    player_game_date.clear()
    for key in team_members:
        team_members[key] = []
    logger.info("All player data reset for new day.")


async def job_send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Runs every hour: send reminder to players whose game starts in exactly 1 hour."""
    now = datetime.now(TIMEZONE)
    current_hour = now.hour
    target_hour = current_hour + 1  # game starts in 1 hour

    today = today_str()
    for uid, p in list(players.items()):
        if not p.get("confirmed"):
            continue
        if player_game_date.get(uid) != today:
            continue

        stad_key = p.get("stadium", "")
        if stad_key not in STADIUMS:
            continue

        game_hour = STADIUMS[stad_key]["hour"]
        if game_hour != target_hour:
            continue

        lang = p.get("lang", "uz")
        stad_name = STADIUMS[stad_key]["name_" + lang]
        team_name = TEAMS[p["team"]]["name_" + lang]

        msg = TEXTS["reminder_" + lang].format(stad=stad_name, team=team_name)
        try:
            await context.bot.send_message(uid, msg, parse_mode="HTML")
            logger.info(f"Reminder sent to {uid}")
        except Exception as e:
            logger.error(f"Reminder error for {uid}: {e}")

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
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    else:
        context.user_data["phone"] = update.message.text.strip()

    lang = get_lang(context)
    await update.message.reply_text(
        t("ask_stadium", context),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await update.message.reply_text("👇", reply_markup=stadium_kb(lang))
    return STADIUM


async def choose_stadium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

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

# ─── Cancellation ─────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(context)
    reset_player_if_new_day(uid)

    if not is_registered_today(uid):
        await update.message.reply_text(TEXTS["cancel_not_registered_" + lang], parse_mode="HTML")
        return ConversationHandler.END

    await update.message.reply_text(
        TEXTS["cancel_confirm_" + lang],
        reply_markup=cancel_confirm_kb(lang),
        parse_mode="HTML"
    )
    return CANCEL_CONFIRM


async def cancel_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    lang = get_lang(context)

    if query.data == "cancel_yes":
        remove_player(uid)
        await query.edit_message_text(TEXTS["cancel_yes_" + lang], parse_mode="HTML")

        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🚪 O'yinchi ro'yxatdan chiqdi / Игрок отменил регистрацию\n"
                    f"🔗 ID: {uid}\n"
                    f"📊 Bo'sh o'rinlar / Свободных мест: {available_slots()}/{MAX_SLOTS}"
                )
            except Exception as e:
                logger.error(f"Cancel notify error: {e}")
    else:
        await query.edit_message_text(TEXTS["cancel_no_" + lang], parse_mode="HTML")

    return ConversationHandler.END

# ─── Admin: Confirm / Reject ───────────────────────────────────────────────────

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

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
        if len(team_members.get(team_key, [])) >= TEAM_MAX:
            await context.bot.send_message(uid, TEXTS["team_full_" + lang], parse_mode="HTML")
            await query.edit_message_caption(f"⚠️ Jamoa to'lgan, tasdiqlab bo'lmadi: {player['name']}")
            return

        team_members[team_key].append(uid)
        players[uid] = {**player, "confirmed": True, "confirmed_at": datetime.now().isoformat()}
        player_game_date[uid] = today_str()

        team_name = TEAMS[team_key]["name_" + lang]
        msg = TEXTS["confirmed_" + lang] + f"\n\n🎽 {team_name}\n🏟 {stad_name}"
        await context.bot.send_message(uid, msg, parse_mode="HTML")
        await query.edit_message_caption(f"✅ Tasdiqlandi: {player['name']}")

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

# ─── Admin: Remove Player ──────────────────────────────────────────────────────

async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /remove <user_id> — remove a player and free their slot."""
    if update.effective_user.id not in ADMIN_IDS:
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Foydalanish: /remove <user_id>\n\nUser ID ni /list dan olishingiz mumkin."
        )
        return

    try:
        target_uid = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri user ID.")
        return

    if target_uid not in players:
        await update.message.reply_text(f"⚠️ ID {target_uid} ro'yxatda topilmadi.")
        return

    player = players[target_uid]
    player_name = player.get("name", "—")
    player_lang = player.get("lang", "uz")

    remove_player(target_uid)

    # Notify the removed player
    try:
        await context.bot.send_message(
            target_uid,
            TEXTS["removed_by_admin_" + player_lang],
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Remove notify error: {e}")

    await update.message.reply_text(
        f"✅ {player_name} (ID: {target_uid}) ro'yxatdan chiqarildi.\n"
        f"📊 Bo'sh o'rinlar: {available_slots()}/{MAX_SLOTS}"
    )

# ─── Admin: Broadcast ─────────────────────────────────────────────────────────

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("📢 Barcha o'yinchilarga yuboriladigan xabarni kiriting:\n\n(Bekor qilish uchun /cancel_broadcast)")
    return BROADCAST_MSG


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("⚠️ Xabar bo'sh bo'lishi mumkin emas.")
        return BROADCAST_MSG

    uids = get_all_registered_uids()
    sent = 0
    for uid in uids:
        try:
            await context.bot.send_message(uid, f"📢 <b>Muhim xabar:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception as e:
            logger.error(f"Broadcast error for {uid}: {e}")

    await update.message.reply_text(f"✅ Xabar {sent} ta o'yinchiga yuborildi.")
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast bekor qilindi.")
    return ConversationHandler.END

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
                    lines.append(f"  {i}. {p['name']}  |  {p['phone']}  |  {stad_name}  |  ID: <code>{uid}</code>")
        else:
            lines.append("  — (bo'sh)")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: show today's live stats."""
    if update.effective_user.id not in ADMIN_IDS:
        return

    today = today_str()
    total = total_registered()
    revenue = total * PRICE_UZS

    team_lines = "\n".join(
        f"  {TEAMS[k]['name_uz']}: {len(v)}/{TEAM_MAX}"
        for k, v in team_members.items()
    )

    stad_counts = {}
    for uid, p in players.items():
        if p.get("confirmed") and player_game_date.get(uid) == today:
            s = p.get("stadium", "unknown")
            stad_counts[s] = stad_counts.get(s, 0) + 1

    stad_lines = "\n".join(
        f"  {STADIUMS[k]['name_uz']}: {v} o'yinchi"
        for k, v in stad_counts.items()
        if k in STADIUMS
    ) or "  —"

    msg = (
        f"📊 <b>Bugungi statistika — {today}</b>\n\n"
        f"👥 Jami: {total}/{MAX_SLOTS}\n"
        f"💰 Daromad: {revenue:,} so'm\n\n"
        f"🎽 <b>Jamoalar:</b>\n{team_lines}\n\n"
        f"🏟 <b>Stadionlar:</b>\n{stad_lines}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(
        "/help yuboring." if lang == "uz" else "Отправьте /help."
    )

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Registration conversation ──
    reg_conv = ConversationHandler(
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
        conversation_timeout=600,
    )

    # ── Cancellation conversation ──
    cancel_conv = ConversationHandler(
        entry_points=[CommandHandler("cancel", cmd_cancel)],
        states={
            CANCEL_CONFIRM: [CallbackQueryHandler(cancel_decision, pattern="^cancel_")],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    # ── Broadcast conversation ──
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", cmd_broadcast)],
        states={
            BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send),
                CommandHandler("cancel_broadcast", broadcast_cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel_broadcast", broadcast_cancel)],
    )

    app.add_handler(reg_conv)
    app.add_handler(cancel_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(confirm|reject)_"))
    app.add_handler(CommandHandler("slots",     cmd_slots))
    app.add_handler(CommandHandler("mystatus",  cmd_mystatus))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("list",      cmd_list))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("remove",    cmd_remove))
    app.add_handler(MessageHandler(filters.ALL, fallback))

    # ── Scheduled jobs ──
    job_queue = app.job_queue

    # Midnight reset (00:00 Tashkent time daily)
    job_queue.run_daily(
        job_midnight_reset,
        time=time(hour=0, minute=0, tzinfo=TIMEZONE),
    )

    # Hourly reminders
    job_queue.run_repeating(
        job_send_reminders,
        interval=3600,
        first=10,
    )

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
