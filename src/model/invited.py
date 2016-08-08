from google.appengine.ext import db

class Invited(db.Model):
    timestamp = db.DateTimeProperty(indexed=False)
    invited_by = db.ReferenceProperty(indexed=False)

    @classmethod
    def for_user(cls, user):
        return cls.all().ancestor(user).fetch(None)

    @classmethod
    def for_(cls, user, bout):
    	return cls.get_by_key_name(str(bout.id), parent=user)