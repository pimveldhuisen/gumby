#!/usr/bin/env python2
import base64
import os
from random import randint, choice

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from gumby.experiments.dispersyclient import main
from gumby.experiments.triblerclient import TriblerExperimentScriptClient

from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.dispersy.candidate import Candidate


class MultiChainClient(TriblerExperimentScriptClient):
    """
    This client is responsible for managing experiments with the MultiChain community.
    """
    def __init__(self, params):
        super(MultiChainClient, self).__init__(params)
        self.multichain_community = None
        self.vars['public_key'] = base64.encodestring(self.my_member_key)
        self.request_random_signatures_lc = LoopingCall(self.request_random_signature)
        self.log_data_lc = LoopingCall(self.log_data)
        self.trace_replay_lc = LoopingCall(self.replay_trace)
        import Tribler.Core.permid as permidmod
        self.multichain_keypair = permidmod.generate_keypair_multichain()
        self.vars['multichain_public_key'] = base64.encodestring(self.multichain_keypair.pub().key_to_bin())

    def setup_session_config(self):
        config = super(MultiChainClient, self).setup_session_config()
        config.set_tunnel_community_enabled(False)
        config.set_enable_multichain(False)  # We're loading our own multichain community
        return config

    def registerCallbacks(self):
        super(MultiChainClient, self).registerCallbacks()
        self.scenario_runner.register(self.request_signature)
        self.scenario_runner.register(self.request_crawl)
        self.scenario_runner.register(self.start_requesting_random_signatures)
        self.scenario_runner.register(self.stop_requesting_random_signatures)
        self.scenario_runner.register(self.load_trace)
        self.scenario_runner.register(self.start_trace_replay)
        self.scenario_runner.register(self.start_logging_data)
        self.scenario_runner.register(self.load_multichain_community)
        self.scenario_runner.register(self.start_trust_walk)

    def start_trust_walk(self):
        self.multichain_community.start_trust_walk()

    def request_signature(self, candidate_id, up, down):
        target = self.all_vars[str(candidate_id)]
        self._logger.info("%s: Requesting Signature for candidate: %s" % (self.my_id, candidate_id))
        candidate = Candidate((str(target['host']), 21000 + int(candidate_id)), False)
        if not candidate.get_member():
            member = self.multichain_community.get_member(public_key=base64.decodestring(target['multichain_public_key']))
            member.add_identity(self.multichain_community)
            candidate.associate(member)
            if not candidate.get_member():
                self._logger.error("Candidate has no member")

        self.request_signature_from_candidate(candidate, up, down)

    def request_signature_from_candidate(self, candidate, up, down):
        self.multichain_community.schedule_block(candidate, int(up), int(down))

    def request_crawl(self, candidate_id, sequence_number):
        target = self.all_vars[candidate_id]
        self._logger.info("%s: Requesting block: %s For candidate: %s" % (self.my_id, sequence_number, candidate_id))
        candidate = self.multichain_community.get_candidate((str(target['host']), target['port']))
        self.multichain_community.send_crawl_request(candidate, int(sequence_number))

    def start_requesting_random_signatures(self):
        self.request_random_signatures_lc.start(1)

    def stop_requesting_random_signatures(self):
        self.request_random_signatures_lc.stop()

    def start_trace_replay(self):
        self.trace_replay_lc.start(1)

    def replay_trace(self):
        if self.request_queue:
            request = self.request_queue.pop()
            try:
                candidate_id = self._find_id(request.public_key_responder)
            except LookupError:
                self._logger.error("Counterparty for block not found within experiment")
                return
            self.request_signature(candidate_id, request.up, request.down)
        else:
            self.trace_replay_lc.stop()

    def request_random_signature(self):
        """
        Request a random signature from one of your known candidates
        """
        rand_up = randint(1, 1000)
        rand_down = randint(1, 1000)
        known_candidates = list(self.multichain_community.dispersy_yield_verified_candidates())
        self.request_signature_from_candidate(choice(known_candidates), rand_up * 1024 * 1024, rand_down * 1024 * 1024)

    def start_logging_data(self):
        self.log_data_lc.start(5)

    def log_data(self):
        with open("log_file_trust_edges", 'a') as f:
            f.write(str(len(self.multichain_community.get_trusted_edges())) + "\n")
        with open("log_file_blocks", 'a') as f:
            f.write(str(len(self.multichain_community.persistence.get_all_hash_requester())) + "\n")
        with open("log_file_load", 'a') as f:
            f.write(str(self.multichain_community.crawl_requests_received) + "\n")

    def load_trace(self):
        number_of_nodes = len(self.get_peers())
        from Tribler.community.multichain.database import MultiChainDB
        self.database = MultiChainDB(None, os.environ['EXPERIMENT_DIR'])
        self.id_lookup_table = []
        for x in range(number_of_nodes):
            self.id_lookup_table.append(self.database.get_requester_identities()[x])
        self.request_queue = self.database.get_requester_blocks(self.id_lookup_table[int(self.my_id)-1])

        self._logger.error("ID " + self.my_id + " has " + str(len(self.request_queue)) + " requests to make")

    def _find_id(self, public_key):
        for x in range(len(self.id_lookup_table)):
            if str(self.id_lookup_table[x]) == public_key:
                return x+1
        raise LookupError

    def load_multichain_community(self):
        """
        Load the multichain community
        """
        my_member = self.session.get_dispersy_instance().get_member(private_key=self.multichain_keypair.key_to_bin())
        self.multichain_community = self.session.get_dispersy_instance().define_auto_load(
            MultiChainCommunity, my_member, load=True, kargs={'tribler_session': self.session})[0]

        # The multichain community needs to keep it's candidates around. So to 'override' the candidate cleanup, we
        # monkeypatch the original object. Using the above method bound to the community instance.
        self.multichain_community.cleanup_candidates = lambda: 0

if __name__ == '__main__':
    MultiChainClient.scenario_file = os.environ.get('SCENARIO_FILE', 'multichain_1000.scenario')
    main(MultiChainClient)
