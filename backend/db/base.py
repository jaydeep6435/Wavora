# Import all the models here so that Base has them registered before
# creating metadata or running migrations.
from db.session import Base  # noqa

# Future database models will be imported here:
from models.song import Song  # noqa
from models.album import Album  # noqa
