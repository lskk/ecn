import json
import logging

import pymongo
from datetime import datetime, timedelta

from ecn import StationKind
from ecn import ecn_mobile_pb2

class MobileHandler:
    logger = logging.getLogger(__name__)

    def __init__(self, db: pymongo.database.Database):
        self.db: pymongo.database.Database = db

    def receive(self, body: bytearray):
        msg: ecn_mobile_pb2.MobileStream = ecn_mobile_pb2.MobileStream()
        msg.ParseFromString(body)
        msg.station_id
        # self.logger.debug('Station: %s', station_id)
        accel_coll: pymongo.collection.Collection = self.db.accel
        self.logger.debug('Station: %s - Stream: %s', msg.station_id, msg)
