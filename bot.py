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
from datetime import datetime

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DIRECTOR_CHAT_ID = int(os.environ.get("DIRECTOR_CHAT_ID", "0"))
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "0").split(",") if x.strip()]

MAX_SLOTS = 20
TEAM_MAX = 5
PRICE_UZS = 150000

TEAMS = {
    "blue":   {"name_uz": "🔵 Ko'k jamoa",   "name_ru": "🔵 Синяя команда"},
    "red":    {"name_uz": "🔴 Qizil jamoa",  "name_ru": "🔴 Красная команда"},
    "green":  {"name_uz": "🟢 Yashil jamoa", "name_ru": "🟢 Зелёная команда"},
    "yellow": {"name_uz": "🟡 Sariq jamoa",  "name_ru": "🟡 Жёлтая команда"},
}

LANG, NAME, PHONE, TEAM, SCREENSHOT = range(5)
players = {}
pending_payments = {}
team_members = {"blue": [], "red": [], "green": [], "yellow": []}

T = {
    "welcome": {"uz": "⚽ <b>Futbol ligasiga xush kelibsiz!</b>\n\nTilni tanlang:", "ru": "⚽ <b>Добро пожаловать в футбольную лигу!</b>\n\nВыберите язык:"},
    "ask_name": {"uz": "Ismingizni kiriting:", "ru": "Введите ваше имя:"},
    "ask_phone": {"uz": "Telefon raqamingizni yuboring:", "ru": "Отправьте ваш номер телефона:"},
    "ask_team": {"uz": "Qaysi jamoani tanlaysiz?", "ru": "Выберите команду:"},
    "team_full": {"uz": "❌ Bu jamoa to'lgan. Boshqa jamoani tanlang.", "ru": "❌ Эта команда заполнена. Выберите другую."},
    "no_slots": {"uz": "😔 Barcha o'rinlar band.", "ru": "😔 Все места заняты."},
    "ask_payment": {
        "uz": f"💳 <b>To'lov</b>\n\nSumma: <b>{PRICE_UZS:,} so'm</b>\n\n• Click: 9860 1234 5678 9012\n• Payme: 8600 0987 6543 2109\n\nTo'lovdan so'ng skrinshot yuboring.",
        "ru": f"💳 <b>Оплата</b>\n\nСумма: <b>{PRICE_UZS:,} сум</b>\n\n• Click: 9860 1234 5678 9012\n• Payme: 8600 0987 6543 2109\n\nПосле оплаты отправьте скриншот."
    },
    "payment_received": {"uz": "✅ Skrinshot qabul qilindi. Kuting...", "ru": "✅ Скриншот получен. Ожидайте..."},
    "payment_confirmed": {"uz": "🎉 <b>Tabriklaymiz!</b> {team} ga qo'shildingiz!", "ru": "🎉 <b>Поздравляем!</b> Вы в {team}!"},
    "payment_rejected": {"uz": "❌ To'lov tasdiqlanmadi.", "ru": "❌ Платёж не подтверждён."},
    "already_registered": {"uz": "ℹ️ Siz allaqachon ro'yxatdan o'tgansiz.", "ru": "ℹ️ Вы уже зарегистрированы."},
    "help": {"uz": "ℹ️ <b>Yordam</b>\n\n/start — Ro'yxatdan o'tish\n/slots — Bo'sh o'rinlar\n/mystatus — Holatim", "ru": "ℹ️ <b>Помощь</b>\n\n/start — Регистрация\n/slots — Свободные места\n/mystatus — Мой статус"}
}

def get_lang(context): return context.user_data.get("lang", "uz")
def total_registered(): return sum(len(v) for v in team_members.values())
def available_slots(): return MAX_SLOTS - total_registered()

def team_status(lang):
    lines = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        lines.append(f"{team[f'name_{lang}']}: {'🟩'*count}{'⬜'*(TEAM_MAX-count)} {count}/{TEAM_MAX}")
    return "\n".join(lines)

def lang_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"), InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]])

def team_kb(lang):
    buttons = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        name = team[f"name_{lang}"]
        if count < TEAM_MAX:
            buttons.append([InlineKeyboardButton(f"{name} ({count}/{TEAM_MAX})", callback_data=f"team_{key}")])
        else:
            buttons.append([InlineKeyboardButton(f"{name} ✗ FULL", callback_data="team_full")])
    return InlineKeyboardMarkup(buttons)

