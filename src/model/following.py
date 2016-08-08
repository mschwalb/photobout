from google.appengine.ext import db

class Following(db.Model):

    @classmethod
    def create(cls, follower, following_id):
        cls(parent=follower, key_name=following_id).put()

    @classmethod
    def for_user(cls, user):
        return cls.all().ancestor(user).fetch(None)

    @classmethod
    def for_(cls, follower, following_id):
        return cls.get_by_key_name(following_id, parent=follower)

    @classmethod
    def is_following(cls, follower, following_id):
        if cls.for_(follower, following_id):
            return True
        else:
            return False

    @property
    def email(self):
        return self.key().name()
