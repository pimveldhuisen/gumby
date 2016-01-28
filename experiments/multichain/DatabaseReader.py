import os
from os import path
import base64

from Tribler.community.multichain.database import MultiChainDB
from Tribler.community.multichain.payload import EMPTY_HASH
from Tribler.community.multichain.community import GENESIS_ID
from Tribler.community.multichain.conversion import PK_LENGTH

EMPTY_HASH_ENCODED = base64.encodestring(EMPTY_HASH)
GENESIS_ID_ENCODED = base64.encodestring(GENESIS_ID)


class MultiChainExperimentAnalysisDatabase(MultiChainDB):
    """
    Extended MultiChainDB that provides additional functionality to analyze an experiment.
    """

    def __init__(self, dispersy, working_directory):
        super(MultiChainExperimentAnalysisDatabase, self).__init__(dispersy, working_directory)

    def get_totals(self, mid):
        """
        Return the totals in order by sequence number for mid.
        """
        mid = buffer(mid)
        db_query = u"SELECT total_up, total_down FROM(" \
                   u"SELECT total_up_responder as total_up, total_down_responder as total_down, sequence_number_responder " \
                   u"as sequence_number FROM multi_chain WHERE mid_responder == ? AND sequence_number_responder != -1 "\
                   u"UNION " \
                   u"SELECT total_up_requester as total_up, total_down_requester " \
                   u"as total_down, sequence_number_requester as sequence_number FROM multi_chain WHERE mid_requester =?) " \
                   u"ORDER BY sequence_number"
        db_result = self.execute(db_query, (mid, mid)).fetchall()
        return db_result


class DatabaseReader(object):

    def __init__(self, working_directory):
        """
        Parent class that contains functionality for both gumby and single database readers.
        DatabaseReaders process experimentation information.
        """
        """ Either contains all information all ready or all information will be aggregated here."""
        self.working_directory = working_directory
        self.database = self.get_database(self.working_directory)
        """ Mids are retrieved during generate_graph and used in generate_totals"""
        self.mids = set([])

        self.combine_databases()
        self.generate_block_file()
        self.generate_totals()
        return

    def get_database(self, db_path):
        raise NotImplementedError("Abstract method")

    def combine_databases(self):
        """
        Combines the databases from the different nodes into one local database
        """
        raise NotImplementedError("Abstract method")

    def generate_graph(self):
        """
        Generates a png file of the graph.
        """
        raise NotImplementedError("Abstract method")

    def generate_block_file(self):
        print "Writing multichain to file"
        with open(os.path.join(self.working_directory, "multichain.dat"), 'w') as multichain_file:
            # Write header
            multichain_file.write(
                "Block_ID " +
                "Up " +
                "Down " +
                "Public_Key_Requester " +
                "Total_Up_Requester " +
                "Total_Down_Requester " +
                "Sequence_Number_Requester " +
                "Previous_Hash_Requester " +
                "Public_Key_Responder " +
                "Total_Up_Responder " +
                "Total_Down_Responder " +
                "Sequence_Number_Responder " +
                "Previous_Hash_Responder" +
                "\n"
            )
            # Write blocks
            ids = self.database.get_ids()
            for block_id in ids:
                block = self.database.get_by_block_id(block_id)
                multichain_file.write(
                    base64.encodestring(block_id).replace('\n', '').replace('\r', '') + " " +
                    str(block.up) + " " +
                    str(block.down)+" " +
                    base64.encodestring(block.public_key_requester).replace('\n', '').replace('\r', '') + " " +
                    str(block.total_up_requester)+ " " +
                    str(block.total_down_requester)+ " " +
                    str(block.sequence_number_requester)+ " " +
                    base64.encodestring(block.previous_hash_requester).replace('\n', '').replace('\r', '') + " " +
                    base64.encodestring(block.public_key_responder).replace('\n', '').replace('\r', '') + " " +
                    str(block.total_up_responder) + " " +
                    str(block.total_down_responder) + " " +
                    str(block.sequence_number_responder) + " " +
                    base64.encodestring(block.previous_hash_responder).replace('\n', '').replace('\r', '') +
                    "\n"
                )

    def generate_totals(self):
        """
        Generates a file containing all totals in a R format.
        """
        print("Reading totals")
        mid_data = dict.fromkeys(self.mids)
        length = 0
        for mid in self.mids:
            totals = self.database.get_totals(mid)
            total_ups, total_downs = zip(*totals)
            mid_data[mid] = (total_ups, total_downs)
            if len(total_ups) > length:
                length = len(total_ups)
            if len(total_downs) > length:
                length = len(total_downs)
        print("Writing data totals to file")
        """ Write to file """
        with open(os.path.join(self.working_directory, "mids_data_up.dat"), 'w') as up_file:
            with open(os.path.join(self.working_directory, "mids_data_down.dat"), 'w') as down_file:
                for mid in self.mids:
                    total_ups = mid_data[mid][0]
                    total_downs = mid_data[mid][1]
                    for i in range(0, length):
                        if i < len(total_ups):
                            up_file.write(str(total_ups[i]))
                            down_file.write(str(total_downs[i]))
                        else:
                            up_file.write("na")
                            down_file.write("na")
                        # Write character separator.
                        if i != length - 1:
                            up_file.write("\t")
                            down_file.write("\t")
                    up_file.write("\n")
                    down_file.write("\n")

    class MockDispersy:

        class MockMember:

            def __init__(self, mid):
                # Return the mid with 0 appended so that the pk has the same length.
                # The real pk cannot be retrieved.
                self.public_key = mid + '0'*(PK_LENGTH - len(mid))

        def __init__(self):
            return

        def get_member(self, mid=''):
            return self.MockMember(mid)


