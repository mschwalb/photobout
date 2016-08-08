import logging
import webapp2
import json
from webapp2_extras.security import generate_password_hash, check_password_hash

from gaesessions import get_current_session, set_current_session

from google.appengine.api import urlfetch, search
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore

from model.user import User
from model.user_picture import UserPicture
from model.photo import Photo
from model.winner import Winner
from model.notification import Notification
from model.invited import Invited
from model.third_party_user import ThirdPartyUser
from model.follower import Follower
from model.following import Following
from search_documents.search_documents import UserDocument
from util import util
from config import PEPPER

class SignupHandler(webapp2.RequestHandler):
    def post(self):
        email = self.request.get('email')
        first_name = self.request.get('first_name')
        last_name = self.request.get('last_name')
        password = self.request.get('password')
        confirm_password = self.request.get('confirm_password')
        device_token = self.request.get('token_hex')
        logging.info('Sign Up:: ')
        logging.info(email)
        if password == confirm_password:
            user = User.get_by_key_name(email)
            if user:
                response = {"success": False, "error": "Email already in use."}
            else:
                User.create(email, first_name, last_name, device_token, password)
                util.set_session(email)
                response = {"success": True}
        else:
            response = {"success": False, "error": "Passwords don't match."}
        self.response.write(json.dumps(response))

class LoginHandler(webapp2.RequestHandler):
    def check_password(self, email, password):
        password_hash = User.get_by_key_name(email).password
        return check_password_hash(password, password_hash, pepper=PEPPER)

    def handle_custom_login(self):
        email = self.request.get('email')
        password = self.request.get('password')
        logging.info('Custom Login:: ')
        logging.info(email)
        user = User.get_by_key_name(email)
        if user and ThirdPartyUser.for_user(user).count() > 0:
            response = {"success": False, "error": "You have previously logged in with Facebook. Please log in using Facebook."}
            return response
        device_token = self.request.get('token_hex')
        if user and self.check_password(email, password):
            User.update(email, device_token=device_token)
            util.set_session(email)
            response = {"success": True, "email": email, "first_name": user.first_name, "last_name": user.last_name}
        else:
            response = {"success": False, "error": "The email or password you entered is incorrect."}
        return response

    def get_profile_picture(self, id):
        response = json.loads(urlfetch.fetch("http://graph.facebook.com/%s/picture?redirect=false"%id).content)
        return response['data']['url']

    def handle_facebook_login(self):
        access_token = self.request.get('access_token')
        user_id = self.request.get('user_id')
        profile_url = 'https://graph.facebook.com/me?access_token=%s'
        profile = json.loads(urlfetch.fetch(profile_url%access_token).content)
        logging.info('Facebook Login:: ')
        logging.info(profile)
        id = profile['id']
        if not id == user_id:
            response = {"success": False, "error": "Facebook ids don't match."}
        else:
            if 'email' in profile:
                email = profile['email']
            else:
                email = id
            user = User.get_by_key_name(email)
            device_token = self.request.get('token_hex')
            if not user:
                user = User.create(email, profile['first_name'], profile['last_name'], device_token)
                ThirdPartyUser.create('FB', user, access_token, id)
                profile_picture = self.get_profile_picture(id)
                User.update(email, profile_picture=profile_picture, device_token=device_token)
            else:
                User.update(email, device_token=device_token)
            util.set_session(email)
            response = {"success": True, "email": email, "first_name": user.first_name, "last_name": user.last_name}
        return response

    def post(self, network):
        logging.info('Handling login for:: ')
        logging.info(network)
        if network == 'custom':
            response = self.handle_custom_login()
        elif network == 'facebook':
            response = self.handle_facebook_login()
        self.response.write(json.dumps(response))

class CheckSessionHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        session = get_current_session()
        self.response.write(session['email'] if session.has_key('email') else 'no key')

class ListUsersHandler(webapp2.RequestHandler):
    def post(self):
        email = self.request.get('email')
        util.set_session(email)

    def get(self):
        users = User.all().fetch(None)
        emails = [user.email for user in User.all()]
        current_user = util.get_user_from_session()
        template_values = {'emails': emails, 'current_user': current_user.email if current_user else None}
        path = 'templates/list_users.html'
        self.response.out.write(template.render(path, template_values))

class UsersSearchHandler(webapp2.RequestHandler):
    def post(self):
        search_string = self.request.get('search_string')
        results = UserDocument().fetch(search_string)
        response = {}
        response['users'] = []
        for user in results:
            user_obj = User.get_by_key_name(user['id'])
            if user_obj:
                user_dict = {}
                user_dict['name'] = user['fields']['name']
                user_dict['id'] = user['id']
                user_dict['profile_picture'] = user_obj.profile_picture
                response['users'].append(user_dict)
        self.response.write(json.dumps(response))

