import webapp2
import time
import logging
from PyAPNs.apns import APNs, Frame, Payload

class NotifHandler(webapp2.RequestHandler):
    def get(self):
        apns = APNs(use_sandbox=True, cert_file='PhotoboutCert.pem', key_file='PhotoboutKeyNoEnc.pem')
        logging.info('Instantiated APNs')
        message = self.request.get('message')
        token_hex = '879825c6931847225caf5f015e9605b415d7c3688c7b4c548a77cb6ad65e2f94'
        bout_id = '4794405554749440'
        payload = Payload(alert=message, sound="default", badge=1, custom={'bid':bout_id})
        apns.gateway_server.send_notification(token_hex, payload)
        logging.info('... feedback_server')
        logging.info(apns.feedback_server)
        for (token_hex, fail_time) in apns.feedback_server.items():
        	logging.info(token_hex)
        	logging.info(fail_time)
        logging.info('Sent send_notification')

application = webapp2.WSGIApplication([ ('/temp/sample_notif', NotifHandler)], debug=True)
