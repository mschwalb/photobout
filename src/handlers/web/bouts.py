import webapp2
import json
import logging
import datetime

from gaesessions import get_current_session
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.ext import deferred
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import blobstore_handlers

from model.user import User
from model.third_party_user import ThirdPartyUser
from model.bout import Bout
from model.photo import Photo
from model.vote import Vote
from model.comment import Comment
from model.invited import Invited
from model.notification import Notification
from model.following import Following
from util import util
from util.util import send_push_notification
from search_documents.search_documents import BoutDocument

class CreateBoutHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        user = util.get_user_from_session()
        name = self.request.get('name')
        period = self.request.get('period')
        permission = self.request.get('permission')
        description = self.request.get('description')
        if not permission:
            permission = 2
        bout = Bout.create(user, name, description, period, permission)
        util.schedule_end(bout)
        if int(permission) == 1:
            users = [following.email for following in Following.for_user(user)]
            message = "%s created a new Bout %s"%(user.name, bout.name)
            util.send_notifications(users, message, bout.id)
        response = {'id': bout.id}
        self.response.write(json.dumps(response))

    def get(self):
        template_values = {}
        path = 'templates/create_bout.html'
        self.response.out.write(template.render(path, template_values))

def send_add_photo_notifications(bout, from_user_email):
    if bout and from_user_email:
        Notification.create('photo_add', bout.owner, from_user_email, bout)
        photos = Photo.for_(bout)
        if len(photos)>0:
            for photo in photos:
                if photo.owner_email != from_user_email and photo.owner_email != bout.owner.email:
                    Notification.create('photo_add', photo.user, from_user_email, bout)

class AddPhotoHandler(blobstore_handlers.BlobstoreUploadHandler):
    @util.login_required
    @util.bout_permission_required
    def post(self):
        user = util.get_user_from_session()
        bout_id = long(self.request.get('bout_id'))
        image_blob_key = str(self.get_uploads()[0].key())
        bout = Bout.get_by_id(bout_id)
        photo = Photo.for_bout_user(bout, user.email)
        if photo:
            votes = Vote.for_photo(photo)
            if len(votes) > 0:
                db.delete(votes)
        Photo.create(bout, user, image_blob_key)
        deferred.defer(send_add_photo_notifications, bout, user.email)
        
    @util.login_required
    def get(self):
        response = {'upload_url': blobstore.create_upload_url('/bouts/photos/add')}
        self.response.write(json.dumps(response))

class AddPhotoPageHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        template_values = {'upload_url': blobstore.create_upload_url('/bouts/photos/add')}
        path = 'templates/add_photo.html'
        self.response.out.write(template.render(path, template_values))

class GetPhotoHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        blob_key = self.request.get('blob_key')
        blob_info = blobstore.BlobInfo.get(blob_key)
        self.send_blob(blob_info)

class PhotoVoteHandler(webapp2.RequestHandler):
    @util.login_required
    @util.bout_permission_required
    def post(self):
        response = {}
        user = util.get_user_from_session()
        email = user.key().name()
        owner_email = self.request.get('owner_email')
        bout_id = long(self.request.get('bout_id'))
        bout = Bout.get_by_id(bout_id)
        photo = Photo.get_by_key_name(owner_email, parent=bout)
        if Vote.update(email, photo, bout):
            Notification.create('photo_vote', bout.owner, user.email, bout)
            message = "%s voted on your photo in the Bout %s."%(user.name, bout.name)
            util.send_push_notification(photo.user.email, message, bout.id)
            response = {"success": True, "voted": True}
        else:
            response = {"success": True, "voted": False}
        vote_count = Vote.count(photo)
        response["vote_count"] = vote_count
        self.response.write(json.dumps(response))

class AddCommentHandler(webapp2.RequestHandler):
    @util.login_required
    @util.bout_permission_required
    def post(self):
        user = util.get_user_from_session()
        message = self.request.get('message')
        owner_email = self.request.get('owner_email')
        bout_id = self.request.get('bout_id')
        bout = Bout.get_by_id(long(bout_id))
        photo = Photo.for_bout_user(bout, owner_email)
        Comment.create(user, photo, message)
        Notification.create('comment_add', photo.bout.owner, user.email, bout)

    def get(self):
        template_values = {}
        path = 'templates/add_comment.html'
        self.response.out.write(template.render(path, template_values))

