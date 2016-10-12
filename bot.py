import random
import datetime
import re

# App Engine API
import webapp2
from google.appengine.ext import ndb
from google.appengine.api import taskqueue

# Twilio API
from twilio import twiml
from twilio.rest import TwilioRestClient

# All the talking parts
import text

# Twilio account information
account_phone_number = '+19006665555' # put your Twilio number here
account_sid = 'ABCDEFG1234567890' # put your Twilio account SID here
auth_token = 'ABCDEFG1234567890' # put your Twilio account auth token here
client = TwilioRestClient(account_sid, auth_token)

# Return this XML when someone calls the Twilio number. It simply plays the MP3 back to them.
call_response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
<Say>I'm sorry, I can't talk.  Goodbye.</Say>
</Response>
"""

# Return this empty Response object when receiving text messages.
empty_response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response />
"""

# Model for the user data
class UserState(ndb.Model):
	# Phone number (this should probably be the NDB key, but it doesn't really matter here)
	phone_number = ndb.StringProperty(indexed=True,required=True)
	
	# Keep track of users that have chosen to unsubscribe, to be compliant with Twilio's guidelines.
	subscribed = ndb.BooleanProperty(required=True,default=False)
	
	# Trail info
	trail_step = ndb.IntegerProperty(default=0)
	max_trail_step = ndb.IntegerProperty(default=0)
	seen_step_0_before = ndb.BooleanProperty(required=True,default=False)
	
	# Statistics
	first_datetime = ndb.DateTimeProperty(auto_now_add=True,required=True)
	last_datetime = ndb.DateTimeProperty(auto_now=True,required=True)
	message_count = ndb.IntegerProperty(default=0,required=True)
	
