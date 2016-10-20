#!/usr/bin/env python2
# dispersymulticlient.py ---
#
# Filename: dispersymulticlient.py
# Description:
# Author: Captain Coder
# Maintainer:
# Created: 20160107

# Commentary:
# Managing multiple dispersy communities in a single experiment
#

#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street, Fifth
# Floor, Boston, MA 02110-1301, USA.
#
#

import base64
import json
import logging
import traceback
from collections import Iterable, defaultdict
from os import chdir, environ, getpid, makedirs, path, symlink
from random import random
from sys import exit, stderr, stdout
from time import time, sleep
from traceback import print_exc

import shutil

from gumby.log import setupLogging
from gumby.scenario import ScenarioRunner
from gumby.sync import ExperimentClient, ExperimentClientFactory, ExperimentServiceFactory

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

from sys import path as pythonpath

class MultiDispersyExperimentScriptClient(ExperimentClient):
    scenario_file = None

    def __init__(self, vars):
        super(MultiDispersyExperimentScriptClient, self).__init__(vars)
        self._dispersy = None
        self._database_file = u"dispersy.db"
        self._dispersy_exit_status = None
        self._dispersy_provider = DispersyExperimentProvider()
        self._strict = True
        self._stats_file = None
        self._online_buffer = []

        self.dispersy_port = 12000
        self.experiment_communities = {}
        self.session = None
        self.original_on_incomming_packets = None

        self._crypto = self.initializeCrypto()
        self.generateMyMember()
        self.vars['private_keypair'] = base64.encodestring(self.my_member_private_key)

    def onVarsSend(self):
        scenario_file_path = path.join(environ['EXPERIMENT_DIR'], self.scenario_file)
        self.scenario_runner = ScenarioRunner(scenario_file_path)

        t1 = time()
        self.scenario_runner._read_scenario(scenario_file_path)
        self._logger.debug('Took %.2f to read scenario file', time() - t1)

    def onIdReceived(self):
        self._logger.debug('Got ID %s assigned', self.my_id)
        self.scenario_runner.set_peernumber(int(self.my_id))

        # If not set with set_dispersy_port, each peer should gets a unique port number
        self.dispersy_port += int(self.my_id)

        # TODO(emilon): Auto-register this stuff
        self.scenario_runner.register(self.echo)
        self.scenario_runner.register(self.online)
        self.scenario_runner.register(self.offline)
        self.scenario_runner.register(self.set_community_kwarg)
        self.scenario_runner.register(self.set_database_file)
        self.scenario_runner.register(self.use_memory_database)
        self.scenario_runner.register(self.set_ignore_exceptions)
        self.scenario_runner.register(self.start_dispersy)
        self.scenario_runner.register(self.stop_dispersy)
        self.scenario_runner.register(self.stop)
        self.scenario_runner.register(self.set_master_member)
        self.scenario_runner.register(self.reset_dispersy_statistics)
        self.scenario_runner.register(self.annotate)
        self.scenario_runner.register(self.peertype)
        self.scenario_runner.register(self.set_community)
        self.scenario_runner.register(self.set_dispersy_port)
        self.scenario_runner.register(self.set_dispersy_source)

        self.registerCallbacks()

        t1 = time()
        self.scenario_runner.parse_file()
        self._logger.debug('Took %.2f to parse scenario file' , time() - t1)

    def startExperiment(self):
        self._logger.debug("Starting dispersy scenario experiment")

        # TODO(emilon): Move this to the right place
        # TODO(emilon): Do we want to have the .dbs in the output dirs or should they be dumped to /tmp?
        my_dir = path.join(environ['OUTPUT_DIR'], self.my_id)
        shutil.rmtree(my_dir, True)
        makedirs(my_dir)
        chdir(my_dir)
        self._stats_file = open("statistics.log", 'w')

        # TODO(emilon): Fix me or kill me
        try:
            bootstrap_fn = path.join(environ['PROJECT_DIR'], 'tribler', 'bootstraptribler.txt')
            if not path.exists(bootstrap_fn):
                bootstrap_fn = path.join(environ['PROJECT_DIR'], '..', 'bootstraptribler.txt')
            symlink(bootstrap_fn, 'bootstraptribler.txt')
        except OSError:
            pass

        self.scenario_runner.run()

    def registerCallbacks(self):
        pass

    def initializeCrypto(self):
        try:
            from Tribler.dispersy.crypto import ECCrypto, NoCrypto
        except:
            from dispersy.crypto import ECCrypto, NoCrypto

        if environ.get('TRACKER_CRYPTO', 'ECCrypto') == 'ECCrypto':
            self._logger.debug('Turning on ECCrypto')
            return ECCrypto()
        self._logger.debug('Turning off Crypto')
        return NoCrypto()

    @property
    def my_member_key_curve(self):
        # low (NID_sect233k1) isn't actually that low, switching to 160bits as this is comparable to rsa 1024
        # http://www.nsa.gov/business/programs/elliptic_curve.shtml
        # speed difference when signing/verifying 100 items
        # NID_sect233k1 signing took 0.171 verify took 0.35 totals 0.521
        # NID_secp160k1 signing took 0.04 verify took 0.04 totals 0.08
        return u"NID_secp160k1"


    def generateMyMember(self):
        ec = self._crypto.generate_key(self.my_member_key_curve)
        self.my_member_key = self._crypto.key_to_bin(ec.pub())
        self.my_member_private_key = self._crypto.key_to_bin(ec)

    #
    # Actions
    #

    def echo(self, *argv):
        self._logger.debug("%s ECHO %s", self.my_id, ' '.join(argv))

    def set_community_args(self, args, name = "default"):
        """
        Example: '1292333014,12923340000'
        """
        self.experiment_communities[name].args = args.split(',')

    def set_community_kwargs(self, kwargs, name = "default"):
        """
        Example: 'startingtimestamp=1292333014,endingtimestamp=12923340000'
        """
        for karg in kwargs.split(","):
            if "=" in karg:
                key, value = karg.split("=", 1)
                self.experiment_communities[name].kwargs[key.strip()] = value.strip()

    def set_community_kwarg(self, key, value, name = "default"):
        self.experiment_communities[name].kwargs[key] = value

    def set_dispersy_source(self, source):
        if source == "Core":
            self._dispersy_provider = DispersyExperimentTriblerProvider()
        else:
            self._dispersy_provider = DispersyExperimentProvider()

    def set_community(self, community_class, name = "default"):
        from sys import modules
        if isinstance(community_class, basestring):
            import __main__
            community_class = getattr(__main__, community_class)
        assert community_class, "Must supply class of community to add"

        if name is None:
            name = community_class.__name__
        if (self.experiment_communities.get(name) is None):
            self.experiment_communities[name] = DispersyExperimentCommunity()
        self.experiment_communities[name].name = name
        self.experiment_communities[name].community_class = community_class

    def set_dispersy_port(self, port):
        self.dispersy_port = int(port)

    def set_database_file(self, filename):
        self._database_file = unicode(filename)

    def use_memory_database(self):
        self._database_file = u':memory:'

    def set_ignore_exceptions(self, boolean):
        self._strict = not self.str2bool(boolean)

    def start_dispersy(self, autoload_discovery=True):
        self._logger.debug("Starting dispersy")
        self._dispersy_provider.start_dispersy(self)

    def post_start_dispersy(self):
        for name in self.experiment_communities:
            if self.experiment_communities[name].master_private_key:
                self.experiment_communities[name].master_member = self._dispersy.get_member(private_key=self.experiment_communities[name].master_private_key)
            else:
                self.experiment_communities[name].master_member = self._dispersy.get_member(public_key=self.experiment_communities[name].master_key)
            assert self.experiment_communities[name].master_member

        self._my_member = self.get_my_member()
        assert self._my_member

        self._do_log()
        self._logger.debug("Finished starting dispersy")

    def get_my_member(self):
        return self._dispersy.get_member(private_key=self.my_member_private_key)

    def stop_dispersy(self):
        self._dispersy_provider.stop_dispersy(self)

    def stop(self, retry=3):
        self._dispersy_provider.stop(self, retry)

    def set_master_member(self, pub_key, name='default', priv_key=''):
        self.experiment_communities[name].master_key = pub_key.decode("HEX")
        self.experiment_communities[name].master_private_key = priv_key.decode("HEX")

    def online(self, dont_empty=False):
        for name in self.experiment_communities:
            self._logger.debug("Trying to go online")
            if self.experiment_communities[name].community is None:
                assert self.experiment_communities[name].master_member, "Community %s should have a master member defined" % name
                self._logger.debug("online %s" % name)
                self._logger.debug("join community %s as %s",
                                   self.experiment_communities[name].master_member.mid.encode("HEX"),
                                   self._my_member.mid.encode("HEX"))
                self._dispersy.on_incoming_packets = self.original_on_incoming_packets
                self.experiment_communities[name].community = self.experiment_communities[name].community_class.init_community(
                                                                  self._dispersy, self.experiment_communities[name].master_member, self._my_member,
                                                                  *self.experiment_communities[name].args, **self.experiment_communities[name].kwargs)
                self.experiment_communities[name].community.auto_load = False

                assert self.is_online(name)
                if not dont_empty:
                    self.empty_buffer(name)

                self._logger.debug("Dispersy is using port %s", repr(self._dispersy._endpoint.get_address()))
            else:
                self._logger.debug("online (we are already online)")

    def offline(self, name=None):
        if not name is None:
            if not self.experiment_communities[name].community is None:
                self._logger.debug("Unload %s (we are already offline)" % name)
            else:
                self._logger.debug("Unloading community %s" % name)
                self.experiment_communities[name].community.unload_community()
                self.experiment_communities[name].community = None
        else:
            self._logger.debug("Trying to go offline")
            for community in self._dispersy.get_communities():
                community.unload_community()
            for key in self.experient_communities:
                self.experiment_communities[name].community = None
            self._dispersy.on_incoming_packets = lambda *params: None
            self._logger.debug("offline")

            if self._database_file == u':memory:':
                self._logger.debug("Be careful with memory databases and nodes going offline, "
                                   "you could be losing database because we're closing databases.")

    def is_online(self, name):
        return self.experiment_communities[name].community != None

    def buffer_call(self, func, args, kargs, name = 'default'):
        if len(self._online_buffer) == 0 and self.is_online(name):
            func(*args, **kargs)
        else:
            self._online_buffer.append((name, func, args, kargs))

    def empty_buffer(self, name = 'default'):
        assert self.is_online(name)

        # perform all tasks which were scheduled while we were offline
        for cname, func, args, kargs in self._online_buffer:
            if cname != name:
                continue
            try:
                func(*args, **kargs)
            except:
                print_exc()

        self._online_buffer = [item[0] != name for item in self._online_buffer]

    def reset_dispersy_statistics(self):
        self._dispersy._statistics.reset()

    def annotate(self, message):
        self._stats_file.write('%.1f %s %s %s\n' % (time(), self.my_id, "annotate", message))
    def peertype(self, peertype):
        self._stats_file.write('%.1f %s %s %s\n' % (time(), self.my_id, "peertype", peertype))

    #
    # Aux. functions
    #


    def get_private_keypair_by_id(self, peer_id):
        if str(peer_id) in self.all_vars:
            key = self.all_vars[str(peer_id)]['private_keypair']
            if isinstance(key, basestring):
                key = self.all_vars[str(peer_id)]['private_keypair'] = self._crypto.key_from_private_bin(base64.decodestring(key))
            return key

    def get_private_keypair(self, ip, port):
        port = int(port)
        for peer_dict in self.all_vars.itervalues():
            if peer_dict['host'] == ip and int(peer_dict['port']) == port:
                key = peer_dict['private_keypair']
                if isinstance(key, basestring):
                    key = peer_dict['private_keypair'] = self._crypto.key_from_private_bin(base64.decodestring(key))
                return key

        err("Could not get_private_keypair for", ip, port)

    def str2bool(self, v):
        return v.lower() in ("yes", "true", "t", "1")

    def str2tuple(self, v):
        if len(v) > 1 and v[1] == "t":
            return (int(v[0]), int(v[2:]))
        if len(v) > 1 and v[1] == ".":
            return float(v)
        return int(v)

    def print_on_change(self, name, prev_dict, cur_dict):
        def get_changed_values(prev_dict, cur_dict):
            new_values = {}
            changed_values = {}
            if cur_dict:
                for key, value in cur_dict.iteritems():
                    # convert key to make it printable
                    if not isinstance(key, (basestring, int, long, float)):
                        key = str(key)

                    # if this is a dict, recursively check for changed values
                    if isinstance(value, dict):
                        converted_dict, changed_in_dict = get_changed_values(prev_dict.get(key, {}), value)

                        new_values[key] = converted_dict
                        if changed_in_dict:
                            changed_values[key] = changed_in_dict

                    # else convert and compare single value
                    else:
                        if not isinstance(value, (basestring, int, long, float, Iterable)):
                            value = str(value)

                        new_values[key] = value
                        if prev_dict.get(key, None) != value:
                            changed_values[key] = value

            return new_values, changed_values

        new_values, changed_values = get_changed_values(prev_dict, cur_dict)
        if changed_values:
            self._stats_file.write('%.1f %s %s %s\n' % (time(), self.my_id, name, json.dumps(changed_values)))
            self._stats_file.flush()
            return new_values
        return prev_dict

    @inlineCallbacks
    def _do_log(self):
        try:
            from Tribler.dispersy.candidate import CANDIDATE_STUMBLE_LIFETIME, CANDIDATE_WALK_LIFETIME, CANDIDATE_INTRO_LIFETIME
        except:
            from dispersy.candidate import CANDIDATE_STUMBLE_LIFETIME, CANDIDATE_WALK_LIFETIME, CANDIDATE_INTRO_LIFETIME
        total_stumbled_candidates = defaultdict(lambda:defaultdict(set))

        prev_statistics = {}
        prev_total_received = {}
        prev_total_dropped = {}
        prev_total_delayed = {}
        prev_total_outgoing = {}
        prev_total_fail = {}
        prev_endpoint_recv = {}
        prev_endpoint_send = {}
        prev_created_messages = {}
        prev_bootstrap_candidates = {}

        while True:
            self._dispersy.statistics.update()

            communities_dict = {}
            for c in self._dispersy.statistics.communities:

                if c._community.dispersy_enable_candidate_walker:
                    # determine current size of candidates categories
                    nr_walked = nr_intro = nr_stumbled = 0

                    # we add all candidates which have a last_stumble > now - CANDIDATE_STUMBLE_LIFETIME
                    now = time()
                    for candidate in c._community.candidates.itervalues():
                        if candidate.last_stumble > now - CANDIDATE_STUMBLE_LIFETIME:
                            nr_stumbled += 1

                            mid = candidate.get_member().mid
                            total_stumbled_candidates[c.hex_cid][candidate.last_stumble].add(mid)

                        if candidate.last_walk > now - CANDIDATE_WALK_LIFETIME:
                            nr_walked += 1

                        if candidate.last_intro > now - CANDIDATE_INTRO_LIFETIME:
                            nr_intro += 1
                else:
                    nr_walked = nr_intro = nr_stumbled = "?"

                total_nr_stumbled_candidates = sum(len(members) for members in total_stumbled_candidates[c.hex_cid].values())

                communities_dict[c.hex_cid] = {'classification': c.classification,
                                         'global_time': c.global_time,
                                         'sync_bloom_new': c.sync_bloom_new,
                                         'sync_bloom_reuse': c.sync_bloom_reuse,
                                         'sync_bloom_send': c.sync_bloom_send,
                                         'sync_bloom_skip': c.sync_bloom_skip,
                                         'nr_candidates': len(c.candidates) if c.candidates else 0,
                                         'nr_walked': nr_walked,
                                         'nr_stumbled': nr_stumbled,
                                         'nr_intro' : nr_intro,
                                         'total_stumbled_candidates': total_nr_stumbled_candidates}

            # check for missing communities, reset candidates to 0
            cur_cids = communities_dict.keys()
            for cid, c in prev_statistics.get('communities', {}).iteritems():
                if cid not in cur_cids:
                    _c = c.copy()
                    _c['nr_candidates'] = "?"
                    _c['nr_walked'] = "?"
                    _c['nr_stumbled'] = "?"
                    _c['nr_intro'] = "?"
                    communities_dict[cid] = _c

            statistics_dict = {'conn_type': self._dispersy.statistics.connection_type,
                               'received_count': self._dispersy.statistics.total_received,
                               'success_count': self._dispersy.statistics.msg_statistics.success_count,
                               'drop_count': self._dispersy.statistics.msg_statistics.drop_count,
                               'delay_count': self._dispersy.statistics.msg_statistics.delay_received_count,
                               'delay_success': self._dispersy.statistics.msg_statistics.delay_success_count,
                               'delay_timeout': self._dispersy.statistics.msg_statistics.delay_timeout_count,
                               'delay_send': self._dispersy.statistics.msg_statistics.delay_send_count,
                               'created_count': self._dispersy.statistics.msg_statistics.created_count,
                               'total_up': self._dispersy.statistics.total_up,
                               'total_down': self._dispersy.statistics.total_down,
                               'total_send': self._dispersy.statistics.total_send,
                               'cur_sendqueue': self._dispersy.statistics.cur_sendqueue,
                               'total_candidates_discovered': self._dispersy.statistics.total_candidates_discovered,
                               'walk_attempt': self._dispersy.statistics.walk_attempt_count,
                               'walk_success': self._dispersy.statistics.walk_success_count,
                               'walk_invalid_response_identifier': self._dispersy.statistics.invalid_response_identifier_count,
                               'communities': communities_dict}

            prev_statistics = self.print_on_change("statistics", prev_statistics, statistics_dict)
            prev_total_dropped = self.print_on_change("statistics-dropped-messages", prev_total_dropped, self._dispersy.statistics.msg_statistics.drop_dict)
            prev_total_delayed = self.print_on_change("statistics-delayed-messages", prev_total_delayed, self._dispersy.statistics.msg_statistics.delay_dict)
            prev_total_received = self.print_on_change("statistics-successful-messages", prev_total_received, self._dispersy.statistics.msg_statistics.success_dict)
            prev_total_outgoing = self.print_on_change("statistics-outgoing-messages", prev_total_outgoing, self._dispersy.statistics.msg_statistics.outgoing_dict)
            prev_created_messages = self.print_on_change("statistics-created-messages", prev_created_messages, self._dispersy.statistics.msg_statistics.created_dict)
            prev_total_fail = self.print_on_change("statistics-walk-fail", prev_total_fail, self._dispersy.statistics.walk_failure_dict)
            prev_endpoint_recv = self.print_on_change("statistics-endpoint-recv", prev_endpoint_recv, self._dispersy.statistics.endpoint_recv)
            prev_endpoint_send = self.print_on_change("statistics-endpoint-send", prev_endpoint_send, self._dispersy.statistics.endpoint_send)

            yield deferLater(reactor, 5.0, lambda : None)

