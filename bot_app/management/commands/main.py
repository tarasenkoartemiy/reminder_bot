from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string

from bot_app.timezone import getting_coordinates, is_time_format
from bot_app.models import User, Reminder
from reminder_bot.settings import TOKEN
from bot_app.response import opener

from zoneinfo import ZoneInfo
from datetime import datetime

from telebot_calendar import Calendar, ENGLISH_LANGUAGE, RUSSIAN_LANGUAGE
from telebot.apihelper import ApiTelegramException
from telebot import types
import telebot


class Command(BaseCommand):
    help = "the main module of the telegram bot"

    def handle(self, *args, **options):
        pass


now = datetime.now()
bot = telebot.TeleBot(TOKEN)
en_calendar = Calendar(language=ENGLISH_LANGUAGE)
ru_calendar = Calendar(language=RUSSIAN_LANGUAGE)
status = {1: "select_language", 2: "enter_city", 3: "enter_text", 4: "select_date", 5: "enter_time"}
calendar_actions = ("IGNORE", "PREVIOUS-MONTH", "NEXT-MONTH", "MONTHS", "MONTH", "CANCEL")


def reply_buttons(*args):
    buttons = [types.KeyboardButton(i) for i in args]

    def reply_keyboard(**kwargs):
        return types.ReplyKeyboardMarkup(**kwargs).add(*buttons)

    return reply_keyboard


def inline_callback_buttons(*args):
    buttons = [types.InlineKeyboardButton(i, callback_data=j) for i, j in args]

    def inline_callback_keyboard(**kwargs):
        return types.InlineKeyboardMarkup(**kwargs).add(*buttons)

    return inline_callback_keyboard


@bot.message_handler(commands=["start"])
def start(message):
    try:
        user = User.objects.get(id=message.chat.id)
        if user.time_zone:
            user.status = status[3]
            user.save()
            keyboard = reply_buttons(*opener("home_page", language=user.language).values())(resize_keyboard=True,
                                                                                            row_width=2)
            msg = opener("start", "home_page", language=user.language)
        else:
            keyboard = None
            if user.language:
                msg = opener("start", "not_authorized", language=user.language)
            else:
                msg = opener("start", "not_authorized", language="EN")
        bot.send_message(message.chat.id, msg, reply_markup=keyboard)
    except ObjectDoesNotExist:
        User.objects.create(id=message.chat.id,
                            username=message.from_user.username,
                            first_name=message.from_user.first_name,
                            last_name=message.from_user.last_name,
                            status=status[1],
                            )
        bot.send_message(message.chat.id, opener("start", "start_of_use", language="EN"),
                         reply_markup=inline_callback_buttons(("English", "EN"), ("Русский", "RU"))())


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user = User.objects.get(id=call.message.chat.id)
    if call.data in ("EN", "RU"):
        if user.language == call.data:
            keyboard = None
            msg = opener("select_language", "same_choice", language=call.data)
        else:
            if user.time_zone:
                keyboard = reply_buttons(*opener("home_page", language=call.data).values())(resize_keyboard=True,
                                                                                            row_width=2)
                msg = opener("select_language", "another_choice", language=call.data)
            elif user.language:
                keyboard = None
                msg = opener("select_language", "another_choice", language=call.data)
            else:
                keyboard = None
                msg = opener("select_language", "first_choice", language=call.data)
                user.status = status[2]
            user.language = call.data
            user.save()
            try:
                bot.edit_message_text(text=opener("start", "start_of_use", language=user.language),
                                      chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      reply_markup=inline_callback_buttons(("English", "EN"), ("Русский", "RU"))())
            except ApiTelegramException:
                pass
        bot.send_message(call.message.chat.id, msg, reply_markup=keyboard)
    elif "DAY" in call.data and user.status == status[4]:
        list_date = call.data.split(":")
        str_date = "-".join(list_date[2:])
        reminder = Reminder.objects.filter(user_id=call.message.chat.id).last()
        reminder.date_time = str_date
        user.status = status[5]
        reminder.save()
        user.save()
        bot.send_message(call.message.chat.id, opener("select_date", "valid_date", language=user.language))
    elif call.data.split(":")[1] in calendar_actions:
        name, action, year, month, day = call.data.split(":")
        calendar = en_calendar if user.language == "EN" else ru_calendar
        calendar.calendar_query_handler(bot=bot, call=call, name=name, action=action, year=year, month=month, day=day)


@bot.message_handler(content_types=['text'])
def reply_answer(message):
    user = User.objects.get(id=message.chat.id)
    if user.status == status[1]:
        bot.send_message(message.chat.id, opener("start", "start_of_use", language="EN"))
    elif user.status == status[2]:
        coordinates = getting_coordinates(message.text)
        timezone = coordinates() if coordinates else coordinates
        # timezone can be True only if coordinates = True
        # In other words, the two apis worked well
        if timezone:
            user.time_zone = timezone
            user.status = status[3]
            user.save()
            keyboard = reply_buttons(*opener("home_page", language=user.language).values())(resize_keyboard=True,
                                                                                            row_width=2)
            msg = opener("enter_city", "success_response", language=user.language)
        # timezone = None when coordinates = True. In other words, the second api does not work
        # OR coordinates = None. In other words, the first api does not work
        elif timezone is None:
            keyboard = None
            msg = opener("enter_city", "bad_response", language=user.language)
        else:
            msg = opener("enter_city", "bad_city", language=user.language)
            keyboard = None
        bot.send_message(message.chat.id, msg, reply_markup=keyboard)
    elif user.status == status[3]:
        Reminder.objects.create(id=message.message_id, user_id=message.chat.id, text=message.text)
        user.status = status[4]
        user.save()
        calendar = en_calendar if user.language == "EN" else ru_calendar
        bot.send_message(message.chat.id, opener("enter_text", language=user.language),
                         reply_markup=calendar.create_calendar(month=now.month,
                                                               year=now.year))
    elif user.status == status[4]:
        bot.send_message(message.chat.id, opener("enter_text", language=user.language))
    elif user.status == status[5]:
        if is_time_format(message.text):
            hour, minute = map(int, message.text.split(":"))
            reminder = Reminder.objects.filter(user_id=message.chat.id).last()
            reminder.date_time = reminder.date_time.replace(tzinfo=ZoneInfo(user.time_zone), hour=hour, minute=minute)
            reminder.is_active = True
            user.reminder_count = + 1
            user.status = status[3]
            reminder.save()
            user.save()
            msg = opener("enter_time", "valid_time", language=user.language)
        else:
            msg = opener("enter_time", "bad_time", language=user.language)
        bot.send_message(message.chat.id, msg)


bot.infinity_polling()