def make_comment_dict(params):
    comment = params['result']
    comment_dict = {}
    comment_dict['first_name'] = comment.user.first_name
    comment_dict['last_name'] = comment.user.last_name
    comment_dict['message'] = comment.message
    comment_dict['id'] = comment.user.email
    comment_dict['timestamp'] = comment.formatted_timestamp
    comment_dict['profile_picture'] = comment.user.profile_picture
    return comment_dict

class GetCommentsHandler(webapp2.RequestHandler):
    @util.login_required
    @util.bout_permission_required
    def get(self):
        next = self.request.get('next')
        owner_email = self.request.get('owner_email')
        bout_id = long(self.request.get('bout_id'))
        bout = Bout.get_by_id(bout_id)
        photo = Photo.for_bout_user(bout, owner_email)
        response = util.fetch_with_cursor(Comment.all().ancestor(photo).order("-timestamp"), limit=20, cursor=next, mapper=make_comment_dict)
        self.response.write(json.dumps(response))

class LeaderboardHandler(webapp2.RequestHandler):
    @util.login_required
    @util.bout_permission_required
    def get(self):
        response = []
        bout_id = long(self.request.get('bout_id'))
        bout = Bout.get_by_id(bout_id)
        for rank, photo in enumerate(sorted(Photo.for_(bout), key=lambda x: Vote.count(x), reverse=True), start=1):
            user_dict = {}
            owner = User.get_by_key_name(photo.owner_email)
            user_dict['votes'] = Vote.count(photo)
            user_dict['rank'] = rank
            user_dict['email'] = photo.owner_email
            user_dict['first_name'] = owner.first_name
            user_dict['last_name'] = owner.last_name
            user_dict['profile_picture'] = owner.profile_picture
            response.append(user_dict)
        self.response.write(json.dumps(response))

class AddInviteHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        ids_str = self.request.get('ids')
        ids = [id for id in ids_str.split(';') if len(id) > 0]
        bout_id = self.request.get('bout_id')
        if len(ids) <= 0:
            return
        invited_by = util.get_user_from_session()
        bout = Bout.get_by_id(long(bout_id))
        for id in ids:
            user = User.get_by_key_name(id)
            Invited(key_name=bout_id, parent=user, timestamp=datetime.datetime.now(), invited_by=invited_by).put()
            Notification.create('invited', user, invited_by.email, bout)
            message = "%s invited you to the bout %s"%(invited_by.name, bout.name)
            deferred.defer(send_push_notification, user.email, message, bout_id)

class GetInvitesHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        user = util.get_user_from_session()
        email = user.email
        response = []
        for invite in Invited.for_(user):
            invite_dict = {}
            bout_id = long(invite.key().name())
            bout = Bout.get_by_id(bout_id)
            invite_dict['bout'] = util.make_bout_dict(bout, email)
            invite_dict['timestamp'] = invite.timestamp.strftime('%x %X')
            invite_dict['profile_picture'] = user.profile_picture
            invite_dict['invited_by_name'] = invite.invited_by.name
            response.append(invite_dict)
        self.response.write(json.dumps(response))

class DeleteInviteHandler(webapp2.RequestHandler):
    @util.login_required
    def post(self):
        user = util.get_user_from_session()
        bout_id = self.request.get('bout_id')
        invite = Invited.get_by_key_name(bout_id, parent=user)
        if invite:
            invite.delete()

class GetBoutsHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        next = self.request.get('next')
        status = self.request.get('status')
        bout_id = self.request.get('bout_id')
        user = util.get_user_from_session()
        if bout_id:
            email = user.email
            bout = Bout.get_by_id(long(bout_id))
            response = [util.make_bout_dict(bout, email)]
        elif status == 'current':
            response = util.fetch_with_cursor(Bout.all().filter('status', 1).order("-created_at"), cursor=next, mapper=_get_current_bouts, mapper_params={'user': user})
        elif status == 'past':
            response = util.fetch_with_cursor(Bout.all().filter('status', 2).order("-created_at"), cursor=next, mapper=_get_past_bouts, mapper_params={'user': user})
        else:
            response = util.fetch_with_cursor(Bout.all().filter('status', 1).order("-created_at"), cursor=next, mapper=_get_open_bouts, mapper_params={'user': user})
        self.response.write(json.dumps(response))

def _get_open_bouts(params):
    user = params['user']
    bout = params['result']
    if bout.permission == 2:
        if bout.owner.email != user.email and not Invited.for_(user, bout):
            return
    return util.make_bout_dict(bout, user.email)

def _get_past_bouts(params):
    user = params['user']
    bout = params['result']
    if bout.permission == 2:
        if bout.owner.email != user.email and not Invited.for_(user, bout):
            return
    return util.make_bout_dict(bout, user.email)

def _get_current_bouts(params):
    user = params['user']
    bout = params['result']
    if bout.permission == 2:
        if bout.owner.email != user.email and not Invited.for_(user, bout):
            return
    if not Photo.get_by_key_name(user.email, parent=bout):
        return
    return util.make_bout_dict(bout, user.email)

class BoutSearchHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        response = []
        name = self.request.get('name')
        results = BoutDocument().fetch(name)
        if len(results) > 0:
            user = util.get_user_from_session()
            email = user.email
            for result in results:
                bout_id = str(result['id'])
                if bout_id and len(bout_id) > 0:
                    bout = Bout.get_by_id(long(bout_id))
                    if bout:
                        response.append(util.make_bout_dict(bout, email))
        self.response.write(json.dumps(response))

class TempBoutSearchHandler(webapp2.RequestHandler):
    @util.login_required
    def get(self):
        response = {}
        response['bouts'] = []
        name = self.request.get('name')
        cursor = self.request.get('cursor')
        search_resp = BoutDocument().fetch_with_web_safe_string(name, web_safe_string=cursor, limit=10)
        results = search_resp['results']
        if len(results) > 0:
            user = util.get_user_from_session()
            email = user.email
            for result in results:
                bout_id = str(result['id'])
                if bout_id and len(bout_id) > 0:
                    bout = Bout.get_by_id(long(bout_id))
                    if bout:
                        response['bouts'].append(util.make_bout_dict(bout, email))
        response['cursor'] = search_resp['cursor']
        self.response.write(json.dumps(response))

class UpdateBoutsHandler(webapp2.RequestHandler):
    @util.login_required
    @util.bout_permission_required
    def post(self):
        bout_id = self.request.get('bout_id')
        permission = self.request.get('permission')
        email = util.get_email_from_session()
        bout = Bout.get_by_id(long(bout_id))
        if bout.owner.email == email:
            Bout.update(bout_id, permission)

class TestHandler(webapp2.RequestHandler):
    @util.login_required
    @util.bout_permission_required
    def get(self):
        self.response.write('... wrkign')

application = webapp2.WSGIApplication([ ('/bouts/create', CreateBoutHandler),
                                        ('/bouts/get', GetBoutsHandler),
                                        ('/bouts/update', UpdateBoutsHandler),
                                        ('/bouts/test', TestHandler),
                                        ('/bouts/search', BoutSearchHandler),
                                        ('/bouts/temp/search', TempBoutSearchHandler),
                                        ('/bouts/leaderboard', LeaderboardHandler),
                                        ('/bouts/photos/add', AddPhotoHandler),
                                        ('/bouts/photos/add_page', AddPhotoPageHandler),
                                        ('/bouts/photos/get', GetPhotoHandler),
                                        ('/bouts/photos/vote', PhotoVoteHandler),
                                        ('/bouts/comments/add', AddCommentHandler),
                                        ('/bouts/comments/get', GetCommentsHandler),
                                        ('/bouts/invites/add', AddInviteHandler),
                                        ('/bouts/invites/get', GetInvitesHandler),
                                        ('/bouts/invites/delete', DeleteInviteHandler)], debug=True)