class SingleDatabaseReader(DatabaseReader):

    def __init__(self, working_directory):
        super(SingleDatabaseReader, self).__init__(working_directory)

    def get_database(self, db_path):
        return MultiChainExperimentAnalysisDatabase(self.MockDispersy(), os.path.join(db_path, "multichain/1/"))


class GumbyIntegratedDatabaseReader(DatabaseReader):

    def __init__(self, working_directory):
        super(GumbyIntegratedDatabaseReader, self).__init__(working_directory)

    def combine_databases(self):
        print "Reading databases."
        databases = []
        for dir_name in os.listdir(self.working_directory):
            # Read all nodes
            if 'Tribler' in dir_name:
                databases.append(MultiChainDB(self.MockDispersy(), path.join(self.working_directory, dir_name)))
        for database in databases:
            ids = database.get_ids()
            for block_id in ids:
                block = database.get_by_block_id(block_id)
                # Fix the block. The hash is different because the Public Key is not accessible.
                block.id = block_id
                if not self.database.contains(block.id):
                    self.database.add_block(block)
        total_blocks = len(self.database.get_ids())
        print "Found " + str(total_blocks) + " unique multichain blocks across databases"



    def get_database(self, db_path):
        return MultiChainExperimentAnalysisDatabase(self.MockDispersy(), db_path)


class GumbyStandaloneDatabaseReader(DatabaseReader):

    def __init__(self, working_directory):
        super(GumbyStandaloneDatabaseReader, self).__init__(working_directory)

    def get_database(self, db_path):
        return MultiChainExperimentAnalysisDatabase(self.MockDispersy(), db_path)

    def combine_databases(self):
        print "Reading databases."
        databases = []
        for dir_name in os.listdir(self.working_directory):
            # Read all nodes
          #  if 'Tribler' in dir_name:
            if dir_name.isdigit():
                databases.append(MultiChainDB(self.MockDispersy(), path.join(self.working_directory, dir_name)))
        for database in databases:
            ids = database.get_ids()
            for block_id in ids:
                block = database.get_by_block_id(block_id)
                # Fix the block. The hash is different because the Public Key is not accessible.
                block.id = block_id
                if not self.database.contains(block.id):
                    self.database.add_block(block)
        total_blocks = len(self.database.get_ids())
        print "Found " + str(total_blocks) + " unique multichain blocks across databases"




def string_is_int(string):
    try:
        int(string)
        return True
    except ValueError:
        return False