def phone_kb(lang):
    label = "📱 Raqamni yuborish" if lang == "uz" else "📱 Отправить номер"
    return ReplyKeyboardMarkup([[KeyboardButton(label, request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in players and players[uid].get("confirmed"):
        await update.message.reply_text(T["already_registered"][get_lang(context)], parse_mode="HTML")
        return ConversationHandler.END
    if available_slots() <= 0:
        await update.message.reply_text(T["no_slots"]["uz"], parse_mode="HTML")
        return ConversationHandler.END
    await update.message.reply_text(T["welcome"]["uz"] + "\n\n" + T["welcome"]["ru"], reply_markup=lang_kb(), parse_mode="HTML")
    return LANG

async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["lang"] = query.data.split("_")[1]
    await query.edit_message_text(T["ask_name"][get_lang(context)], parse_mode="HTML")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text(T["ask_name"][get_lang(context)])
        return NAME
    context.user_data["name"] = name
    lang = get_lang(context)
    await update.message.reply_text(T["ask_phone"][lang], reply_markup=phone_kb(lang))
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    lang = get_lang(context)
    await update.message.reply_text(T["ask_team"][lang], reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(team_status(lang), reply_markup=team_kb(lang), parse_mode="HTML")
    return TEAM

async def choose_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "team_full":
        await query.message.reply_text(T["team_full"][get_lang(context)])
        return TEAM
    team_key = query.data.split("_")[1]
    if len(team_members[team_key]) >= TEAM_MAX:
        await query.message.reply_text(T["team_full"][get_lang(context)])
        return TEAM
    context.user_data["team"] = team_key
    await query.edit_message_text(T["ask_payment"][get_lang(context)], parse_mode="HTML")
    return SCREENSHOT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    if not (update.message.photo or update.message.document):
        lang = get_lang(context)
        await update.message.reply_text("📸 Skrinshot yuboring." if lang == "uz" else "📸 Отправьте скриншот.")
        return SCREENSHOT
    pending_payments[uid] = {"name": context.user_data.get("name"), "phone": context.user_data.get("phone"), "team": context.user_data.get("team"), "lang": get_lang(context), "user_id": uid, "username": user.username or "—"}
    await update.message.reply_text(T["payment_received"][get_lang(context)], parse_mode="HTML")
    p = pending_payments[uid]
    caption = f"💰 <b>Yangi to'lov</b>\n\n👤 {p['name']}\n📱 {p['phone']}\n🎽 {TEAMS[p['team']]['name_uz']}\n🔗 @{p['username']}"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{uid}"), InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{uid}")]])
    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption=caption, parse_mode="HTML", reply_markup=buttons)
            else:
                await context.bot.send_document(admin_id, update.message.document.file_id, caption=caption, parse_mode="HTML", reply_markup=buttons)
        except Exception as e:
            logger.error(f"Admin notify error: {e}")
    return ConversationHandler.END

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        return
    action, uid = query.data.split("_", 1)
    uid = int(uid)
    if uid not in pending_payments:
        await query.edit_message_caption("⚠️ Allaqachon ko'rib chiqilgan.")
        return
    player = pending_payments.pop(uid)
    lang = player["lang"]
    if action == "confirm":
        team_members[player["team"]].append(uid)
        players[uid] = {**player, "confirmed": True}
        team_name = TEAMS[player["team"]][f"name_{lang}"]
        await context.bot.send_message(uid, T["payment_confirmed"][lang].format(team=team_name), parse_mode="HTML")
        await query.edit_message_caption(f"✅ Tasdiqlandi — {player['name']}")
        if DIRECTOR_CHAT_ID:
            msg = f"🆕 <b>Yangi o'yinchi!</b>\n\n👤 {player['name']}\n📱 {player['phone']}\n🎽 {TEAMS[player['team']]['name_uz']}\n📊 Jami: {total_registered()}/{MAX_SLOTS}\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            try:
                await context.bot.send_message(DIRECTOR_CHAT_ID, msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Director notify error: {e}")
    else:
        await context.bot.send_message(uid, T["payment_rejected"][lang], parse_mode="HTML")
        await query.edit_message_caption(f"❌ Rad etildi — {player['name']}")

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    header = f"📊 <b>Bo'sh o'rinlar: {available_slots()} ta</b>" if lang == "uz" else f"📊 <b>Свободных мест: {available_slots()}</b>"
    await update.message.reply_text(f"{header}\n\n{team_status(lang)}", parse_mode="HTML")

async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(context)
    if uid in players and players[uid].get("confirmed"):
        p = players[uid]
        team_name = TEAMS[p["team"]][f"name_{lang}"]
        msg = f"✅ <b>{'Ro'yxatdan o'tgansiz' if lang == 'uz' else 'Вы зарегистрированы'}</b>\n\n👤 {p['name']}\n📱 {p['phone']}\n🎽 {team_name}"
    elif uid in pending_payments:
        msg = "⏳ To'lovingiz ko'rib chiqilmoqda..." if lang == "uz" else "⏳ Платёж на рассмотрении..."
    else:
        msg = "❌ Ro'yxatdan o'tmagansiz. /start yuboring." if lang == "uz" else "❌ Не зарегистрированы. Отправьте /start."
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(T["help"][get_lang(context)], parse_mode="HTML")

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not players:
        await update.message.reply_text("Hozircha hech kim ro'yxatdan o'tmagan.")
        return
    lines = ["📋 <b>Ro'yxatdan o'tganlar:</b>\n"]
    for i, (uid, p) in enumerate(players.items(), 1):
        lines.append(f"{i}. {p['name']} | {p['phone']} | {TEAMS[p['team']]['name_uz']}")
    lines.append(f"\n<b>Jami:</b> {total_registered()}/{MAX_SLOTS}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text("❓ /help buyrug'ini yuboring." if lang == "uz" else "❓ Отправьте /help.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG:       [CallbackQueryHandler(set_lang, pattern="^lang_")],
            NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE:      [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_phone)],
            TEAM:       [CallbackQueryHandler(choose_team, pattern="^team_")],
            SCREENSHOT: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_screenshot)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(confirm|reject)_"))
    app.add_handler(CommandHandler("slots", cmd_slots))
    app.add_handler(CommandHandler("mystatus", cmd_mystatus))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(MessageHandler(filters.ALL, fallback))
    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
