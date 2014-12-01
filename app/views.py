import os
import sys
import PIL.Image
from datetime import datetime
from app import app, basic_auth, db
from forms import CreateAlbumForm, EditAlbumForm
from flask import request, render_template, Response, abort, flash
from werkzeug import secure_filename
from models import Image, ImageInstance, Album
from decorators import async

# TODO: Look into using something like https://github.com/danielgtaylor/jpeg-archive
@async
def createScaledImages(originalFilename, imageId):
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

        # TODO: All things equal faster compression is nice, but optimizing for better image compression should be the ultimate goal.
        # If there is enough downscaling, use a two pass algorithm to downsize the image
        # Pass 1: Using a nearest neighbor algorithm, create an intermediate image that is twice the size of the final thumbnail
        # Pass 2: Using the ANTIALIAS algorithm, create the final thumbnail
        # Some guy's blog said that this provided a good tradeoff between speed and quality, and it sounds reasonable, so I'm going to go with it
        if 3*scaledWidth < origWidth:
            scaled = orig.resize( (2*scaledWidth, 2*scaledHeight), PIL.Image.NEAREST ).resize( (scaledWidth, scaledHeight), PIL.Image.ANTIALIAS)
        else:
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
        album = Album(name=form.name.data, description=form.description.data, creationDate=datetime.utcnow(), numImages=0, coverImageId=0)
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

    # Delete Image (the cascade will delete the ImageInstances)
    albumId = image.albumId
    db.session.delete(image)

    # Update album
    album = Album.query.filter_by(id=albumId).first()
    if album != None:
        album.numImages = album.images.count()

    # TODO: Delete images from disk

    # TODO: Update album cover image if necessary

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

@app.route('/editAlbum/<int(min=1):id>', methods=['POST', 'GET'])
@basic_auth.required
def editAlbum(id):
    album = Album.query.filter_by(id=id).first()
    if album is None:
        abort(404)
    form = EditAlbumForm(obj=album, prefix="album")
    form.coverImageId.choices = [(image.id, image.id) for image in album.images]
    if form.validate_on_submit():
        album.name = form.name.data
        album.description = form.description.data
        album.coverImageId = form.coverImageId.data
        album.numImages = album.images.count()
        db.session.commit()
    return render_template('editAlbum.html', editAlbumForm=form, album=album, maxUploadMb=app.config['MAX_CONTENT_LENGTH_MB'])

@app.route('/deleteAlbum/<int(min=1):id>', methods=['POST'])
@basic_auth.required
def deleteAlbum(id):
    album = Album.query.filter_by(id=id).first()
    if album == None:
        abort(404)
    db.session.delete(album)
    # TODO: Delete images
    db.session.commit()
    return admin()

@app.route('/viewAlbum/<int(min=1):id>', methods=['GET'])
def viewAlbum(id):
    album = Album.query.filter_by(id=id).first()
    if album == None:
        abort(404)
    # TODO: order images
    return render_template('viewAlbum.html', album=album)

# TODO: Do a better job of telling the user the upload failed
@app.route('/uploadPicture/<int(min=1):albumId>', methods=['POST'])
@basic_auth.required
def uploadPicture(albumId):
    successfulUpload = False
    album = Album.query.filter_by(id=albumId).first()
    print "Test 1"
    print request.files["file"]
    if "file" not in request.files or album == None:
        abort(404)
    filename = secure_filename(request.files["file"].filename)
    filename = Image.make_unique_filename(filename)
    image = Image(originalFilename = filename, uploadDate = datetime.utcnow(), albumId=albumId)

    print "Test 2"
    # Ensure upload directory exists, write file
    try:
        if not os.path.isdir(app.config['UPLOADED_IMAGES_DEST']):
            os.makedirs(app.config['UPLOADED_IMAGES_DEST'])
        print app.config['UPLOADED_IMAGES_DEST']
        savePath = os.path.join(app.config['UPLOADED_IMAGES_DEST'], filename)
        print savePath
        request.files["file"].save(savePath)
    except:
        app.logger.error("Failed to save uploaded image to %s [%s]", savePath, sys.exc_info()[0])
        abort(404)

    # Verify PIL can open the image
    print "Test 3"
    try:
        PIL.Image.open(os.path.join(app.config['UPLOADED_IMAGES_DEST'], filename)) # TODO: memory is faster than disk
        successfulUpload = True
    except:
        flash("Not a valid image")
        os.unlink(os.path.join(app.config['UPLOADED_IMAGES_DEST'], filename))
        abort(404)
    print "Test 4"
    if successfulUpload:
        db.session.add(image)
        db.session.flush()
        db.session.commit()
        flash("Successfully uploaded image") # TODO: flash doesn't make sense anymore
        createScaledImages(image.originalFilename, image.id)
    else:
        flash("Failed to upload image") # TODO: flash doesn't make sense anymore

    # Update album
    album.numImages = album.images.count()
    if album.coverImageId == 0:
        album.coverImageId = image.id
    db.session.add(album)
    db.session.commit()
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

    # TODO: What about images in portrait mode? Probably want something more intelligent here
    if clientHeight > clientWidth:
        # Assume user can rotate device
        temp = clientHeight
        clientHeight = clientWidth
        clientWidth = clientHeight
    clientAspectRatio = float(clientWidth) / float(clientHeight)
    retImage = images.first()
    imageAspectRatio = float(retImage.horizontalResolution) / float(retImage.verticalResolution)

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
