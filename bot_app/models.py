from django.db import models


class User(models.Model):
    id = models.IntegerField(primary_key=True)
    username = models.CharField(max_length=100)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    language = models.CharField(max_length=2, default=None, null=True)
    time_zone = models.CharField(max_length=50, default=None, null=True)
    status = models.CharField(max_length=15)
    reminder_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.username}:{self.id}"


class Reminder(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    date_time = models.DateTimeField(default=None, null=True)
    is_active = models.BooleanField(default=None, null=True)

    def __str__(self):
        return f"{self.text.split()[0]}:{self.id}:{self.user_id}"
