# basic-textbot
a textbot that tells you things, asks for a response, and checks the response

To get this set up and working as a textbot, you'll need to use two services:
GoogleAppEngine and Twilio.

Getting Started
===
There are four important files for this app:
- app.yaml, which defines the files for this app
- queue.yaml, which defines the task queue for this app
- bot.py, which contains the interface for the bot
- text.py, which contains the actual text the bot says


Step by step instructions
===
- make a Twilio account
  it needs to be a paid account to interact with the html stuff Google App Engine is going to make
  edit bot.py to use your account's phone number, account sid, and auth token
- make a Google App Engine account

- add Twilio's python library to this directory
  see GoogleAppEngine's instructions TODO
  but warning: they are missing a step! you also need to 
    ln pytz
- test it with GoogleAppEngineLauncher
  debug with the log console

- make a project for the app in Google Developer's Console
  this gives a project id
- edit the project id in app.yaml to use this project id
  application: project-id
- upload the application using
  cd .. (go up a directory level)
  appcfg.py update dirOfProject

- configure phone number on Twilio so SMS URL point to the GoogleAppEngine URL
  http://project-id.appspot.com/respond

