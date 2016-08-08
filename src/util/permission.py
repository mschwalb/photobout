import logging

from model.bout import Bout
from model.photo import Photo
from util import session

def _user_has_permission(handler):
	bout_id = long(handler.request.get('bout_id'))
	bout = Bout.get_by_id(bout_id)
	if not bout:
		logging.info('... invalid bout id')
		return False
	if bout.permission == 1:
		logging.info('... public bout')
		return True
	user = session.get_user_from_session()
	if bout.owner.email == user.email:
		logging.info('... is owner')
		return True
	if Photo.get_by_key_name(user.email, parent=bout):
		logging.info('... is participant')
		return True
	return False

def bout_permission_required(fn):
    def check_permission(self, *args):
        if _user_has_permission(self):
            fn(self, *args)
    return check_permission