class DispersyExperimentCommunity(object):
    def __init__(self, *args, **kargs):
        super(DispersyExperimentCommunity, self).__init__(*args, **kargs)
        self.name = "Unnamed Experiment Community"
        self.community = None
        self.community_class = None
        self.master_key = None
        self.master_private_key = None
        self.master_member = None
        self.args = []
        self.kwargs = {}

class DispersyExperimentProvider(object):
    def __init__(self, *args, **kargs):
        super(DispersyExperimentProvider, self).__init__(*args, **kargs)
        self.dispersy = None

    def start_dispersy(self, client, autoload_discovery=True):
        try:
            from Tribler.dispersy.dispersy import Dispersy
            from Tribler.dispersy.endpoint import StandaloneEndpoint
        except:
            from dispersy.dispersy import Dispersy
            from dispersy.endpoint import StandaloneEndpoint

        self.dispersy = Dispersy(StandaloneEndpoint(client.dispersy_port, '0.0.0.0'), u'.', client._database_file, client._crypto)
        self.dispersy.statistics.enable_debug_statistics(True)
        client._dispersy = self.dispersy
        client.original_on_incoming_packets = self.dispersy.on_incoming_packets

        if client._strict:
            from twisted.python.log import addObserver
            try:
                from Tribler.dispersy.util import unhandled_error_observer
            except:
                from dispersy.util import unhandled_error_observer
            addObserver(unhandled_error_observer)

        self.dispersy.start(autoload_discovery=autoload_discovery)
        client.post_start_dispersy()

    def stop_dispersy(self, client):
        client._dispersy_exit_status = self.dispersy.stop()

    def stop(self, client, retry=3):
        retry = int(retry)
        if client._dispersy_exit_status is None and retry:
            reactor.callLater(1, self.stop, client, retry - 1)
        else:
            client._logger.debug("Dispersy exit status was: %s", client._dispersy_exit_status)
            reactor.callLater(0, reactor.stop)

