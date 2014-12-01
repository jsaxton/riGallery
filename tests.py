#!flask/bin/python
import os
import unittest
import hashlib
import shutil

from config import basedir
from app import app, db
from StringIO import StringIO
from time import sleep
from PIL import Image

testDbPath = os.path.join(basedir, 'test.db')

class TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + testDbPath
        app.config['IMAGE_ROOT_DIR'] = os.path.join(basedir, "test_uploads")
        app.config['UPLOADED_IMAGES_DEST'] = os.path.join(app.config['IMAGE_ROOT_DIR'], "uploads")
        app.config['THUMBNAIL_DIR'] = os.path.join(app.config['IMAGE_ROOT_DIR'], "thumbs")
        if os.path.isdir(app.config['UPLOADED_IMAGES_DEST']):
            shutil.rmtree(app.config['UPLOADED_IMAGES_DEST'])
        if os.path.isdir(app.config['THUMBNAIL_DIR']):
            shutil.rmtree(app.config['THUMBNAIL_DIR'])
        if os.path.isdir(testDbPath):
            os.unlink(testDbPath)
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        shutil.rmtree(app.config['UPLOADED_IMAGES_DEST'])
        shutil.rmtree(app.config['THUMBNAIL_DIR'])
        shutil.rmtree(app.config['IMAGE_ROOT_DIR'])
        db.session.remove()
        db.drop_all()
        os.unlink(os.path.join(basedir, testDbPath))

    def test_upload(self):
        # First create an album
        rv = self.app.post('/albums', data={
            "name": "Test album",
            "description": "Test description"
            }, follow_redirects=True)
        assert rv.status_code == 200
        sleep(.5)
        origPath = os.path.join("test_content", "picture1.jpg")
        imagePath = os.path.join(app.config['UPLOADED_IMAGES_DEST'], "picture1.jpg")
        thumbPath = os.path.join(app.config['THUMBNAIL_DIR'], "picture1.jpg")
        imageData = open(origPath);
        rv = self.app.post('/uploadPicture/1', data= {
            "upload-photo": (StringIO(imageData.read()), "picture1.jpg"),
            "upload-description": "Test Description"
            }, follow_redirects=True);
        assert rv.status_code == 200
        sleep(2) # Thumbnail generation is asynchronous
        # TODO: Don't assume this is picture 1, test order not guaranteed
        rv = self.app.get('/picture/1', follow_redirects=True)
        assert rv.status_code == 200
        rv = self.app.get('/thumbnail/1', follow_redirects=True)
        assert rv.status_code == 200
        assert os.path.isfile(imagePath)
        assert os.path.isfile(thumbPath)
        assert hashlib.md5(open(origPath, 'rb').read()).hexdigest() == hashlib.md5(open(imagePath, 'rb').read()).hexdigest()
        im = Image.open(thumbPath)
        thumbWidth, thumbHeight = im.size
        assert thumbWidth == 150
        assert thumbHeight == 200

        imageData.close()
        imageData = open(origPath);

        # Test a duplicate upload (test order is not guaranteed, so this has to be part of the first test
        self.app.post('/uploadPicture/1', data= {
            "upload-photo": (StringIO(imageData.read()), "picture1.jpg"),
            "upload-description": "Test Description"
            }, follow_redirects=True);
        sleep(2) # Thumbnail generation is asynchronous
        rv = self.app.get('/picture/2', follow_redirects=True)
        assert rv.status_code == 200
        rv = self.app.get('/thumbnail/2', follow_redirects=True)
        assert rv.status_code == 200
        # Make sure we didn't clobber the original image
        assert len([name for name in os.listdir(app.config['UPLOADED_IMAGES_DEST']) if os.path.isfile(os.path.join(app.config['UPLOADED_IMAGES_DEST'], name))]) == 2
        # Make sure we didn't clobber the original thumbnail
        assert len([name for name in os.listdir(app.config['THUMBNAIL_DIR']) if os.path.isfile(os.path.join(app.config['THUMBNAIL_DIR'], name))]) == 2
        sleep(1) # Sleep until background thread finishes scaling images

if __name__ == '__main__':
    unittest.main()
