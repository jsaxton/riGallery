import os

CSRF_ENABLED = True
SECRET_KEY = 'this-seems-like-a-bad-idea'

basedir = os.path.abspath(os.path.dirname(__file__))
# Where are uploaded images stored?
IMAGE_ROOT_DIR = basedir
UPLOADED_IMAGES_DEST = os.path.join(IMAGE_ROOT_DIR, "uploads")
THUMBNAIL_DIR = os.path.join(IMAGE_ROOT_DIR, "thumbs")

# Thumbnails are a fixed height, vary the width to preserve the aspect ratio
THUMBNAIL_HEIGHT = 200

# Supported vertical resolutions (in addition to the original image)
VERTICAL_RESOLUTIONS = [480, 720, 1080]

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

# Username and password needed to access admin console
BASIC_AUTH_USERNAME = 'admin'
BASIC_AUTH_PASSWORD = 'password'

MAX_CONTENT_LENGTH_MB = 20
MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024
