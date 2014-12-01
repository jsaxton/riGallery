from flask.ext.wtf import Form
from wtforms import HiddenField, SelectField, TextAreaField, TextField, validators
from flask_wtf.file import FileField, FileRequired
from models import Album

class CreateAlbumForm(Form):
    name = TextField(u'Album Name', [validators.DataRequired()])
    description = TextAreaField(u'Album Description')
    id = HiddenField(u'Album ID', default=0)

    def validate(self):
        rv = Form.validate(self)
        if not rv:
            return False

        # Prevent albums with duplicate names
        album = Album.query.filter_by(name=self.name.data).first()
        if album is not None:
            # When editing an album, duplicate album names are expected
            if self.id.data == None or int(self.id.data) != album.id:
                self.name.errors.append('Album name already exists')
                return False

        return True

# When creating an album, there isn't a cover picture ID. When editing an album, there is.
class EditAlbumForm(CreateAlbumForm):
    coverImageId = SelectField(u'Cover Picture ID', coerce=int)

    def __init__(self, *args, **kwargs):
        images = []
        try:
            album = kwargs['obj']
            images = album.images
        except KeyError:
            pass
        Form.__init__(self, *args, **kwargs)
        self.coverImageId.choices = [(image.id, image.id) for image in images]
