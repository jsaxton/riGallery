from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.basicauth import BasicAuth

app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)
basic_auth = BasicAuth(app)
from app import views, models

