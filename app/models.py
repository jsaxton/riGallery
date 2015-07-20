import os
from app import app, db

class Image(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    originalFilename = db.Column(db.String(150))
    uploadDate = db.Column(db.DateTime)
    description = db.Column(db.Text)
    albumId = db.Column(db.Integer, db.ForeignKey('album.id'))
    scaledImages = db.relationship('ImageInstance', backref=db.backref('image'), cascade="all, delete")
    imageOrder = db.Column(db.Integer)

    # TODO: Is it worthwhile to come up with a better way of doing this? Seems
    # like a potential DOS attack vector? Not sure if the ORM is smart enough
    # to cache the query results.
    @staticmethod
    def make_unique_filename(filename):
        if Image.query.filter_by(originalFilename=filename).first() is None:
            return filename
        base, ext = os.path.splitext(filename)
        version = 0
        while True:
            filename = base + str(version) + ext
            if Image.query.filter_by(originalFilename=filename).first() is None:
                break
            version += 1
        return filename

    def getThumbPath(self):
        return os.path.join(app.config['THUMBNAIL_DIR'], self.originalFilename)

    def __repr__(self):
        return "<Image %r>" % self.originalFilename

class ImageInstance(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    verticalResolution = db.Column(db.Integer)
    horizontalResolution = db.Column(db.Integer)
    mimeType = db.Column(db.String(20))
    isOriginal = db.Column(db.Boolean)
    imageId = db.Column(db.Integer, db.ForeignKey('image.id', ondelete='CASCADE'))

    # Returns the path to the image on disk
    def getPath(self):
        if self.isOriginal:
            return os.path.join(app.config['UPLOADED_IMAGES_DEST'], self.image.originalFilename)
        if self.verticalResolution == app.config['THUMBNAIL_HEIGHT']:
            return os.path.join(app.config['THUMBNAIL_DIR'], self.image.originalFilename)
        else:
            return os.path.join(app.config['IMAGE_ROOT_DIR'], str(self.verticalResolution), self.image.originalFilename)

    def __repr__(self):
        return "<ImageInstance %r (%r x %r)>" % (self.imageId, self.horizontalResolution, self.verticalResolution)

class Album(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(150))
    description = db.Column(db.Text)
    creationDate = db.Column(db.DateTime)
    images = db.relationship('Image', backref='album', lazy='dynamic', cascade="all, delete")
    coverImageId = db.Column(db.Integer) # TODO: Get foreign key working
    numImages = db.Column(db.Integer)
    passwordHash = db.Column(db.String(128)) # TODO: right length

    def __repr__(self):
        return "<Album %r>" % self.id
