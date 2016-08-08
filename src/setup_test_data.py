import datetime

from model.user import User
from model.third_party_user import ThirdPartyUser
from model.bout import Bout
from model.photo import Photo
from model.vote import Vote
from model.comment import Comment
from model.notification import Notification
from model.following import Following
from model.follower import Follower
from model.winner import Winner
from util import util

def setup():
    user_1 = User.create('email1', 'firstname1', 'lastname1', 'password1')
    tp_user_1 = ThirdPartyUser(key_name='FB', parent=user_1)
    tp_user_1.network_id = '359059317608175'
    tp_user_1.put()
    user_2 = User.create('email2', 'firstname2', 'lasstname2', 'password2')
    tp_user_2 = ThirdPartyUser(key_name='FB', parent=user_2)
    tp_user_2.network_id = '359059317608175'
    tp_user_2.put()
    bout_1 = Bout.create(user_1, 'bout1', 'desc1', 1, 1)
    util.schedule_end(bout_1)
    photo_1 = Photo.create(bout_1, user_1, 'image_blob_key_1')
    photo_2 = Photo.create(bout_1, user_2, 'image_blob_key_2')
    bout_2 = Bout.create(user_2, 'bout2', 'desc2', 1, 2)
    util.schedule_end(bout_2)
    Vote.create('email1', photo_1)
    Vote.create('email2', photo_1)
    Vote.create('email2', photo_2)
    #photo_add, photo_vote, comment_add, winner, invited
    Notification.create('photo_add', bout_1.owner, user_2.email, bout_1)
    Notification.create('photo_vote', bout_1.owner, user_2.email, bout_1)
    Notification.create('comment_add', bout_1.owner, user_2.email, bout_1)
    Notification.create('winner', user_1, user_2.email, bout_1)
    Notification.create('invited', user_1, user_2.email, bout_1)
    #Winner.create(user_1, bout_1)
    Comment(parent=photo_1, user=user_1, message='message1', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_1, user=user_2, message='message2', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_1, message='message3', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_1, message='message4', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_2, message='message5', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_1, message='message6', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_2, message='message7', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_2, message='message8', timestamp=datetime.datetime.now()).put()
    Comment(parent=photo_2, user=user_2, message='message9', timestamp=datetime.datetime.now()).put()
    Follower.create('email1', user_2)
    Following.create(user_1, 'email2')