# http://bot.appspot.com/ shouldn't have any info on it
class Index(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		self.response.write('There is nothing here.')

# Query the datastore. If user doesn't exist, create a new UserState object		
def retrieve_or_create_user(sms_sender):
	state = UserState.query(UserState.phone_number==sms_sender).get()
	if not state:
		state = UserState(phone_number=sms_sender)
	return state

# Query the datastore. Return true if the user exists.
def user_exists(sms_sender):
	state = UserState.query(UserState.phone_number==sms_sender).get()
	return state is not None

# Take any incoming message and convert to lowercase, remove spaces and common punctuation	
def standardize_message(message):
	return (''.join(ch for ch in message if ch.isalnum() )).lower()

def create_responses(state, message):

	"""
	Process the message, update user state, and return any response messages.
	
	If they choose to unsubscribe, then we record that in the database and
	never send them another SMS message, unless they send "START" again.
	
	"""	
	
	responses = []
	
	# Add the incoming message to the message count
	state.message_count += 1
	
	# Use lowercase, and remove spaces
	standardized_message = standardize_message(message)
	
	# If the user sends 'start', reset state and subscribe them
	if standardized_message==('start'):
		state.trail_step = 0
		state.subscribed = True # Make sure user is marked as subscribed
		
	# If user is unsubscribed, don't respond
	if not state.subscribed:
		return None
	
	# If the user is already unsubscribed, keep them unsubscribed
	# Unsubscribe the user if they send STOP, UNSUBSCRIBE, CANCEL, or QUIT
	if standardized_message in ('stop', 'unsubscribe', 'cancel', 'quit'):
		# Mark as unsubscribed, save state, and return no response
		state.subscribed = False
		responses.append("You will not receive any more messages from this number. Reply START to try again.")
		return responses
	
	# Ensure we haven't gone past the end
	if state.trail_step >= len(text.steps):
		state.trail_step = len(text.steps) - 1
	
	# Check if the answer is correct
	got_correct = False
	fact_prefix = ''

	if standardize_message(message) == text.steps[state.trail_step]['answer']:
		
		# Correct answer for other steps
		got_correct = True

	# Go to the next step if correct, don't go past the end.
	if got_correct and state.trail_step + 1 < len(text.steps):
		state.trail_step += 1
		
	# Include full talking text if it's the first step or a new step
	if (state.trail_step==0 and state.seen_step_0_before and not(got_correct)):
		responses += ['OK, text \'ready\' when you\'re ready.']
	elif (state.trail_step==0 or got_correct) and len(text.steps[state.trail_step]['flavor']) > 0:
		responses += text.steps[state.trail_step]['flavor']
		responses += [text.steps[state.trail_step]['question'],]
	elif not(got_correct):
		responses += [fact_prefix]
	
	# Cut the responses down to less than 160 characters
	for i in range(len(responses)):
		if len(responses[i]) >= 160:
			responses[i] = responses[i][:156] + '...'
	
	# Add the # of responses to the message count
	state.message_count += len(responses)
	
	# Set the maximum trail step
	state.max_trail_step = max(state.max_trail_step, state.trail_step)

	# have they seen the opening?
	state.seen_step_0_before = True

        # unsubscribe if trail is done
        if (state.trail_step >= len(text.steps)-1):
		state.subscribed = False

	return responses

# Respond to a text message		 
class Respond(webapp2.RequestHandler):

	"""
	Handle every incoming SMS or XMLHttpRequest from the demo page.
	
	We use the 'from' phone number to retrieve the user's information,
	then determine the response. For SMS users, we add all the responses
	to an outgoing queue. For demo users, we simply return it in the page content.
	"""

	def post(self):

		# Get the POST data
		sms_sender = self.request.get('From')
		message = self.request.get('Body')
		
		# Retrieve the user
		state = retrieve_or_create_user(sms_sender)
	
		# Create the response
		responses = create_responses(state, message)
		
		# Save state
		state.put()
	
		# Return if there are no responses (unsubscribed)
		if responses is None:
			return
		
		# Send the response
		if sms_sender.startswith('demo'):
			# As text, for the demo page
			self.response.headers['Content-Type'] = 'text/plain'
			response = '\n'.join(responses)
			response = response.replace('<', '&lt;').replace('>', '&gt;').replace('\n','<br>')
			self.response.write(response)
		else:
			# For each response, add it to the task queue
			for i, response in enumerate(responses):
				
				# Set the countdown for this SMS, hopefully this will help keep the texts in order
				countdown = i*2
				
				# Or add this SMS to the task queue
				taskqueue.add(queue_name='sms', url='/sendsms', countdown=countdown, params={'to': sms_sender, 'body': response})
			
			# Send an empty response back to Twilio
			self.response.headers['Content-Type'] = 'text/xml'
			self.response.write(empty_response_xml)

# Send an SMS from the task queue				
class SendSMS(webapp2.RequestHandler):

	"""
	Process the outgoing SMS task queue.
	
	(Please read Google's documentation on GAE task queues.)
	
	For every outgoing SMS, we take the user's phone number,
	make sure we've communicated with them before, and send the message.
	
	Note that we do *not* check if the user is subscribed or not. Otherwise we wouldn't be
	able to send an acknowledgement when they unsubscribe.
	"""

	def post(self):
		# Get the sender and SMS responses
		to = self.request.get('to')
		body = self.request.get('body')

		# Never send an SMS to someone not in the database
		if not user_exists(to):
			return
	
		# Send via Twilio
		sms = client.sms.messages.create(to=to, from_=account_phone_number, body=body)	

# Demo HTML for testing
demo_html = """<html>
<head>
<style type="text/css">
div.message  {font-style: italic; padding-top: 5px; padding-bottom: 5px;}
div.response {font-weight: bold;}
</style>
<script type="text/javascript">
function send()
{
	var message = document.forms[0]["text"].value;
	document.getElementsByTagName("body")[0].innerHTML += "<div class=\\\"message\\\">" + message + "</div>";
	
	var params = "From=%s&Body="+message;
	x = new XMLHttpRequest();
	x.open("POST","/respond",true);
	x.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
	x.setRequestHeader("Content-length", params.length);
	x.setRequestHeader("Connection", "close");
	x.onreadystatechange=function()
	  {
	  if (x.readyState==4 && x.status==200)
		{
			document.getElementsByTagName("body")[0].innerHTML += "<div class=\\\"response\\\">" + x.responseText + "</div>";
		}
	  }
	x.send(params);
}
</script>
</head>
<body>
<div class="response">This is trailhead #1. Text START to 510 2000 449 to begin.</div>
<div>
  <form onsubmit="send(); return false;">
  <input type="text" name="text" autofocus />
  <input type="submit" value="Send" />
  </form>
</div>
</body>
</html>
"""

class Demo(webapp2.RequestHandler):

	"""
	Display a page that runs a demo of the training.
	
	(You can use this for testing instead of text messages.)
	"""

	# Send the demo HTML, giving a random demo ID
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		id = 'demo' + str(random.randrange(10000));
		self.response.write(demo_html%id)
		
class Voice(webapp2.RequestHandler):

	"""
	Handle incoming phone calls.
	
	"""
	
	def post(self):
		self.response.headers['Content-Type'] = 'text/xml'
		self.response.write(call_response_xml)

# Register URLs for Google App Engine 
application = webapp2.WSGIApplication([ ('/', Index),
										('/respond', Respond),
										('/demo', Demo),
										('/voice', Voice),
										('/sendsms', SendSMS),
									  ],
									  debug=True)
										
