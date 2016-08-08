import logging
import json
    
from google.appengine.ext import deferred
from gaesessions import get_current_session
from google.appengine.api import mail
from google.appengine.api import urlfetch

from model.vote import Vote
from model.photo import Photo
from model.user import User
from model.winner import Winner
from model.bout import Bout
from model.comment import Comment
from model.following import Following
from model.invited import Invited
from model.notification import Notification
from model.third_party_user import ThirdPartyUser
from model.invited import Invited

from PyAPNs.apns import APNs, Frame, Payload

MAIL_TEMPLATES = {
    'forgot_password': {
        'subject': 'Password Reset',
        'body': "Click to reset password: {template_values[reset_link]}"
    }
}

def send_push_notification(email, message, bout_id=None):
    device_token = User.get_by_key_name(email).device_token
    if device_token:
        logging.info('... sending notification')
        logging.info(email)
        logging.info(message)
        logging.info(bout_id)
        apns = APNs(use_sandbox=False, cert_file='PhotoboutProdCert.pem', key_file='PhotoboutProdKeyNoEnc.pem')
        payload = Payload(alert=message, sound="default", badge=1, custom={'bid':bout_id})
        apns.gateway_server.send_notification(device_token, payload)

def send_notifications(users, message, bout_id=None):
    for user in users:
        deferred.defer(send_push_notification, user, message, bout_id)

def fetch_with_cursor(query, limit=10, cursor=None, mapper=None, mapper_params={}):
    response = {}
    response['data'] = []
    if cursor:
        query.with_cursor(start_cursor=cursor)
    max_count = 0
    for count, result in enumerate(query, start=1):
        max_count = count
        mapper_params['result'] = result
        mapper_response = mapper(mapper_params)
        if mapper_response:
            response['data'].append(mapper_response)
        if count >= limit:
            break
    response['next'] = None if max_count < limit else query.cursor()
    return response

def send_mail(to, template, **kwargs):
    subject = MAIL_TEMPLATES[template]['subject']
    body = MAIL_TEMPLATES[template]['body'].format(template_values=kwargs)
    sender = "support@b-eagles.com"
    mail.send_mail(sender=sender, to=to, subject=subject, body=body)

def make_photo_dict(photo, email):
    photo_dict = {}
    owner = User.get_by_key_name(photo.owner_email)
    photo_dict['image'] = photo.image_url
    photo_dict['owner_email'] = photo.owner_email
    photo_dict['owner_first_name'] = owner.first_name
    photo_dict['owner_last_name'] = owner.last_name
    photo_dict['num_votes'] = Vote.count(photo)
    photo_dict['num_comments'] = len(Comment.for_(photo))
    photo_dict['is_voted'] = Vote.is_voted(email, photo)
    photo_dict['profile_picture'] = owner.profile_picture
    return photo_dict

def make_bout_dict(bout, email):
    bout_dict = {}
    bout_dict['id'] = bout.id
    bout_dict['name'] = bout.name
    bout_dict['description'] = bout.description
    bout_dict['time_left'] = bout.time_left_string
    bout_dict['ended'] = bout.ended
    bout_dict['photos'] = []
    user_in_session_photo = Photo.for_bout_user(bout, email)
    if user_in_session_photo:
        photo_dict = make_photo_dict(user_in_session_photo, email)
        bout_dict['photos'].append(photo_dict)
    for photo in sorted(Photo.for_(bout), key=lambda x: Vote.count(x), reverse=True):
        if photo.owner_email != email:
            photo_dict = make_photo_dict(photo, email)
            bout_dict['photos'].append(photo_dict)
    if bout.ended:
        bout_dict['winners'] = []
        winners = Winner.for_bout(bout)
        if len(winners) > 0:
            for winner in winners:
                bout_dict['winners'].append(winner.email)
    return bout_dict

def make_users_bout_dict(bout, email):
    bout_dict = {}
    bout_dict['id'] = bout.id
    bout_dict['name'] = bout.name
    bout_dict['photos'] = []
    num_photos = Photo.all().ancestor(bout).count()
    user_uploaded_photo = Photo.for_bout_user(bout, email)
    if user_uploaded_photo:
        bout_dict['photos'].append({'image':user_uploaded_photo.image_url})
        num_photos -= 1
    for i in range(0, num_photos):
        bout_dict['photos'].append({})
    bout_dict['ended'] = bout.ended
    if bout_dict['ended']:
        bout_dict['winners'] = []
        if Winner.for_bout_user(bout, email):
            bout_dict['winners'].append(email)
    return bout_dict

def schedule_end(bout):
    deferred.defer(set_winner, bout, _eta=bout.end_time)

def set_winner(bout):
    bout.change_status(2)
    participants = sorted(Photo.for_(bout), key=lambda x: Vote.count(x), reverse=True)
    if len(participants) > 0:
        max_vote_count = Vote.count(participants[0])
        if max_vote_count > 0:
            for participant in participants:
                current_vote_count = Vote.count(participant)
                if current_vote_count == max_vote_count:
                    winner = User.get_by_key_name(participant.owner_email)
                    Winner.create(winner, bout)
                    Notification.create('winner', winner, winner.email, bout)
                elif current_vote_count < max_vote_count:
                    break

def _user_has_permission(handler):
    bout_id = long(handler.request.get('bout_id'))
    bout = Bout.get_by_id(bout_id)
    if not bout:
        logging.info('... invalid bout id')
        return False
    if bout.permission == 1:
        logging.info('... public bout')
        return True
    email = get_email_from_session()
    if bout.owner.email == email:
        logging.info('... is owner')
        return True
    user = User.get_by_key_name(email)
    if Invited.for_(user, bout):
        logging.info('... invited')
        return True
    logging.info('... no permission')
    return False

def bout_permission_required(fn):
    def check_permission(self, *args):
        if _user_has_permission(self):
            fn(self, *args)
    return check_permission

def get_user_from_session():
    session = get_current_session()
    return User.get_by_key_name(session['email']) if 'email' in session else None

def get_email_from_session():
    session = get_current_session()
    return session['email'] if 'email' in session else None

def set_session(email):
    session = get_current_session()
    session['email'] = email

def _user_logged_in(handler):
    session = get_current_session()
    if session.is_active() and 'email' in session:
        if User.get_by_key_name(session['email']):
            return True
        session.terminate()
    return False

def login_required(fn):
    def check_login(self, *args):
        if _user_logged_in(self):
            fn(self, *args)
    return check_login
