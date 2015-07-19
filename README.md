# riGallery
riGallery is an open source image gallery designed to be as fast and responsive as possible while preserving as much image quality as possible. 

Existing open source image gallery software is generally extremely simple: users upload images which visitors can then view. There is rarely any server-side image processing, so if your camera is configured to generate 3MB 3264x2448 images, then your users are going to have to download 3MB 3264x2448 images, which is a slow and painful process, even on desktop systems with a good internet connection.

Of course, you could manually scale the images beforehand to something more reasonable, but this is a tricky problem, since reasonable can mean lots of different things, depending on the client device. It's also a tedious process. Skilled users can write a script to automatically scale a large number of images, but average users have no simple solution here.

riGallery solves this problem by scaling the original image to several different resolutions. The client then sends information to the server which can be used to determine which resolution is most appropriate for the client device. 

This approach is better for image gallery administrators, because you don't need to worry about rescaling your images before uploading them to the image gallery. Everything will just work. It's also more futureproof than existing solutions. If you scale all of your images down to a lower resolution, when higher resolution displays come out, visitors will end up looking at a scaled down image. With riGallery, an appropriately sized image will be displayed.

It's better for image gallery viewers too, because images will load much faster at the appropriate resolution for whatever device you're on, whether it's an old cell phone display or a 4K monitor.

## Install
* Install python, virtualenv, and libjpeg-dev if not already installed
* Run setup.sh
* Run flask/bin/alembic upgrade head

## Upgrade
* Run flask/bin/alembic upgrade head

## Deploying with Apache and mod\_wsgi
First, ensure the paths in riGallery.wsgi are correct. 

Next, ensure your VirtualHost entry has the following:
        WSGIDaemonProcess yourapplication user=www-data group=www-data threads=8
        WSGIScriptAlias /gallery /path/to/riGallery/riGallery.wsgi
        WSGIPassAuthorization On

        <Directory /path/to/riGallery>
                WSGIProcessGroup yourapplication
                WSGIApplicationGroup %{GLOBAL}
                Order deny,allow
                Allow from all
        </Directory>

After restarting apache, you should be able to access the gallery by going to "/gallery" (or something else if you'd prefer). For improved security, consider changing the user and group to something other than www-data.

Note that SQLAlchemy requires write access to the database's parent directory.

## Getting Started
* Go to the admin console (default credentials are admin/password, which you should edit via config.py)
* Add an album
* Edit the album
* Add pictures to the album

## Dependencies
riGallery is built upon a number of third party libraries and frameworks, including:
* Flask
* SQL-Alchemy
* Alembic
* PIL
* jquery
* jquery-ui
* Swipebox
* plupload

## Feature Wishlist
* Use the img srcset attribute where supported. Also take css multiplier into account.
* Better authentication scheme that doesn't require https.
* UI needs a huge facelift. Image viewer should have priority over admin console.
* Some kind of analytics - Image X got viewed Y times, breakdown by resolution
* Fix race conditions via an "image visible" attribute
* Ability to reorder images via the admin console
