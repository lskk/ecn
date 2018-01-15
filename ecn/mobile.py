import json
import logging

import pymongo
from datetime import datetime, timedelta

from ecn import StationKind, StationState
from ecn import ecn_mobile_pb2

class MobileHandler:
    logger = logging.getLogger(__name__)

    def __init__(self, db: pymongo.database.Database):
        self.db: pymongo.database.Database = db

    def receive(self, body: bytearray):
        msg: ecn_mobile_pb2.MobileStream = ecn_mobile_pb2.MobileStream()
        msg.ParseFromString(body)
        # self.logger.debug('Station: %s', station_id)
        accel_coll: pymongo.collection.Collection = self.db.accel
        cur_time = datetime.utcfromtimestamp(msg.start_time/1000)
        self.logger.debug('Received %d bytes stream from mobile station %s, start_time=%s, sample_rate=%d Hz',
                          len(body), msg.station_id, cur_time, msg.sample_rate)

        cur_hour = cur_time.strftime('%Y%m%d%H')
        accel_z_buf = {}
        accel_n_buf = {}
        accel_e_buf = {}
        sample_idx = 0 # Pointer to current sample index being processed.
        while sample_idx < len(msg.accel_z):
            accel_z_buf[60 * cur_time.minute + cur_time.second] = msg.accel_z[sample_idx : sample_idx + msg.sample_rate]
            accel_n_buf[60 * cur_time.minute + cur_time.second] = msg.accel_n[sample_idx : sample_idx + msg.sample_rate]
            accel_e_buf[60 * cur_time.minute + cur_time.second] = msg.accel_e[sample_idx : sample_idx + msg.sample_rate]
            sample_idx += msg.sample_rate
            cur_time = cur_time + timedelta(seconds=1)
            next_hour = cur_time.strftime('%Y%m%d%H')
            if next_hour != cur_hour:
                # Flush this hour first
                self.__upsert_data(msg.station_id, cur_hour, msg.sample_rate,
                                   accel_z_buf, accel_n_buf, accel_e_buf)
                accel_z_buf = {}
                accel_n_buf = {}
                accel_e_buf = {}
                cur_hour = next_hour

        # Usually we have some data here, so flush it
        if accel_z_buf:
            self.__upsert_data(msg.station_id, cur_hour, msg.sample_rate,
                               accel_z_buf, accel_n_buf, accel_e_buf)
            accel_z_buf = {}
            accel_n_buf = {}
            accel_e_buf = {}

    def __upsert_data(self, station_id: int, cur_hour: str, sample_rate: int,
                      accel_z_buf: [], accel_n_buf: [], accel_e_buf: []):
        accel_coll: pymongo.collection.Collection = self.db.accel
        accel_id = '%s:%s' % (cur_hour, station_id)
        existing_accel_doc = accel_coll.find_one({'_id': accel_id}, projection={'_id': 1})
        if not existing_accel_doc:
            # "Preallocate" top-level arrays only
            accels = [None for sec in range(60 * 60)]
            accel_coll.insert_one({'_id': accel_id, 'r': sample_rate, 'z': accels, 'n': accels, 'e': accels})

        update_doc = {'$set': {}}
        for second_of_hour, samples in accel_z_buf.items():
            update_doc['$set']['z.%d' % second_of_hour] = samples
        for second_of_hour, samples in accel_n_buf.items():
            update_doc['$set']['n.%d' % second_of_hour] = samples
        for second_of_hour, samples in accel_e_buf.items():
            update_doc['$set']['e.%d' % second_of_hour] = samples
        self.logger.debug('Updating accel %s with %s', accel_id, update_doc['$set'].keys())
        accel_coll.update_one({'_id': accel_id}, update_doc)

        # mark as 'H'igh rate
        station_coll: pymongo.collection.Collection = self.db.station
        station_coll.update_one({'_id': station_id}, {'$set': {'s': StationState.HIGH_RATE, 't': datetime.utcnow()}})
