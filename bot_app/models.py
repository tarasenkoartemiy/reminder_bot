from django.db import models


class User(models.Model):
    id = models.IntegerField(primary_key=True)
    username = models.CharField(max_length=100)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    language = models.CharField(max_length=2, default=None, null=True)
    time_zone = models.CharField(max_length=50, default=None, null=True)
    user_initialization = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    score = models.IntegerField(default=0)
    status = models.IntegerField()
    change_number = models.IntegerField(default=None, null=True)

    def __str__(self):
        return f"| USERNAME:{self.username} | USER_ID:{self.id} |"


class LastMessages(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    reminder_message_id = models.IntegerField(default=None, null=True)
    note_message_id = models.IntegerField(default=None, null=True)
    calendar_id = models.IntegerField(default=None, null=True)

    def __str__(self):
        return (f"| USER_ID:{self.user_id} "
                f"| REMINDER_MESSAGE_ID:{self.reminder_list_id} "
                f"| NOTE_MESSAGE_ID:{self.note_list_id} "
                f"| CALENDAR_ID:{self.calendar_id} |")


class Reminder(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    date_time = models.DateTimeField(default=None, null=True)
    is_active = models.BooleanField(null=True)

    def __str__(self):
        return f"| REMINDER:{self.text} | REMINDER_ID:{self.id} | USER_ID:{self.user_id} |"


class Note(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    possible_date = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return f"| NOTE:{self.text} | NOTE_ID:{self.id} | USER_ID:{self.user_id} |"
