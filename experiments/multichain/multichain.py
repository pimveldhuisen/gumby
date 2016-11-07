#!/usr/bin/env python2
from os import path, environ
from sys import path as pythonpath
import base64

from gumby.experiments.dispersymulticlient import main
from experiments.dispersy.hiddenservices_client import HiddenServicesClient

from twisted.python.log import msg

pythonpath.append(path.abspath(path.join(path.dirname(__file__), '..', '..', '..', "./tribler")))

from Tribler.dispersy.candidate import Candidate
from Tribler.community.multichain.community import MultiChainCommunity, MultiChainCommunityCrawler


class MultiChainClient(HiddenServicesClient):
    """
    Gumby client to start the MultiChain Community in conjunction with the HiddenServicesClient.
    """

    def __init__(self, *args, **kwargs):
        super(MultiChainClient, self).__init__(*args, **kwargs)
        msg("Starting MultiChain client")
        self.set_community(MultiChainCommunity, name="multichain")
        self.vars['public_key'] = base64.encodestring(self.my_member_key)

        # Override the test files to speed up the test.
        # 10 Mb
        self.test_file_size = 10 * 1024 * 1024
        self.min_circuits = 1
        self.max_circuits = 1

    def configure_multichain_community(self):
        self.set_community_kwarg('tribler_session', self.session, name="multichain")

    def registerCallbacks(self):
        super(MultiChainClient, self).registerCallbacks()
        self.scenario_runner.register(self.configure_multichain_community)
        self.scenario_runner.register(self.online)
        self.scenario_runner.register(self.introduce_candidates)
        self.scenario_runner.register(self.request_signature)
        self.scenario_runner.register(self.request_crawl)

    @property
    def multichain_community(self):
        return self.experiment_communities["multichain"].community

    def online(self, dont_empty=False):
        super(MultiChainClient, self).online(dont_empty)
        def cleanup_candidates(self):
            return 0
        # The multichain community needs to keep it's candidates around. So to 'override' the candidate cleanup, we
        # monkeypatch the original object with a bound instance function, obtained through the __get__ descriptor of the
        #  function object.
        self.multichain_community.cleanup_candidates = cleanup_candidates.__get__(
                self.multichain_community,
                self.experiment_communities["multichain"].community_class)

    def request_signature(self, candidate_id):
        target = self.all_vars[candidate_id]
        msg("%s: Requesting Signature for candidate: %s" % (self.my_id, candidate_id))
        candidate = self.multichain_community.get_candidate((str(target['host']), target['port']))
        self.multichain_community.sign_block(candidate, 1, 1)

    def request_crawl(self, candidate_id, sequence_number):
        target = self.all_vars[candidate_id]
        msg("%s: Requesting block: %s For candidate: %s" % (self.my_id, sequence_number, candidate_id))
        candidate = self.multichain_community.get_candidate((str(target['host']), target['port']))
        self.multichain_community.send_crawl_request(candidate, int(sequence_number))

    def introduce_candidates(self):
        """
        Introduce every candidate to each other so that later the candidates can be retrieved and used as a destination.
        """
        super(MultiChainClient, self).introduce_candidates()
        msg("Introducing every candidate")
        for node in self.all_vars.itervalues():
            candidate = Candidate((str(node['host']), node['port']), False)
            self.multichain_community.add_discovered_candidate(candidate)
            candidate = self.multichain_community.get_candidate((str(node['host']), node['port']))
            member = self.multichain_community.get_member(public_key=base64.decodestring(str(node['public_key'])))
            member.add_identity(self.multichain_community)
            candidate.associate(member)


class MultiChainDelayCommunity(MultiChainCommunity):
    """
    Test Community that delays signature requests.
    """
    delay = 3

    def __init__(self, *args, **kwargs):
        super(MultiChainDelayCommunity, self).__init__(*args, **kwargs)

    def received_signed_block(self, messages):
        """
        Ignore the signature requests.
        :param message: the to be delayed request
        """
        def continue_after_delay():
            self.logger.info("Delay over.")
            super(MultiChainDelayCommunity, self).received_signed_block(messages)
        self.logger.info("Received signature requests that will delayed for %s." % self.delay)
        reactor.callLater(self.delay, continue_after_delay)


class MultiChainNoResponseCommunity(MultiChainCommunity):
    """
    Test Community that does not respond to signature requests.
    """

    def __init__(self, *args, **kwargs):
        super(MultiChainNoResponseCommunity, self).__init__(*args, **kwargs)

    def received_signed_block(self, messages):
        """
        Ignore the signature requests.
        :param message: the to be ignored request
        """
        self.logger.info("Received signature request that will be ignored.")
        return

if __name__ == '__main__':
    MultiChainClient.scenario_file = environ.get('SCENARIO_FILE', 'multichain.scenario')
    main(MultiChainClient)
