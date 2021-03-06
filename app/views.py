import os
import sys
import PIL.Image
import hashlib
from _version import __version__
from datetime import datetime
from app import app, basic_auth, db
from forms import AlbumAuthenticateForm, CreateAlbumForm, EditAlbumForm
from flask import redirect, request, render_template, session, Response, abort, url_for
from werkzeug import secure_filename
from models import Image, ImageInstance, Album
from decorators import async

@app.context_processor
def get_version_string():
    return dict(version_string=__version__)

# TODO: Look into using something like https://github.com/danielgtaylor/jpeg-archive
@async
def createScaledImages(originalFilename, imageId):
    # TODO: This can trigger an exception
    orig = PIL.Image.open(os.path.join(app.config['UPLOADED_IMAGES_DEST'], originalFilename))
    origWidth, origHeight = orig.size
    if origHeight == 0 or origWidth == 0:
        app.logger.warning("Uploaded image %d has invalid dimensions %d x %d", imageId, origWidth, origHeight)
        image = Image.query.get(imageId)
        db.session.delete(image)
        db.session.commit()
        return
    # Store original image
    # Apparently wtforms doesn't expose the mime type?
    # TODO: Does PIL expose the MIME type?
    imageInstance = ImageInstance(verticalResolution=origHeight, horizontalResolution=origWidth, mimeType="image/jpeg", imageId=imageId, isOriginal=True)
    db.session.add(imageInstance)
    aspectRatio = origWidth / float(origHeight)
    verticalResolutions = app.config['VERTICAL_RESOLUTIONS'][:]
    saveDirs = [ os.path.join(app.config['IMAGE_ROOT_DIR'], str(res)) for res in app.config['VERTICAL_RESOLUTIONS'] ]
    verticalResolutions.insert(0, app.config['THUMBNAIL_HEIGHT'])
    saveDirs.insert(0, app.config['THUMBNAIL_DIR'])

    for i in range(len(verticalResolutions)):
        vRes = verticalResolutions[i]
        saveDir = saveDirs[i]

        # Don't upscale
        if vRes >= origHeight:
            continue

        scaledHeight = vRes
        scaledWidth = int(vRes * aspectRatio)
        # TODO: Maybe do this as part of the constructor?
        if not os.path.isdir(saveDir):
            os.makedirs(saveDir)
        out = file(os.path.join(saveDir, originalFilename), "w")

        # The goal is to create the highest quality images possible, even if
        # that is computationally expensive. There seems to be a consensus that
        # the Lanczos filter is the best algorithm to use when downscaling
        # images. The ANTIALIAS constant is left for backwards compatibility
        # and is an alias for LANCZOS.
        scaled = orig.resize( (scaledWidth, scaledHeight), PIL.Image.ANTIALIAS)

        try:
            # TODO: Use same image format as original?
            scaled.save(out, "JPEG")
            imageInstance = ImageInstance(verticalResolution=scaledHeight, horizontalResolution=scaledWidth, mimeType="image/jpeg", imageId=imageId, isOriginal=False)
            db.session.add(imageInstance)
        except:
            app.logger.warning("Failed to save %s [%s]", out, sys.exc_info()[0])
        finally:
            out.close()

    db.session.commit()

def deleteImageFiles(id):
    imageInstances = ImageInstance.query.filter_by(imageId=id)
    for image in imageInstances:
        try:
            os.unlink(image.getPath())
        except:
            app.logger.warning("Failed to delete %s [%s]", image.getPath(), sys.exc_info()[0])

def getAlbumPasswordHash(creationDate, password):
    # Could just use unicode(creationDate), but in the unlikely event there are
    # any changes to how that is represented, the salt completely breaks
    dateStr = creationDate.strftime("%Y-%m-%d %H:%M:%S")
    return hashlib.sha256(dateStr + password).hexdigest()

def normalizeImageOrder(albumId):
    images = Image.query.filter_by(albumId=albumId).order_by(Image.imageOrder)
    i = 1
    for image in images:
        image.imageOrder = i
        i += 1
        db.session.add(image)

@app.route('/')
@app.route('/index')
def index():
    albums = Album.query.all()
    return render_template('index.html', albums=albums)

@app.route('/admin')
@basic_auth.required
def admin(createAlbumForm=None):
    albums = Album.query.order_by("id asc")
    # Can't set default values in function declaration - causes "RuntimeError: working outside of application context"
    if createAlbumForm == None:
        createAlbumForm = CreateAlbumForm(prefix="createAlbum")
    return render_template('admin.html', createAlbumForm=createAlbumForm, albums=albums)

