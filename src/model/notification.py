import datetime

from google.appengine.ext import db

MESSAGES = {
    'photo_add': 'added a photo to',
    'photo_vote': 'voted on your photo in',
    'comment_add': 'commented on',
    'winner': 'have won the Bout',
    'invited': 'invited you to'
    }

class Notification(db.Model):
    notification_type = db.StringProperty(indexed=False)
    bout = db.ReferenceProperty(indexed=False)
    from_user = db.StringProperty(indexed=False)
    viewed = db.BooleanProperty(indexed=False)
    timestamp = db.DateTimeProperty()

    @property
    def user(self):
        return self.parent()

    @property
    def formatted_timestamp(self):
        posted_time_string = ""
        total_hours = int(abs((datetime.datetime.now() - self.timestamp).total_seconds()))/(3600)
        hours = total_hours%24
        days = total_hours/24
        if days >= 1:
            posted_time_string += "%s d, %s h ago"%(days, hours)
        else:
            posted_time_string += "%s h ago"%hours
        return posted_time_string

    @classmethod
    def for_(cls, user):
        return cls.all().ancestor(user).fetch(None)

    @classmethod
    def create(cls, type, user, from_user, bout):
        cls(parent=user, notification_type=type, bout=bout, from_user=from_user, viewed=False, timestamp=datetime.datetime.now()).put()

    @property
    def message(self):
        return MESSAGES[self.notification_type]
  