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

BOT_TOKEN = "8246944384:AAGnr7n4dzx4AEBip8GG5NXzu8HIV7B9-8E"
DIRECTOR_CHAT_ID = 7504925076
ADMIN_IDS = [6663841273]

MAX_SLOTS = 20
TEAM_MAX = 5
PRICE_UZS = 150000

TEAMS = {
    "blue":   {"name_uz": "\U0001f535 Kok jamoa",    "name_ru": "\U0001f535 Синяя команда"},
    "red":    {"name_uz": "\U0001f534 Qizil jamoa",  "name_ru": "\U0001f534 Красная команда"},
    "green":  {"name_uz": "\U0001f7e2 Yashil jamoa", "name_ru": "\U0001f7e2 Зеленная команда"},
    "yellow": {"name_uz": "\U0001f7e1 Sariq jamoa",  "name_ru": "\U0001f7e1 Желная команда"},
}

LANG, NAME, PHONE, TEAM, SCREENSHOT = range(5)
players = {}
pending_payments = {}
team_members = {"blue": [], "red": [], "green": [], "yellow": []}

TEXTS = {
    "welcome_uz": "\u26bd <b>Futbol ligasiga xush kelibsiz!</b>\n\nTilni tanlang:",
    "welcome_ru": "\u26bd <b>Добро пожаловать в футбольную лигу!</b>\n\nВыберите язык:",
    "ask_name_uz": "Ismingizni kiriting:",
    "ask_name_ru": "Введите ваще имя:",
    "ask_phone_uz": "Telefon raqamingizni yuboring:",
    "ask_phone_ru": "Отправите ваш номер телефона:",
    "ask_team_uz": "Qaysi jamoani tanlaysiz?",
    "ask_team_ru": "Выберите команду:",
    "team_full_uz": "\u274c Bu jamoa tolgan. Boshqa jamoani tanlang.",
    "team_full_ru": "\u274c Это команда заполнена. Выберите другую.",
    "no_slots_uz": "\U0001f614 Barcha orinlar band.",
    "no_slots_ru": "\U0001f614 Все места заняты.",
    "payment_uz": "\U0001f4b3 <b>Tolov</b>\n\nSumma: <b>45,000 som</b>\n\n- Click: 8600 4904 1734 5204\n- Payme: 8600 4904 1734 5204\n\nTolovdan song skrinshot yuboring.",
    "payment_ru": "\U0001f4b3 <b>Oplata</b>\n\nSumma: <b>45,000 sum</b>\n\n- Click: 8600 4904 1734 5204\n- Payme: 8600 4904 1734 5204\n\nPosle oplaty otpravte skrinshot.",
    "received_uz": "\u2705 Skrinshot qabul qilindi. Kuting...",
    "received_ru": "\u2705 Skrinshot polucen. Ojidayte...",
    "confirmed_uz": "\U0001f389 <b>Tabriklaymiz!</b> Siz jamoaga qoshildingiz!",
    "confirmed_ru": "\U0001f389 <b>Pozdravlyaem!</b> Vy dobavleny v komandu!",
    "rejected_uz": "\u274c Tolov tasdiqlanmadi. Qayta urining.",
    "rejected_ru": "\u274c Platezh ne podtverzhden. Povtorite.",
    "already_uz": "\u2139\ufe0f Siz allaqachon royxatdan otgansiz.",
    "already_ru": "\u2139\ufe0f Vy uzhe zaregistrirovany.",
    "help_uz": "\u2139\ufe0f <b>Yordam</b>\n\n/start - Royxatdan otish\n/slots - Bosh orinlar\n/mystatus - Holatim",
    "help_ru": "\u2139\ufe0f <b>Pomosh</b>\n\n/start - Registraciya\n/slots - Svobodnye mesta\n/mystatus - Moy status",
    "status_yes_uz": "\u2705 <b>Royxatdan otgansiz</b>",
    "status_yes_ru": "\u2705 <b>Vy zaregistrirovany</b>",
    "status_pending_uz": "\u23f3 Tolovingiz korib chiqilmoqda...",
    "status_pending_ru": "\u23f3 Platezh na rassmotrenii...",
    "status_no_uz": "\u274c Royxatdan otmagansiz. /start yuboring.",
    "status_no_ru": "\u274c Ne zaregistrirovany. Otpravte /start.",
}

def get_lang(context): return context.user_data.get("lang", "uz")
def t(key, context): return TEXTS[key + "_" + get_lang(context)]
def total_registered(): return sum(len(v) for v in team_members.values())
def available_slots(): return MAX_SLOTS - total_registered()

def team_status(lang):
    lines = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        lines.append(team["name_" + lang] + ": " + "\U0001f7e9"*count + "\u2b1c"*(TEAM_MAX-count) + " " + str(count) + "/" + str(TEAM_MAX))
    return "\n".join(lines)

def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Uzbekcha", callback_data="lang_uz"),
        InlineKeyboardButton("Russkiy", callback_data="lang_ru")
    ]])

def team_kb(lang):
    buttons = []
    for key, team in TEAMS.items():
        count = len(team_members[key])
        name = team["name_" + lang]
        if count < TEAM_MAX:
            buttons.append([InlineKeyboardButton(name + " (" + str(count) + "/" + str(TEAM_MAX) + ")", callback_data="team_" + key)])
        else:
            buttons.append([InlineKeyboardButton(name + " FULL", callback_data="team_full")])
    return InlineKeyboardMarkup(buttons)

