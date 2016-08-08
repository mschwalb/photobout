from gaesessions import get_current_session

from model.user import User

def get_user_from_session():
	session = get_current_session()
	return User.get_by_key_name(session['email']) if 'email' in session else None

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
