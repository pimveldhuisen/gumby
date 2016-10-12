import os
from os import path
import base64

from Tribler.community.multichain.database import MultiChainDB
from Tribler.community.multichain.block import GENESIS_HASH, PK_LENGTH

class MultiChainExperimentAnalysisDatabase(MultiChainDB):
    """
    Extended MultiChainDB that provides additional functionality to analyze an experiment.
    """

    def __init__(self, working_directory):
        super(MultiChainExperimentAnalysisDatabase, self).__init__(working_directory)

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
        # Either contains all information all ready or all information will be aggregated here.
        self.working_directory = working_directory
        self.database = self.get_database(self.working_directory)
        # Mids are retrieved during generate_graph and used in generate_totals
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
                "Up " +
                "Down " +
                "Total_Up " +
                "Total_Down " +

                "Public_Key "
                "Sequence_Number " +
                "Linked_Public_Key " +
                "Linked_Sequence_Number " +
                "Previous_Hash " +

                "Signature " +
                "Insert_Time " +
                "Block_Hash " +
                "\n"
            )

            # Write blocks
            blocks = self.database._getall(u"", [])
            for block in blocks:
                multichain_file.write(
                    str(block.up) + " " +
                    str(block.down)+" " +
                    str(block.total_up) + " " +
                    str(block.total_down) + " " +

                    base64.encodestring(block.public_key).replace('\n', '').replace('\r', '') + " " +
                    str(block.sequence_number) + " " +
                    base64.encodestring(block.link_public_key).replace('\n', '').replace('\r', '') + " " +
                    str(block.link_sequence_number) + " " +
                    base64.encodestring(block.previous_hash).replace('\n', '').replace('\r', '') + " " +

                    base64.encodestring(block.signature).replace('\n', '').replace('\r', '') + " " +
                    base64.encodestring(block.insert_time).replace('\n', '').replace('\r', '') + " " +
                    base64.encodestring(block.hash).replace('\n', '').replace('\r', '') + " " +
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
        # Write to file
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
                databases.append(MultiChainDB(path.join(self.working_directory, dir_name)))
        for database in databases:
            blocks = database._getall(u"", [])
            for block in blocks:
                if not self.database.contains(block):
                    self.database.add_block(block)
        total_blocks = len(self.database._getall(u"", []))
        print "Found " + str(total_blocks) + " unique multichain blocks across databases"

    def get_database(self, db_path):
        return MultiChainExperimentAnalysisDatabase(db_path)


class GumbyStandaloneDatabaseReader(DatabaseReader):

    def __init__(self, working_directory):
        super(GumbyStandaloneDatabaseReader, self).__init__(working_directory)

    def get_database(self, db_path):
        return MultiChainExperimentAnalysisDatabase(self.MockDispersy(), db_path)

    def combine_databases(self):
        print "THIS CODE SHOULD NOT BE REACHED"
        print "Reading databases."
        databases = []
        for dir_name in os.listdir(self.working_directory):
            # Read all nodes
          #  if 'Tribler' in dir_name:
            if dir_name.isdigit():
                databases.append(MultiChainDB(self.MockDispersy(), path.join(self.working_directory, dir_name)))
        for database in databases:
            hashes_requester = database.get_all_hash_requester()
            for hash_requester in hashes_requester:
                block = database.get_by_hash_requester(hash_requester)
                if not self.database.contains(hash_requester):
                    self.database.add_block(block)
        total_blocks = len(self.database.get_all_hash_requester())
        print "Found " + str(total_blocks) + " unique multichain blocks across databases"




def string_is_int(string):
    try:
        int(string)
        return True
    except ValueError:
        return False
