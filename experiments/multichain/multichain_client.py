#!/usr/bin/env python
from os import path, environ
from sys import path as pythonpath
from time import sleep
import base64

from gumby.experiments.dispersyclient import DispersyExperimentScriptClient, main

from twisted.python.log import msg

pythonpath.append(path.abspath(path.join(path.dirname(__file__), '..', '..', '..', "./tribler")))

from Tribler.dispersy.candidate import Candidate
from Tribler.community.multichain.community import MultiChainCommunity


class MultiChainClient(DispersyExperimentScriptClient):
    """
    Gumby client to start the MultiChain Community
    """

    _SECURITY_LEVEL = u'high'

    def __init__(self, *argv, **kwargs):
        DispersyExperimentScriptClient.__init__(self, *argv, **kwargs)
        msg("Starting MultiChain client")
        # Set the default MultiChainCommunity as community
        self.community_class = MultiChainCommunity
        self.vars['public_key'] = base64.encodestring(self.my_member_key)

    def registerCallbacks(self):
        self.scenario_runner.register(self.introduce_candidates, 'introduce_candidates')
        self.scenario_runner.register(self.set_community_class, 'set_community_class')
        self.scenario_runner.register(self.request_signature, 'request_signature')
        self.scenario_runner.register(self.close, 'close')

    def set_community_class(self, community_type='MultiChainCommunity'):
        """
        Sets the community class of this gumby node to a special community.
        """
        msg("CommunityType: %s" % community_type)
        if community_type == 'MultiChainDelayCommunity':
            msg("Starting MultiChain client with: " + MultiChainDelayCommunity.__name__)
            self.community_class = MultiChainCommunity
        elif community_type == 'MultiChainNoResponseCommunity':
            msg("Starting MultiChain client with: " + MultiChainNoResponseCommunity.__name__)
            self.community_class = MultiChainNoResponseCommunity
        else:
            raise RuntimeError("Tried to set to unknown community.")

    def online(self):
        DispersyExperimentScriptClient.online(self)

    def request_signature(self, candidate_id=0):
        msg("%s: Requesting Signature for candidate: %s" % (self.my_id, candidate_id))
        if candidate_id == 0:
            for c in self.all_vars.itervalues():
                candidate = self._community.get_candidate((str(c['host']), c['port']))
                print("Member: %s" % candidate.get_member())
                self._community.publish_signature_request_message(candidate)
        else:
            target = self.all_vars[candidate_id]
            candidate = self._community.get_candidate((str(target['host']), target['port']))
            print("Candidate: %s" % candidate.get_member())
            self._community.publish_signature_request_message(candidate)

    def introduce_candidates(self):
        """
        Introduce every candidate to each other so that later the candidates can be retrieved and used as a destination.
        """
        msg("Introducing every candidate")
        for node in self.all_vars.itervalues():
            candidate = Candidate((str(node['host']), node['port']), False)
            self._community.add_discovered_candidate(candidate)

    def close(self):
        msg("close command received")
        self._community.unload_community()


class MultiChainDelayCommunity(MultiChainCommunity):
    """
    Test Community that delays signature requests.
    """
    delay = 3

    def __init__(self, *args, **kwargs):
        super(MultiChainCommunity, self).__init__(*args, **kwargs)

    def allow_signature_request(self, message):
        """
        Ignore the signature requests.
        :param message: the to be delayed request
        """
        self._logger.info("Received signature request that will delayed for %s." % self.delay)
        sleep(self.delay)
        self._logger.info("Delay over.")
        super(MultiChainCommunity, self).allow_signature_request(message)


class MultiChainNoResponseCommunity(MultiChainCommunity):
    """
    Test Community that does not respond to signature requests.
    """

    def __init__(self, *args, **kwargs):
        super(MultiChainNoResponseCommunity, self).__init__(*args, **kwargs)

    def allow_signature_request(self, message):
        """
        Ignore the signature requests.
        :param message: the to be ignored request
        """
        self._logger.info("Received signature request that will be ignored.")
        return

if __name__ == '__main__':
    MultiChainClient.scenario_file = environ.get('SCENARIO_FILE', 'multichain.scenario')
    main(MultiChainClient)