def phone_kb(lang):
    label = "Raqamni yuborish" if lang == "uz" else "Otpravit nomer"
    return ReplyKeyboardMarkup([[KeyboardButton(label, request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in players and players[uid].get("confirmed"):
        await update.message.reply_text(t("already", context), parse_mode="HTML")
        return ConversationHandler.END
    if available_slots() <= 0:
        await update.message.reply_text(TEXTS["no_slots_uz"], parse_mode="HTML")
        return ConversationHandler.END
    await update.message.reply_text(TEXTS["welcome_uz"] + "\n\n" + TEXTS["welcome_ru"], reply_markup=lang_kb(), parse_mode="HTML")
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
    await update.message.reply_text(t("ask_phone", context), reply_markup=phone_kb(lang))
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    lang = get_lang(context)
    await update.message.reply_text(t("ask_team", context), reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(team_status(lang), reply_markup=team_kb(lang))
    return TEAM

async def choose_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "team_full":
        await query.message.reply_text(t("team_full", context))
        return TEAM
    team_key = query.data.split("_")[1]
    if len(team_members[team_key]) >= TEAM_MAX:
        await query.message.reply_text(t("team_full", context))
        return TEAM
    context.user_data["team"] = team_key
    await query.edit_message_text(t("payment", context), parse_mode="HTML")
    return SCREENSHOT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    if not (update.message.photo or update.message.document):
        await update.message.reply_text("Skrinshot yuboring / Otpravte skrinshot.")
        return SCREENSHOT
    pending_payments[uid] = {
        "name": context.user_data.get("name"),
        "phone": context.user_data.get("phone"),
        "team": context.user_data.get("team"),
        "lang": get_lang(context),
        "user_id": uid,
        "username": user.username or "-"
    }
    await update.message.reply_text(t("received", context), parse_mode="HTML")
    p = pending_payments[uid]
    caption = "\U0001f4b0 Yangi tolov\n\nIsm: " + p["name"] + "\nTel: " + p["phone"] + "\nJamoa: " + TEAMS[p["team"]]["name_uz"] + "\n@" + p["username"]
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("Tasdiqlash", callback_data="confirm_" + str(uid)),
        InlineKeyboardButton("Rad etish", callback_data="reject_" + str(uid))
    ]])
    for admin_id in ADMIN_IDS:
        try:
            if update.message.photo:
                await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption=caption, reply_markup=buttons)
            else:
                await context.bot.send_document(admin_id, update.message.document.file_id, caption=caption, reply_markup=buttons)
        except Exception as e:
            logger.error("Admin notify error: " + str(e))
    return ConversationHandler.END

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        return
    action, uid = query.data.split("_", 1)
    uid = int(uid)
    if uid not in pending_payments:
        await query.edit_message_caption("Allaqachon korib chiqilgan.")
        return
    player = pending_payments.pop(uid)
    lang = player["lang"]
    if action == "confirm":
        team_members[player["team"]].append(uid)
        players[uid] = {**player, "confirmed": True}
        team_name = TEAMS[player["team"]]["name_" + lang]
        await context.bot.send_message(uid, TEXTS["confirmed_" + lang] + "\nJamoa: " + team_name, parse_mode="HTML")
        await query.edit_message_caption("Tasdiqlandi: " + player["name"])
        if DIRECTOR_CHAT_ID:
            msg = "Yangi oyinchi!\n\nIsm: " + player["name"] + "\nTel: " + player["phone"] + "\nJamoa: " + TEAMS[player["team"]]["name_uz"] + "\nJami: " + str(total_registered()) + "/" + str(MAX_SLOTS) + "\nVaqt: " + datetime.now().strftime("%d.%m.%Y %H:%M")
            try:
                await context.bot.send_message(DIRECTOR_CHAT_ID, msg)
            except Exception as e:
                logger.error("Director notify error: " + str(e))
    else:
        await context.bot.send_message(uid, TEXTS["rejected_" + lang], parse_mode="HTML")
        await query.edit_message_caption("Rad etildi: " + player["name"])

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    header = "Bosh orinlar: " + str(available_slots()) if lang == "uz" else "Svobodnykh mest: " + str(available_slots())
    await update.message.reply_text(header + "\n\n" + team_status(lang))

async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(context)
    if uid in players and players[uid].get("confirmed"):
        p = players[uid]
        team_name = TEAMS[p["team"]]["name_" + lang]
        msg = TEXTS["status_yes_" + lang] + "\n\nIsm: " + p["name"] + "\nTel: " + p["phone"] + "\nJamoa: " + team_name
    elif uid in pending_payments:
        msg = TEXTS["status_pending_" + lang]
    else:
        msg = TEXTS["status_no_" + lang]
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t("help", context), parse_mode="HTML")

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not players:
        await update.message.reply_text("Hozircha hech kim royxatdan otmagan.")
        return
    lines = ["Royxatdan otganlar:\n"]
    for i, (uid, p) in enumerate(players.items(), 1):
        lines.append(str(i) + ". " + p["name"] + " | " + p["phone"] + " | " + TEAMS[p["team"]]["name_uz"])
    lines.append("\nJami: " + str(total_registered()) + "/" + str(MAX_SLOTS))
    await update.message.reply_text("\n".join(lines))

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text("/help yuboring." if lang == "uz" else "Otpravte /help.")

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
