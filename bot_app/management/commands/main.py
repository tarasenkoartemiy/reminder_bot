from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone

from bot_app.timezone import getting_coordinates, is_time_format
from bot_app.models import User, Reminder, Note
from reminder_bot.settings import TOKEN
from bot_app.response import opener, context_gen

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pytz import utc

from telebot_calendar import Calendar, ENGLISH_LANGUAGE, RUSSIAN_LANGUAGE
from telebot.apihelper import ApiTelegramException
from telebot import types
import telebot

from apscheduler.schedulers.background import BackgroundScheduler


class Command(BaseCommand):
    help = "the main module of the telegram bot"

    def handle(self, *args, **options):
        pass


bot = telebot.TeleBot(TOKEN)
scheduler = BackgroundScheduler()
scheduler.configure(timezone=utc)
en_calendar = Calendar(language=ENGLISH_LANGUAGE)
ru_calendar = Calendar(language=RUSSIAN_LANGUAGE)
status = {"select_language": 1,
          "enter_city": 2,
          "enter_text": 3,
          "select_date": 4,
          "enter_time": 5,
          "change_reminder_text": 6,
          "change_reminder_date": 7,
          "change_reminder_time": 8,
          "change_note_text": 9,
          }
calendar_actions = ("IGNORE", "PREVIOUS-MONTH", "NEXT-MONTH", "MONTHS", "MONTH", "CANCEL")


def schedule_reminder(reminder_date, user_id, message, reminder, job_id):
    scheduler.add_job(remind, trigger='date', run_date=reminder_date, args=(user_id, message, reminder), id=job_id)


def reschedule_reminders():
    for reminder in Reminder.objects.filter(is_active=True):
        args = (reminder.user_id, reminder.reminder_text, reminder)
        scheduler.add_job(remind, trigger='date', run_date=reminder.date_time, args=args, id=str(reminder.reminder_id))


def remind(user_id, message, reminder):
    bot.send_message(user_id, message)
    reminder.is_active = None
    reminder.save()
    user = User.objects.get(id=reminder.user_id)
    user.score += 10
    user.save()
    delete_date = reminder.date_time + timedelta(days=14)
    scheduler.add_job(delete_reminder, trigger='date', run_date=delete_date, args=(reminder,))


def delete_reminder(reminder):
    reminder.delete()


def check_inactive_reminders():
    for reminder in Reminder.objects.filter(is_active=False):
        if reminder.date_time < timezone.now():
            user = User.objects.get(id=reminder.user_id)
            note = Note.objects.create(note_id=reminder.reminder_id,
                                       user_id=reminder.user_id,
                                       note_text=reminder.reminder_text)
            delete_reminder(reminder)
            local_values = {"note": note}
            context = context_gen("inactive_reminder", language=user.language, other=local_values)
            message = render_to_string("bot_app/Inactive_reminder.html", context=context)
            bot.send_message(note.user_id, message, parse_mode="HTML")


def reply_buttons(section, language):
    buttons = [types.KeyboardButton(value) for value in opener(section, language=language).values()]

    def reply_keyboard(**kwargs):
        return types.ReplyKeyboardMarkup(**kwargs).add(*buttons)

    return reply_keyboard


def inline_callback_buttons(section, language, prefix, number=None, active=False):
    buttons = []
    if number:
        for key, value in opener(section, language=language).items():
            if key == "DEACTIVATE" and not active:
                continue
            elif key == "ACTIVATE" and active:
                continue
            buttons.append(types.InlineKeyboardButton(value, callback_data=f"{prefix}:{key}:{number}"))
    else:
        for key, value in opener(section, language=language).items():
            buttons.append(types.InlineKeyboardButton(value, callback_data=f"{prefix}:{key}"))

    def inline_callback_keyboard(**kwargs):
        return types.InlineKeyboardMarkup(**kwargs).add(*buttons)

    return inline_callback_keyboard


reschedule_reminders()


