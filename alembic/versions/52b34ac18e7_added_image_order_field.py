"""Added image order field

Revision ID: 52b34ac18e7
Revises: 4f3f55688877
Create Date: 2015-07-19 21:14:27.551788

"""

# revision identifiers, used by Alembic.
revision = '52b34ac18e7'
down_revision = '4f3f55688877'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, Session as BaseSession, relationship

# Import the model
import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '..', '..'))
from app import models

Session = sessionmaker()

def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    op.add_column('image', sa.Column('imageOrder', sa.Integer(), nullable=False, server_default="0"))

    # Ensure the image order new image order column is initialized for all images
    image_order_map = {}
    for album in session.query(models.Album):
        image_order_map[album.id] = 1

    for image in session.query(models.Image):
        image.imageOrder = image_order_map[image.albumId]
        image_order_map[image.albumId] += 1

    session.commit()

def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('image', 'imageOrder')
    ### end Alembic commands ###
