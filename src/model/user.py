from webapp2_extras.security import generate_password_hash, check_password_hash

from google.appengine.ext import db
from google.appengine.ext import blobstore

from config import PEPPER

from search_documents.search_documents import UserDocument

class User(db.Model):
    first_name = db.StringProperty(indexed=False)
    last_name = db.StringProperty(indexed=False)
    password = db.StringProperty(indexed=False)
    profile_picture = db.StringProperty(indexed=False)
    device_token = db.StringProperty(indexed=False)

    @property
    def name(self):
        return "%s %s"%(self.first_name, self.last_name)

    @classmethod
    def create(cls, email, first_name, last_name, device_token, password=None):
        if not password:
            password = 'makethisrandom'
        password_hash = generate_password_hash(password, pepper=PEPPER)
        user = cls(key_name=email, first_name=first_name, last_name=last_name, device_token=device_token, password=password_hash)
        UserDocument().create(email, name="%s %s"%(first_name, last_name))
        user.put()
        return user

    @classmethod
    def update(cls, email, first_name=None, last_name=None, device_token=None, profile_picture=None):
        user = cls.get_by_key_name(email)
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if profile_picture:
            user.profile_picture = profile_picture
        if device_token:
            user.device_token = device_token
        if first_name or last_name:
            UserDocument().create(email, name="%s %s"%(user.first_name, user.last_name))
        user.put()

    @property
    def email(self):
        return self.key().name()

    @staticmethod
    def get_by_email(email):
        return User.all().filter('email =',email)