@app.route('/albums', methods=['POST'])
@basic_auth.required
def createAlbum():
    form = CreateAlbumForm(prefix="createAlbum")
    if form.validate_on_submit():
        album = Album(name=form.name.data, 
                      description=form.description.data, 
                      creationDate=datetime.utcnow(), 
                      numImages=0, 
                      coverImageId=0)
        if form.passwordProtected.data and form.passwordHash.data:
            album.passwordHash = getAlbumPasswordHash(album.creationDate, form.passwordHash.data)
        db.session.add(album)
        db.session.commit()
    return admin(createAlbumForm=form)

@app.route('/deletePicture', methods=['POST']) # Can't use /deletePicture/id because id is unknown when we call url_for()
@basic_auth.required
def deletePicture(id=0):
    id=request.form.get('id', 0, type=int)
    image = Image.query.filter_by(id=id).first()
    if image == None:
        app.logger.warning("Image %d doesn't exist", int(id))
        abort(404)

    deleteImageFiles(id)

    # Delete Image (the cascade will delete the ImageInstances)
    albumId = image.albumId
    db.session.delete(image)

    # Update album
    album = Album.query.filter_by(id=albumId).first()
    if album != None:
        album.numImages = album.images.count()

        # Update cover image if necessary
        if album.coverImageId == id:
            album.coverImageId = None
            if album.numImages > 0:
                album.coverImageId = album.images.first().id

    # Ensure images are monotonically increasing
    normalizeImageOrder(image.albumId)

    db.session.commit()
    return ""

@app.route('/updatePictureDescription/<int(min=1):id>', methods=['POST'])
@basic_auth.required
def updatePictureDescription(id):
    image = Image.query.filter_by(id=id).first()
    if image == None:
        app.logger.warning("Image %d doesn't exist", int(id))
        abort(404)
    image.description = request.form.get('description', '', type=str)
    db.session.commit()
    return ""

@app.route('/updateOrder/<int(min=1):id>', methods=['POST'])
@basic_auth.required
def updateOrder(id):
    image = Image.query.filter_by(id=id).first()
    if image == None:
        app.logger.warning("Image %d doesn't exist", int(id))
        abort(404)
    # TODO: Sanity check inputs
    image.imageOrder = request.form.get('order', '', type=int)
    db.session.commit()
    return ""

@app.route('/editAlbum/<int(min=1):id>', methods=['POST', 'GET'])
@basic_auth.required
def editAlbum(id):
    album = Album.query.filter_by(id=id).first()
    if album is None:
        abort(404)

    # Initialize password protected checkbox
    passwordProtected = False
    if album.passwordHash:
        passwordProtected = True

    form = EditAlbumForm(obj=album, prefix="album", passwordProtected=passwordProtected)
    form.coverImageId.choices = [(image.id, image.id) for image in album.images]
    if form.validate_on_submit():
        album.name = form.name.data
        album.description = form.description.data
        album.coverImageId = form.coverImageId.data
        album.numImages = album.images.count()
        if form.passwordProtected.data and form.passwordHash.data:
            album.passwordHash = getAlbumPasswordHash(album.creationDate, form.passwordHash.data)
        else:
            album.passwordHash = None
        db.session.commit()
    return render_template('editAlbum.html', editAlbumForm=form, album=album, maxUploadMb=app.config['MAX_CONTENT_LENGTH_MB'])

# TODO: Fix tiny race condition that probably doesn't actually matter
@app.route('/deleteAlbum/<int(min=1):id>', methods=['POST'])
@basic_auth.required
def deleteAlbum(id):
    album = Album.query.filter_by(id=id).first()
    if album == None:
        abort(404)
    for image in album.images:
        deleteImageFiles(image.id)
    db.session.delete(album)
    db.session.commit()
    return admin()

# TODO: Come up with something better. It's still trivial to break this - just GET all the pictures from 1..$maxPictureId.
@app.route('/albumAuthenticate/<int(min=1):id>', methods=['POST'])
def albumAuthenticate(id):
    album = Album.query.filter_by(id=id).first()
    if album == None:
        abort(404)
    if "viewAlbum" + str(id) not in session:
        form = AlbumAuthenticateForm()
        if form.validate_on_submit():
            if getAlbumPasswordHash(album.creationDate, form.password.data) == album.passwordHash:
                session["viewAlbum" + str(id)] = True
    return redirect(url_for("viewAlbum", id=id))

