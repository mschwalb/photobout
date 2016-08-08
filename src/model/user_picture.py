from google.appengine.ext import db
from google.appengine.ext import blobstore

class UserPicture(db.Model):
    blob_key = db.StringProperty(indexed=False)

    @classmethod
    def create_or_update(cls, email, blob_key):
        user_picture = cls.for_(email)
        if not user_picture:
            user_picture = cls(key_name=email)
        old_blob_key = user_picture.blob_key
        if old_blob_key:
            blobstore.delete(old_blob_key)
        user_picture.blob_key = blob_key
        user_picture.put()

    @classmethod
    def for_(cls, email):
        return cls.get_by_key_name(email)