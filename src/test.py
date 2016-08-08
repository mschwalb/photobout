import webapp2

from gaesessions import get_current_session

class Test(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('ehhhh')

application = webapp2.WSGIApplication([('/test', Test)], debug=True)