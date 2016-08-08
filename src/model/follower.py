from google.appengine.ext import db

class Follower(db.Model):

    @classmethod
    def create(cls, follower_id, following):
        cls(parent=following, key_name=follower_id).put()

    @classmethod
    def for_user(cls, user):
        return cls.all().ancestor(user).fetch(None)

    @classmethod
    def for_(cls, follower_id, following):
        return cls.get_by_key_name(follower_id, parent=following)

    @property
    def email(self):
        return self.key().name()