@app.route('/viewAlbum/<int(min=1):id>', methods=['GET', 'POST'])
def viewAlbum(id):
    album = Album.query.filter_by(id=id).first()
    if album == None:
        abort(404)
    if album.passwordHash:
        authenticated = "viewAlbum" + str(id) in session
        if not authenticated:
            return render_template('albumAuthenticate.html', album=album, albumAuthenticateForm=AlbumAuthenticateForm())
    # TODO: order images
    return render_template('viewAlbum.html', album=album)

# TODO: Do a better job of telling the user the upload failed
@app.route('/uploadPicture/<int(min=1):albumId>', methods=['POST'])
@basic_auth.required
def uploadPicture(albumId):
    successfulUpload = False
    album = Album.query.filter_by(id=albumId).first()
    if "file" not in request.files or album == None:
        abort(404)
    filename = secure_filename(request.files["file"].filename)
    filename = Image.make_unique_filename(filename)
    image = Image(originalFilename = filename, uploadDate = datetime.utcnow(), albumId=albumId, imageOrder=(album.numImages+1))

    # Ensure upload directory exists, write file
    try:
        if not os.path.isdir(app.config['UPLOADED_IMAGES_DEST']):
            os.makedirs(app.config['UPLOADED_IMAGES_DEST'])
        savePath = os.path.join(app.config['UPLOADED_IMAGES_DEST'], filename)
        request.files["file"].save(savePath)
    except:
        app.logger.error("Failed to save uploaded image to %s [%s]", savePath, sys.exc_info()[0])
        abort(404)

    # Verify PIL can open the image
    try:
        PIL.Image.open(os.path.join(app.config['UPLOADED_IMAGES_DEST'], filename)) # TODO: memory is faster than disk
        successfulUpload = True
    except:
        os.unlink(os.path.join(app.config['UPLOADED_IMAGES_DEST'], filename))
        abort(404)
    if successfulUpload:
        db.session.add(image)
        db.session.flush()
        db.session.commit()
        createScaledImages(image.originalFilename, image.id)

        # Update album
        album.numImages = album.images.count()
        if album.coverImageId == 0:
            album.coverImageId = image.id
        db.session.add(album)
        db.session.commit()
    else:
        abort(404)
    return ""

@app.route('/picture/<int(min=1):id>')
@app.route('/picture/<int(min=1):id>/<int:clientWidth>/<int:clientHeight>')
def picture(id, clientWidth=0, clientHeight=0):
    images = ImageInstance.query.filter_by(imageId=id).order_by('verticalResolution desc')
    if images.first() == None:
        app.logger.warning("Image %d doesn't exist", int(id))
        abort(404)

    # If no height is provided, return the original
    if clientHeight <= 0 or clientWidth <= 0:
        imageInstance = images.filter_by(isOriginal=True).first()
        image = open(imageInstance.getPath())
        return Response(image.read(), mimetype="image/jpeg")

    retImage = images.first()
    imageAspectRatio = float(retImage.horizontalResolution) / float(retImage.verticalResolution)
    if clientHeight > clientWidth and imageAspectRatio < 1:
        # Assume user can rotate device
        temp = clientHeight
        clientHeight = clientWidth
        clientWidth = clientHeight
    clientAspectRatio = float(clientWidth) / float(clientHeight)

    if imageAspectRatio > clientAspectRatio:
        # Letterbox case, constrained by clientWidth
        for image in images:
            if clientWidth < image.horizontalResolution*1.1:
                retImage = image
    else:
        # Pillarbox case, constrained by clientHeight
        for image in images:
            if clientHeight < image.verticalResolution*1.1:
                retImage = image

    try:
        image = open(retImage.getPath())
        return Response(image.read(), mimetype="image/jpeg")
    except:
        app.logger.warning("Failed to open %s [%s]", retImage.getPath(), sys.exc_info()[0])
        abort(404)

@app.route('/thumbnail/<int(min=1):id>')
def thumbnail(id):
    image = Image.query.filter_by(id=id).first()
    if image == None:
        abort(404)
    try:
        thumbnail = open(image.getThumbPath())
        return Response(thumbnail.read(), mimetype="image/jpeg")
    except:
        app.logger.warning("Failed to open %s [%s]", image.getThumbPath(), sys.exc_info()[0])
        abort(404)
