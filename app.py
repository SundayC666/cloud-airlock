import json
import os
import logging
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

# Initialize Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 1. Initialize Slack App
# It automatically reads environment variables: SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET
app = App(process_before_response=True)

# 2. Handle Slack's "Challenge" (URL Verification)
# When you configure the URL in Slack API settings, Slack sends this request to verify ownership.
@app.event("url_verification")
def handle_challenge(body, logger):
    return body["challenge"]

# 3. Handle the "/scan" command
@app.command("/scan")
def handle_scan_command(ack, body, respond):
    # A. Acknowledge the command within 3 seconds to prevent Slack timeout errors
    ack()
    
    user_id = body["user_id"]
    text = body["text"]  # The URL input by the user
    
    # B. Send an immediate response indicating the scan has started
    respond(f"🚨 Mission received! Scanning target: {text} \nPlease wait, AI analyst is investigating... 🕵️‍♂️")

    # TODO: We will add the actual scanning logic here in the next step
    # Currently just testing connectivity

# 4. AWS Lambda Entry Point (Handler)
def lambda_handler(event, context):
    # Adapt Slack Bolt to handle AWS Lambda events
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)