@bot.message_handler(commands=["start"])
def start(message):
    try:
        user = User.objects.get(id=message.chat.id)
        if user.time_zone:
            user.status = status["enter_text"]
            user.save()
            keyboard = reply_buttons("home_page", language=user.language)(resize_keyboard=True, row_width=2)
            context = context_gen("enter_city", "success_response", language=user.language)
            del context["header1"]
            msg = render_to_string("bot_app/How_to_create.html", context=context)
            pm = "HTML"
        else:
            keyboard = pm = None
            language = user.language if user.language else "EN"
            msg = opener("start", "not_authorized", language=language)
        bot.send_message(message.chat.id, msg, parse_mode=pm, reply_markup=keyboard)
    except ObjectDoesNotExist:
        User.objects.create(id=message.chat.id,
                            username=message.from_user.username,
                            first_name=message.from_user.first_name,
                            last_name=message.from_user.last_name,
                            status=status["select_language"],
                            )
        bot.send_message(message.chat.id, opener("start", "start_of_use", language="EN"),
                         reply_markup=inline_callback_buttons("language_buttons", language="EN", prefix="LANGUAGE")())


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    now = timezone.now()
    cd = call.data.split(":")
    prefix, action = cd[:2]
    msg_id = call.message.message_id
    user_id = call.message.chat.id
    user = User.objects.get(id=call.message.chat.id)
    tz_obj = ZoneInfo(key=user.time_zone) if user.time_zone else None
    keyboard = None
    if prefix == "LANGUAGE":
        section = "select_language"
        if user.language == action:
            subsection = "same_choice"
        else:
            user.language = action
            user.save()
            if user.time_zone:
                subsection = "another_choice"
                keyboard = reply_buttons("home_page", language=user.language)(resize_keyboard=True, row_width=2)
            else:
                subsection = "first_choice"
                user.status = status["enter_city"]
                user.save()
            try:
                buttons = inline_callback_buttons("language_buttons", language=user.language, prefix="LANGUAGE")
                bot.edit_message_text(text=opener("start", "start_of_use", language=user.language),
                                      chat_id=user_id, message_id=msg_id, reply_markup=buttons())
            except ApiTelegramException:
                pass
        message = opener(section, subsection, language=action)
        bot.send_message(user_id, message, reply_markup=keyboard)
    elif prefix == "REMINDER":
        timezone.activate(tz_obj)
        number = call.data.split(":")[2]
        index = int(number) - 1
        reminders = Reminder.objects.filter(user_id=user_id, is_active__isnull=False)
        reminder = reminders[index]
        pm = "HTML"
        if action in ("NUMBER", "DEACTIVATE", "ACTIVATE", "CHANGE", "CHANGE-BACK"):
            buttons_section = "reminder_change_buttons" if action == "CHANGE" else "reminder_buttons"
            if action in ("DEACTIVATE", "ACTIVATE"):
                if action == "DEACTIVATE":
                    reminder.is_active = False
                    scheduler.remove_job(job_id=str(reminder.reminder_id))
                else:
                    reminder.is_active = True
                    schedule_reminder(reminder_date=reminder.date_time,
                                      user_id=user_id,
                                      message=reminder.reminder_text,
                                      reminder=reminder,
                                      job_id=str(reminder.reminder_id))
                reminder.save()
                reminder = Reminder.objects.filter(user_id=user_id, is_active__isnull=False)[index]
            local_values = {"reminder": reminder,
                            "relevance": opener("relevance", language=user.language)}
            context = context_gen("reminder", language=user.language, other=local_values)
            new_msg = render_to_string("bot_app/Reminder.html", context=context)
            buttons = inline_callback_buttons(buttons_section, language=user.language, prefix=prefix, number=number,
                                              active=reminder.is_active)
            keyboard = buttons(row_width=3)
        elif action in ("DELETE", "BACK"):
            if action == "DELETE":
                reminder.delete()
                reminders = Reminder.objects.filter(user_id=user_id, is_active__isnull=False)
            if not reminders:
                pm = None
                new_msg = opener("my_reminders", "empty_list", language=user.language)
            else:
                local_values = {"reminders": reminders,
                                "relevance": opener("relevance", language=user.language)}
                context = context_gen("my_reminders", language=user.language, other=local_values)
                new_msg = render_to_string("bot_app/My_reminders.html", context=context)
                buttons = (types.InlineKeyboardButton(str(i), callback_data=f"REMINDER:NUMBER:{i}") for i in
                           range(1, len(reminders) + 1))
                keyboard = types.InlineKeyboardMarkup(row_width=3).add(*buttons)
        elif action in ("CHANGE-TEXT", "CHANGE-DATE", "CHANGE-TIME"):
            timezone.deactivate()
            pm = None
            user.change_number = number
            if action == "CHANGE-TEXT":
                user.status = status["change_reminder_text"]
                message = "Пожалуйста, введите новый текст"
            else:
                message = "Скоро. Введите /start, чтобы вернуться"
            user.save()
            new_msg = message
            try:
                bot.delete_message(chat_id=user_id, message_id=msg_id)
            except ApiTelegramException:
                pass
        try:
            bot.edit_message_text(text=new_msg, chat_id=user_id, message_id=msg_id, parse_mode=pm,
                                  reply_markup=keyboard)
        except ApiTelegramException:
            bot.send_message(user_id, message)
        timezone.deactivate()
    elif prefix == "CALENDAR":
        if action == "DAY":
            year, month, day = map(int, cd[2:])
            trigger = False
            if user.status == status["select_date"]:
                note = Note.objects.filter(user_id=call.message.chat.id).last()
                date = datetime(year, month, day, 0, 0, 0, tzinfo=tz_obj)
                if date.date() >= timezone.localdate(now, timezone=tz_obj):
                    note.possible_date = date
                    note.save()
                    user.status = status["enter_time"]
                    trigger = True
            elif user.status == status["change_reminder_date"]:
                reminder = Reminder.objects.filter(user_id=user_id, is_active__isnull=False)[user.change_number - 1]
                date = timezone.localtime(reminder.date_time, timezone=tz_obj).replace(year=year, month=month, day=day)
                if date >= timezone.localtime(now, timezone=tz_obj):
                    reminder.date_time = date
                    reminder.save()
                    user.status = status["change_reminder_time"]
                    trigger = True
            user.save()
            if trigger:
                subsection = "valid_date"
                try:
                    bot.delete_message(chat_id=user_id, message_id=msg_id)
                except ApiTelegramException:
                    pass
            else:
                subsection = "bad_date"
            msg = opener("select_date", subsection, language=user.language)
            bot.send_message(user_id, msg)
        elif action == "CANCEL":
            user.status = status["enter_text"]
            user.change_number = None
            user.save
            try:
                bot.delete_message(chat_id=user_id, message_id=msg_id)
            except ApiTelegramException:
                pass
            msg = opener("select_date", "cancel", language=user.language)
            bot.send_message(user_id, msg)
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
    if user.status == status["select_language"]:
        bot.send_message(message.chat.id, opener("start", "start_of_use", language="EN"))
    elif user.status == status["enter_city"]:
        coordinates = getting_coordinates(message.text)
        time_zone = coordinates() if coordinates else coordinates
        # time_zone can be True only if coordinates = True
        # In other words, the two apis worked well
        if time_zone:
            user.time_zone = time_zone
            user.status = status["enter_text"]
            user.save()
            pm = "HTML"
            keyboard = reply_buttons("home_page", language=user.language)(resize_keyboard=True, row_width=2)
            context = context_gen("enter_city", "success_response", language=user.language)
            msg = render_to_string("bot_app/How_to_create.html", context=context)
        # time_zone = None when coordinates = True. In other words, the second api does not work
        # OR coordinates = None. In other words, the first api does not work
        elif time_zone is None:
            keyboard = pm = None
            msg = opener("enter_city", "bad_response", language=user.language)
        else:
            msg = opener("enter_city", "bad_city", language=user.language)
            keyboard = pm = None
        bot.send_message(message.chat.id, msg, parse_mode=pm, reply_markup=keyboard)
    elif message.text == opener("home_page", "btn1", language=user.language):
        if reminders := Reminder.objects.filter(user_id=message.chat.id, is_active__isnull=False):
            timezone.activate(tz_obj)
            local_values = {"reminders": reminders,
                            "relevance": opener("relevance", language=user.language)}
            context = context_gen("my_reminders", language=user.language, other=local_values)
            buttons = (types.InlineKeyboardButton(str(i), callback_data=f"REMINDER:NUMBER:{i}") for i in
                       range(1, len(reminders) + 1))
            keyboard = types.InlineKeyboardMarkup(row_width=3).add(*buttons)
            bot.send_message(message.chat.id, render_to_string("bot_app/My_reminders.html", context=context),
                             parse_mode="HTML", reply_markup=keyboard)
            timezone.deactivate()
        else:
            bot.send_message(message.chat.id, opener("my_reminders", "empty_list", language=user.language))
    elif message.text == opener("home_page", "btn2", language=user.language):
        if notes := Note.objects.filter(user_id=message.chat.id):
            local_values = {"notes": notes,
                            "relevance": opener("relevance", language=user.language)}
            context = context_gen("my_notes", language=user.language, other=local_values)
            buttons = (types.InlineKeyboardButton(str(i), callback_data=f"NOTE:NUMBER:{i}") for i in
                       range(1, len(notes) + 1))
            keyboard = types.InlineKeyboardMarkup(row_width=3).add(*buttons)
            bot.send_message(message.chat.id, render_to_string("bot_app/My_notes.html", context=context),
                             parse_mode="HTML", reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, opener("my_notes", "empty_list", language=user.language))
    elif message.text == opener("home_page", "btn3", language=user.language):
        local_values = {"users": User.objects.all().order_by("-score")[:10],
                        "relevance": opener("relevance", language=user.language)}
        context = context_gen("rating", language=user.language, other=local_values)
        bot.send_message(message.chat.id, render_to_string("bot_app/Rating.html", context=context),
                         parse_mode="HTML")
    elif message.text == opener("home_page", "btn4", language=user.language):
        timezone.activate(tz_obj)
        local_values = {"time_zone_value": user.time_zone,
                        "language_value": user.language,
                        "local_time_value": now,
                        "relevance": opener("relevance", language=user.language)}
        context = context_gen("settings", language=user.language, other=local_values)
        bot.send_message(message.chat.id, render_to_string("bot_app/Settings.html", context=context),
                         parse_mode="HTML")
        timezone.deactivate()
    elif user.status == status["enter_text"]:
        Note.objects.create(note_id=message.message_id, user_id=message.chat.id, note_text=message.text)
        user.status = status["select_date"]
        user.save()
        calendar = en_calendar if user.language == "EN" else ru_calendar
        bot.send_message(message.chat.id, opener("enter_text", language=user.language),
                         reply_markup=calendar.create_calendar(name="CALENDAR", month=now.month, year=now.year))
    elif user.status == status["select_date"]:
        bot.send_message(message.chat.id, opener("enter_text", language=user.language))
    elif user.status == status["enter_time"]:
        if is_time_format(message.text):
            hour, minute = list(map(int, message.text.split(":")))
            note = Note.objects.filter(user_id=message.chat.id).last()
            date = timezone.localtime(note.possible_date, timezone=tz_obj).replace(hour=hour, minute=minute)
            if date >= timezone.localtime(now, timezone=tz_obj):
                reminder = Reminder.objects.create(reminder_id=note.note_id,
                                                   user_id=note.user_id,
                                                   reminder_text=note.note_text,
                                                   date_time=date,
                                                   is_active=True)
                note.delete()
                user.reminder_count += 1
                user.status = status["enter_text"]
                user.save()
                schedule_reminder(reminder_date=reminder.date_time,
                                  user_id=message.chat.id,
                                  message=reminder.reminder_text,
                                  reminder=reminder,
                                  job_id=str(reminder.reminder_id))
                msg = opener("enter_time", "valid_time", language=user.language)
            else:
                msg = opener("enter_time", "bad_time", language=user.language)
        else:
            msg = opener("enter_time", "invalid_time", language=user.language)
        bot.send_message(message.chat.id, msg)


scheduler.add_job(check_inactive_reminders, 'interval', seconds=1)
scheduler.start()
bot.infinity_polling()