BASE_DIR = path.abspath(path.join(path.dirname(__file__), '..', '..', '..'))

class DispersyExperimentTriblerProvider(DispersyExperimentProvider):
    def __init__(self, *args, **kargs):
        super(DispersyExperimentProvider, self).__init__(*args, **kargs)
        self.session = None
        self.session_config = None
        self.session_deferred = None
        self.base_dir = BASE_DIR
        pythonpath.append(path.abspath(path.join(self.base_dir, "./tribler")))

    def start_dispersy(self, client, autoload_discovery=True):
        from Tribler.Core.Session import Session
        from twisted.internet import threads

        def _do_start():
            try:
                logging.error("Starting Tribler Session")
                self.session_config = self.setup_session_config(client)
                self.session = Session(scfg=self.session_config)
                client.session = self.session

                upgrader = self.session.prestart()
                while not upgrader.is_done:
                    sleep(0.1)

                self.session.start()

                while not self.session.lm.initComplete:
                    sleep(0.5)

                self.dispersy = self.session.lm.dispersy
                client._dispersy = self.dispersy

                logging.error("Tribler Session started")
                client.annotate("Tribler Session started")

                return self.session
            except:
                logging.error("Error starting Session: %s" % traceback.format_exc())
                raise

        def __start_dispersy(session):
            try:
                client.original_on_incoming_packets = self.dispersy.on_incoming_packets
                client.post_start_dispersy()
            except:
                logging.error("Error fetching master members: %s" % traceback.format_exc())
                raise

        self.session_deferred = threads.deferToThread(_do_start)
        self.session_deferred.addCallback(__start_dispersy)
        # You may think WUT?! at this point. The __start_dispersy callback ends up doing database work and the callback
        # ensures that it is run on the proper thread (somehow,,,)

    def setup_session_config(self, client):
        from Tribler.Core.SessionConfig import SessionStartupConfig

        config = SessionStartupConfig()
        config.set_install_dir(path.abspath(path.join(self.base_dir, "tribler")))
        config.set_state_dir(path.abspath(path.join(self.base_dir, "output", ".Tribler-%d") % getpid()))
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(False)
        config.set_dispersy(True)
        config.set_mainline_dht(True)
        config.set_torrent_collecting(False)
        config.set_libtorrent(True)
        config.set_dht_torrent_collecting(False)
        config.set_enable_torrent_search(False)
        config.set_enable_channel_search(False)
        config.set_videoserver_enabled(False)
        config.set_listen_port(20000 + client.scenario_runner._peernumber)

        if client.dispersy_port is None:
            client.dispersy_port = 21000 + client.scenario_runner._peernumber
        config.set_dispersy_port(client.dispersy_port)
        logging.error("Dispersy port set to %d" % client.dispersy_port)
        return config

    def stop(self, client, retry=3):
        from twisted.internet import threads

        logging.error("Defer session stop to thread and stop reactor afterwards")
        client.annotate('end of experiment')
        return threads.deferToThread(self.session.shutdown, False).addBoth(lambda _: reactor.callLater(10.0, reactor.stop))

    def stop_dispersy(self, client):
        pass

def main(client_class):
    from gumby.instrumentation import init_instrumentation
    init_instrumentation()
    setupLogging()
    if not environ.get('SELF_SERVICE') is None:
        def expStartedReplacement(_):
            pass
        selfSync = ExperimentServiceFactory(1, 1.0)
        selfSync.onExperimentStarted = expStartedReplacement
        environ['SYNC_HOST'] = "localhost"
        environ['SYNC_PORT'] = "%d" % (22220 + random()*100)
        reactor.listenTCP(int(environ['SYNC_PORT']), selfSync)
    factory = ExperimentClientFactory({}, client_class)
    logger = logging.getLogger()
    logger.debug("Connecting to: %s:%s", environ['SYNC_HOST'], int(environ['SYNC_PORT']))
    # Wait for a random amount of time before connecting to try to not overload the server when we have a lot of connections
    reactor.callLater(random() * 10,
                      lambda: reactor.connectTCP(environ['SYNC_HOST'], int(environ['SYNC_PORT']), factory))
    reactor.exitCode = 0
    reactor.run()
    exit(reactor.exitCode)
