from django.db import models


class User(models.Model):
    id = models.IntegerField(primary_key=True)
    username = models.CharField(max_length=100)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    language = models.CharField(max_length=2, default=None, null=True)
    time_zone = models.CharField(max_length=50, default=None, null=True)
    status = models.CharField(max_length=15)
    change_number = models.IntegerField(default=None, null=True)
    reminder_count = models.IntegerField(default=0)

    def __str__(self):
        return f"| USERNAME:{self.username} | USER_ID:{self.id} |"


class Reminder(models.Model):
    reminder_id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reminder_text = models.TextField()
    date_time = models.DateTimeField(default=None, null=True)
    is_active = models.BooleanField(default=None, null=True)

    def __str__(self):
        return f"| REMINDER:{self.reminder_text} | REMINDER_ID:{self.reminder_id} | USER_ID:{self.user_id} |"


class Note(models.Model):
    note_id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note_text = models.TextField()
    possible_date = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return f"| NOTE:{self.note_text} | NOTE_ID:{self.note_id} | USER_ID:{self.user_id} |"
