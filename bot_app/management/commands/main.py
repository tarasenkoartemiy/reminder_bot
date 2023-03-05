from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone

from bot_app.timezone import getting_coordinates, is_time_format
from bot_app.models import User, Reminder
from reminder_bot.settings import TOKEN
from bot_app.response import opener, context_gen

from datetime import datetime
from zoneinfo import ZoneInfo

from telebot_calendar import Calendar, ENGLISH_LANGUAGE, RUSSIAN_LANGUAGE
from telebot.apihelper import ApiTelegramException
from telebot import types
import telebot


class Command(BaseCommand):
    help = "the main module of the telegram bot"

    def handle(self, *args, **options):
        pass


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
    now = timezone.now()
    cd = call.data.split(":")
    user_id = call.message.chat.id
    user = User.objects.get(id=call.message.chat.id)
    tz_obj = ZoneInfo(key=user.time_zone) if user.time_zone else None
    if len(cd) == 1:
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
    elif len(cd) == 2:
        if cd[0] == "R":
            pass
        else:
            pass
    elif len(cd) == 3:
        if cd[0] == "R":
            pass
        else:
            pass
    elif len(cd) == 5:
        if "DAY" in cd and user.status == status[4]:
            year, month, day = map(int, cd[2:])
            date = datetime(year, month, day, 0, 0, 0, tzinfo=tz_obj)
            if date.date() >= timezone.localdate(now, timezone=tz_obj):
                reminder = Reminder.objects.filter(user_id=call.message.chat.id).last()
                reminder.date_time = date
                reminder.save()
                user.status = status[5]
                user.save()
                msg = opener("select_date", "valid_date", language=user.language)
            else:
                msg = opener("select_date", "bad_date", language=user.language)
            bot.send_message(call.message.chat.id, msg)
        else:
            name, action, year, month, day = cd
            calendar = en_calendar if user.language == "EN" else ru_calendar
            calendar.calendar_query_handler(bot=bot, call=call, name=name, action=action, year=year, month=month,
                                            day=day)


@bot.message_handler(content_types=['text'])
def reply_answer(message):
    now = timezone.now()
    user = User.objects.get(id=message.chat.id)
    tz_obj = ZoneInfo(key=user.time_zone) if user.time_zone else None
    if user.status == status[1]:
        bot.send_message(message.chat.id, opener("start", "start_of_use", language="EN"))
    elif user.status == status[2]:
        coordinates = getting_coordinates(message.text)
        time_zone = coordinates() if coordinates else coordinates
        # time_zone can be True only if coordinates = True
        # In other words, the two apis worked well
        if time_zone:
            user.time_zone = time_zone
            user.status = status[3]
            user.save()
            keyboard = reply_buttons(*opener("home_page", language=user.language).values())(resize_keyboard=True,
                                                                                            row_width=2)
            msg = opener("enter_city", "success_response", language=user.language)
        # time_zone = None when coordinates = True. In other words, the second api does not work
        # OR coordinates = None. In other words, the first api does not work
        elif time_zone is None:
            keyboard = None
            msg = opener("enter_city", "bad_response", language=user.language)
        else:
            msg = opener("enter_city", "bad_city", language=user.language)
            keyboard = None
        bot.send_message(message.chat.id, msg, reply_markup=keyboard)
    elif message.text == opener("home_page", "btn1", language=user.language):
        if reminders := Reminder.objects.filter(user_id=message.chat.id, is_active__isnull=False):
            timezone.activate(tz_obj)
            local_values = {"reminders": reminders}
            context = context_gen("my_reminders", language=user.language, other=local_values)
            bot.send_message(message.chat.id, render_to_string("bot_app/My_reminders.html", context=context),
                             parse_mode="HTML")
            timezone.deactivate()
        else:
            bot.send_message(message.chat.id, opener("my_reminders", "empty_list", language=user.language))
    elif message.text == opener("home_page", "btn2", language=user.language):
        if notes := Reminder.objects.filter(user_id=message.chat.id, is_active__isnull=True):
            local_values = {"notes": notes}
            context = context_gen("my_notes", language=user.language, other=local_values)
            bot.send_message(message.chat.id, render_to_string("bot_app/My_notes.html", context=context),
                             parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, opener("my_notes", "empty_list", language=user.language))
    elif message.text == opener("home_page", "btn3", language=user.language):
        local_values = {"users": User.objects.all().order_by("-reminder_count")}
        context = context_gen("rating", language=user.language, other=local_values)
        bot.send_message(message.chat.id, render_to_string("bot_app/Rating.html", context=context),
                         parse_mode="HTML")
    elif message.text == opener("home_page", "btn4", language=user.language):
        timezone.activate(tz_obj)
        local_values = {"time_zone_value": user.time_zone, "language_value": user.language, "local_time_value": now}
        context = context_gen("settings", language=user.language, other=local_values)
        bot.send_message(message.chat.id, render_to_string("bot_app/Settings.html", context=context),
                         parse_mode="HTML")
        timezone.deactivate()
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
            hour, minute = list(map(int, message.text.split(":")))
            reminder = Reminder.objects.filter(user_id=message.chat.id).last()
            date = timezone.localtime(reminder.date_time, timezone=tz_obj).replace(hour=hour, minute=minute)
            if date >= timezone.localtime(now, timezone=tz_obj):
                reminder.date_time = date
                reminder.is_active = True
                reminder.save()
                user.reminder_count += 1
                user.status = status[3]
                user.save()
                msg = opener("enter_time", "valid_time", language=user.language)
            else:
                msg = opener("enter_time", "bad_time", language=user.language)
        else:
            msg = opener("enter_time", "invalid_time", language=user.language)
        bot.send_message(message.chat.id, msg)


bot.infinity_polling()