class TempUsersSearchHandler(webapp2.RequestHandler):
    def post(self):
        response = {}
        response['users'] = []
        search_string = self.request.get('search_string')
        cursor = self.request.get('cursor')
        search_resp = UserDocument().fetch_with_web_safe_string(search_string, web_safe_string=cursor, limit=10)
        results = search_resp['results']
        for user in results:
            user_obj = User.get_by_key_name(user['id'])
            if user_obj:
                user_dict = {}
                user_dict['name'] = user['fields']['name']
                user_dict['id'] = user['id']
                user_dict['profile_picture'] = user_obj.profile_picture
                response['users'].append(user_dict)
        response['cursor'] = search_resp['cursor']
        self.response.write(json.dumps(response))

class LogoutHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        user = util.get_user_from_session()
        user.device_token = None
        user.put()
        session = get_current_session()
        session.terminate()

def user_bout_dict_mapper(params):
    photo = params['result']
    user_email = params['user_email']
    return util.make_users_bout_dict(photo.bout, user_email)

def user_win_bout_dict_mapper(params):
    win = params['result']
    user_email = params['user_email']
    return util.make_users_bout_dict(win.bout, user_email)

class TempUsersBoutsHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        next_cursor = self.request.get('next')
        user_id = self.request.get('user_id')
        user = User.get_by_key_name(user_id)
        response = util.fetch_with_cursor(Photo.all().filter('user', user), limit=10, cursor=next_cursor, mapper=user_bout_dict_mapper, mapper_params={'user_email':user.email})
        self.response.write(json.dumps(response))

class TempUsersWinsHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        next_cursor = self.request.get('next')
        user_id = self.request.get('user_id')
        user = User.get_by_key_name(user_id)
        response = util.fetch_with_cursor(Winner.all().filter('user', user), limit=10, cursor=next_cursor, mapper=user_win_bout_dict_mapper, mapper_params={'user_email':user.email})
        self.response.write(json.dumps(response))

class UsersBoutsHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        user_id = self.request.get('user_id')
        user = User.get_by_key_name(user_id)
        photos = Photo.all().filter('user', user).fetch(20)
        current_user_email = util.get_email_from_session()
        response = [util.make_bout_dict(photo.bout, current_user_email) for photo in photos]
        self.response.write(json.dumps(response))

class UsersWinsHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        user_id = self.request.get('user_id')
        user = User.get_by_key_name(user_id)
        response = [util.make_bout_dict(win.bout, user.email) for win in Winner.for_user(user)]
        self.response.write(json.dumps(response))

def make_notification_dict(params):
    notification = params['result']
    notification_type = notification.notification_type
    bout = notification.bout
    current_user = util.get_email_from_session()
    from_user = User.get_by_key_name(notification.from_user)
    notification_dict = {}
    notification_dict['from_name'] = 'You' if current_user == from_user.email else from_user.name
    notification_dict['type'] = notification_type
    notification_dict['timestamp'] = notification.formatted_timestamp
    notification_dict['profile_picture'] = from_user.profile_picture
    notification_dict['bout'] = bout.id
    notification_dict['message'] = notification.message + ' ' + bout.name
    return notification_dict

class GetNotificationsHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        next = self.request.get('next')
        user = util.get_user_from_session()
        response = util.fetch_with_cursor(Notification.all().ancestor(user).order("-timestamp"), limit=20, cursor=next, mapper=make_notification_dict)
        self.response.write(json.dumps(response))

class AddProfilePictureHandler(blobstore_handlers.BlobstoreUploadHandler):
    @util.login_required
    def post(self):
        email = util.get_email_from_session()
        image_blob_key = str(self.get_uploads()[0].key())
        UserPicture.create_or_update(email, image_blob_key)
        profile_picture = '/users/profile_picture/get?email=%s'%email
        User.update(email, profile_picture=profile_picture)

    @util.login_required
    def get(self):
        response = {'upload_url': blobstore.create_upload_url('/users/profile_picture/add')}
        self.response.write(json.dumps(response))

class GetProfilePictureHandler(blobstore_handlers.BlobstoreDownloadHandler):
    @util.login_required
    def get(self):
        email = self.request.get('email')
        user_picture = UserPicture.for_(email)
        if user_picture:
            blob_key = user_picture.blob_key
            if blob_key:
                blob_info = blobstore.BlobInfo.get(blob_key)
                self.send_blob(blob_info)

class AddProfilePicturePageHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        template_values = {'upload_url': blobstore.create_upload_url('/users/profile_picture/add')}
        path = 'templates/add_profile_photo.html'
        self.response.out.write(template.render(path, template_values))

class UpdateProfileHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        user = util.get_user_from_session()
        first_name = self.request.get('first_name')
        last_name = self.request.get('last_name')
        User.update(user.email, first_name=first_name, last_name=last_name)

class AddFollowerHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        follower = util.get_user_from_session()
        following_email = self.request.get('following')
        following = User.get_by_key_name(following_email)
        if Following.for_(follower, following_email):
            response = {"success": False, "error": "Already following this user."}
        elif following:
            Follower.create(follower.email, following)
            Following.create(follower, following_email)
            logging.info(following.email)
            message = "%s is following you."%follower.name
            util.send_push_notification(following.email, message)
            response = {"success": True}
        else:
            response = {"success": False, "error": "User does not exist."}
        self.response.write(json.dumps(response))

class DeleteFollowerHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        follower_user = util.get_user_from_session()
        following_email = self.request.get('following')
        following_user = User.get_by_key_name(following_email)
        if following_user:
            follower = Follower.get_by_key_name(follower_user.email, parent=following_user)
            if follower:
                follower.delete()
            following = Following.get_by_key_name(following_email, parent=follower_user)
            if following:
                following.delete()

class GetFollowingHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        response = {}
        response['data'] = []
        follower_email = self.request.get('user_id')
        if follower_email:
            follower = User.get_by_key_name(follower_email)
            if follower:
                followings = Following.for_user(follower)
                for following in followings:
                    user = User.get_by_key_name(following.email)
                    user_dict = {}
                    user_dict['name'] = user.name
                    user_dict['id'] = user.email
                    user_dict['profile_picture'] = user.profile_picture
                    response['data'].append(user_dict)
        self.response.write(json.dumps(response))

class GetFollowerHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        response = {}
        response['data'] = []
        user_email = self.request.get('user_id')
        if user_email:
            user = User.get_by_key_name(user_email)
            if user:
                for follower in Follower.for_user(user):
                    follower_email = follower.email
                    follower_user = User.get_by_key_name(follower_email)
                    _dict = {}
                    _dict['id'] = follower_email
                    _dict['name'] = follower_user.name
                    _dict['profile_picture'] = follower_user.profile_picture
                    response['data'].append(_dict)
        self.response.write(json.dumps(response))

class IsFollowingHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        response = {}
        response['data'] = {}
        user_email = self.request.get('user_id')
        if user_email:
            user = User.get_by_key_name(user_email)
            if user:
                current_user = util.get_user_from_session()
                if current_user:
                    response['data']['is_following'] = Following.is_following(current_user, user_email)
        self.response.write(json.dumps(response))

class GetProfilePictureUrlHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        user = util.get_user_from_session()
        response = {'profile_picture_url': user.profile_picture}
        self.response.write(json.dumps(response))

application = webapp2.WSGIApplication([ ('/users/signup', SignupHandler),
                                        ('/users/logout', LogoutHandler),
                                        ('/users/update_profile', UpdateProfileHandler),
                                        ('/users/notifications/get', GetNotificationsHandler),
                                        ('/users/profile_picture/add', AddProfilePictureHandler),
                                        ('/users/profile_picture/get', GetProfilePictureHandler),
                                        ('/users/profile_picture_url', GetProfilePictureUrlHandler),
                                        ('/users/profile_picture/add_page', AddProfilePicturePageHandler),
                                        ('/users/followers/add', AddFollowerHandler),
                                        ('/users/followers/delete', DeleteFollowerHandler),
                                        ('/users/following/get', GetFollowingHandler),
                                        ('/users/followers/get', GetFollowerHandler),
                                        ('/users/is_following_user', IsFollowingHandler),
                                        ('/users/list', ListUsersHandler),
                                        ('/users/bouts', UsersBoutsHandler),
                                        ('/users/wins', UsersWinsHandler),
                                        ('/users/temp/bouts', TempUsersBoutsHandler),
                                        ('/users/temp/wins', TempUsersWinsHandler),
                                        ('/users/([^/]+)/login', LoginHandler),
                                        ('/users/checksession', CheckSessionHandler),
                                        ('/users/search', UsersSearchHandler),
                                        ('/users/temp/search', TempUsersSearchHandler)], debug=True)
