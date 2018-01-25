# Save queue using ad-hoc format due to app server outrage during earthquake
import logging
import os
import json
import pymongo
from datetime import datetime
from pymongo import MongoClient

from ecn.amqp import AmqpProcessor


class AdhocStationaryV1Handler:
    logger = logging.getLogger(__name__)
    SAMPLE_RATE = 40

    def __init__(self, db: pymongo.database.Database):
        self.db: pymongo.database.Database = db
        self.adhoc_count = 0

    def receive(self, body: bytearray):
        self.adhoc_count = self.adhoc_count + 1
        adhoc_id = self.adhoc_count
        body = body.replace(b'nan,', b'null,') # Workaround for ECNv1 bug
        # logger.debug('Decoding %s', body)
        msg = json.loads(body)
        msg['_id'] = adhoc_id
        msg['tf'] = datetime.utcnow()
        client_id = msg['clientID']
        if client_id != 'ECN-4':
            self.logger.info('Skipping %s', client_id)
            return
        adhoc_coll: pymongo.collection.Collection = self.db.adhoc
        self.logger.debug('Adhoc: %s - %s', adhoc_id, msg['tf'])
        adhoc_coll.insert_one(msg)

MONGODB_URI = 'mongodb://localhost/ecn' # os.environ['MONGODB_URI']
AMQP_HOST = os.environ['AMQP_HOST']
AMQP_VHOST = os.environ['AMQP_VHOST']
AMQP_USER = os.environ['AMQP_USER']
AMQP_PASSWORD = os.environ['AMQP_PASSWORD']

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.info('Connecting to MongoDB...')
mongo = MongoClient(MONGODB_URI)
db = mongo.ecn

processor = AmqpProcessor()
processor.stationary_v1_handler = AdhocStationaryV1Handler(db)
processor.connect(AMQP_HOST, AMQP_VHOST, AMQP_USER, AMQP_PASSWORD)
processor.run()