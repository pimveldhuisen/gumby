#!/usr/bin/env python2
# bartercast_client.py ---
#
# Filename: hiddenservices_client.py
# Description:
# Author: Rob Ruigrok
# Maintainer:
# Created: Wed Apr 22 11:44:23 2015 (+0200)

# Commentary:
#
#
#
#

# Change Log:
#
#
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

# Code:

from os import path

from gumby.experiments.dispersymulticlient import MultiDispersyExperimentScriptClient, BASE_DIR
from gumby.experiments.dispersymulticlient import main
import logging
from twisted.internet import reactor
from twisted.python.log import msg
from posix import environ
from time import sleep


class HiddenServicesClient(MultiDispersyExperimentScriptClient):

    def __init__(self, *argv, **kwargs):
        from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
        super(HiddenServicesClient, self).__init__(*argv, **kwargs)
        self.set_community(HiddenTunnelCommunity, name="tunnel")
        self.speed_download = {'download': 0}
        self.speed_upload = {'upload': 0}
        self.progress = {'progress': 0}
        self.security_limiters = False
        self.min_circuits = 3
        self.max_circuits = 5

    def configure_tunnel_community(self, become_exitnode=None, no_crypto=None):
        become_exitnode = become_exitnode == 'exit'
        no_crypto = no_crypto == 'no_crypto'

        from Tribler.community.tunnel.tunnel_community import TunnelSettings
        tunnel_settings = TunnelSettings()

        tunnel_settings.become_exitnode = become_exitnode
        msg("This peer is exit node: %s" % ('Yes' if become_exitnode else 'No'))

        tunnel_settings.socks_listen_ports = [27000 + (10 * self.scenario_runner._peernumber) + i for i in range(5)]

        if not self.security_limiters:
            tunnel_settings.max_traffic = 1024 * 1024 * 1024 * 1024

        tunnel_settings.min_circuits = self.min_circuits
        tunnel_settings.max_circuits = self.max_circuits

        logging.debug("My wan address is %s" % repr(self._dispersy._wan_address[0]))

        msg("Crypto on tunnels: %s" % ('Disabled' if no_crypto else 'Enabled'))
        if no_crypto:
            from Tribler.community.tunnel.crypto.tunnelcrypto import NoTunnelCrypto
            tunnel_settings.crypto = NoTunnelCrypto()

        self.set_community_kwarg('tribler_session', self.session, name="tunnel")
        self.set_community_kwarg('settings', tunnel_settings, name="tunnel")

    @property
    def tunnel_community(self):
        return self.experiment_communities["tunnel"].community

    @property
    def my_member_key_curve(self):
        return u"curve25519"

    def modify_config(self, config):
        # We want to create our own community
        config.set_tunnel_community_enabled(False)
        config.set_anon_listen_port(27000 + self.scenario_runner._peernumber * 10)
        return config

    def log_progress_stats(self, ds):
        new_speed_download = {'download': ds.get_current_speed('down')}
        self.speed_download = self.print_on_change("speed-download",
                                                   self.speed_download,
                                                   new_speed_download)

        new_progress = {'progress': ds.get_progress() * 100}
        self.progress = self.print_on_change("progress-percentage",
                                             self.progress,
                                             new_progress)

        new_speed_upload = {'upload': ds.get_current_speed('up')}
        self.speed_upload = self.print_on_change("speed-upload",
                                                 self.speed_upload,
                                                 new_speed_upload)

    def fake_create_introduction_point(self, info_hash):
        msg("Fake creating introduction points, to prevent this download from messing other experiments")
        pass


    def online(self, dont_empty=False):
        super(HiddenServicesClient, self).online(dont_empty)
        if not self.session is None:
            self.session.set_anon_proxy_settings(2, ("127.0.0.1", self.session.get_tunnel_community_socks5_listen_ports()))

            def monitor_downloads(dslist):
                self.tunnel_community.monitor_downloads(dslist)
                return (1.0, [])
            self.session.set_download_states_callback(monitor_downloads, False)

    def introduce_candidates(self):
        # We are letting dispersy deal with addins the community's candidate to itself.
        from Tribler.dispersy.candidate import Candidate
        for i in range(len(self.all_vars)):
            port = 21000 + i + 1
            if self.dispersy_port != port:
                print "Introducing.."
                self.tunnel_community.add_discovered_candidate(Candidate(("127.0.0.1", port),
                                                                   tunnel=False))
                print "Tunnel Community now has " + str(sum(1 for _ in self.tunnel_community.dispersy_yield_candidates())) + " candidates"

    def set_security_limiters(self, value):
        self.security_limiters = value == 'True'

    def create_tdef(self, file_name="", file_size=100 * 1024 * 1024):
        from Tribler.Core.TorrentDef import TorrentDef
        tdef = TorrentDef()
        download_file = path.join(BASE_DIR, "output", str(self.scenario_file) + "-" + file_name + "-download_file")
        if not path.exists(download_file):
            with open(download_file, 'wb') as fp:
                fp.write("0" * file_size)
        tdef.add_content(download_file)
        tdef.set_tracker("http://fake.net/announce")
        tdef.finalize()
        tdef_file = path.join(BASE_DIR, "output", str(file_name) + ".torrent")
        if not path.exists(tdef_file):
            tdef.save(tdef_file)
        return tdef

    def start_seeder(self, file_name, hops=0):
        hops = int(hops)
        tdef = self.create_tdef(file_name)
        self.annotate('start seeding %d hop(s)' % hops)

        msg("Start seeding")
        print "Hello I am a seeder an my listen port is: " + str(self.session.get_listen_port())

        from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()
        dscfg.set_dest_dir(path.join(BASE_DIR, "output"))
        dscfg.set_hops(hops)
        dscfg.set_safe_seeding(False)

        def cb(ds):
            from Tribler.Core.simpledefs import dlstatus_strings
            msg('Seed infohash=%s, hops=%d, down=%d, up=%d, progress=%s, status=%s, peers=%s, cand=%d' %
                          (tdef.get_infohash().encode('hex')[:5],
                           hops,
                           ds.get_current_speed('down'),
                           ds.get_current_speed('up'),
                           ds.get_progress(),
                           dlstatus_strings[ds.get_status()],
                           sum(ds.get_num_seeds_peers()),
                           sum(1 for _ in self.tunnel_community.dispersy_yield_verified_candidates())))

            self.log_progress_stats(ds)

            return 1.0, False

        download = self.session.start_download_from_tdef(tdef, dscfg)
        download.set_state_callback(cb, getpeerlist=True)

    def start_download(self, file_name, hops=1):
        hops = int(hops)
        self.annotate('start downloading %d hop(s)' % hops)
        from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()
        dscfg.set_hops(hops)
        dscfg.set_dest_dir(path.join(BASE_DIR, 'tribler', 'download-%s-%d' % (self.session.get_dispersy_port(), hops)))
        dscfg.set_safe_seeding(False)

        # Monkeypatch! Disable creating intropoints after finishing downloading
        self.tunnel_community.create_introduction_point = self.fake_create_introduction_point

        from Tribler.Core.simpledefs import dlstatus_strings
        tdef = self.create_tdef(file_name)

        def cb(ds):
            msg('Download infohash=%s, hops=%d, down=%s, up=%d, progress=%s, status=%s, peers=%s, cand=%d' %
                (tdef.get_infohash().encode('hex')[:5],
                 hops,
                 ds.get_current_speed('down'),
                 ds.get_current_speed('up'),
                 ds.get_progress(),
                 dlstatus_strings[ds.get_status()],
                 sum(ds.get_num_seeds_peers()),
                 sum(1 for _ in self.tunnel_community.dispersy_yield_verified_candidates())))

            self.log_progress_stats(ds)
            if ds.get_status() == 3 and sum(ds.get_num_seeds_peers()) == 0:
                print "Connecting to peers"
                self.connect_to_peers(download)
            return 1.0, False

        download = self.session.start_download_from_tdef(tdef, dscfg)
        download.set_state_callback(cb, getpeerlist=True)

        # Force lookup
        # sleep(10)
        # msg("Do a manual dht lookup call to bootstrap it a bit")
        # self.tunnel_community.do_dht_lookup(tdef.get_infohash())

        # self.session.lm.threadpool.call_in_thread(0, cb_start_download)

    def connect_to_peers(self, download):
        #for i in range(len(self.all_vars)):
        i = 0
        port = 20001 + i
        if port != self.session.get_listen_port():
            print "Adding peer at port:" + str(port)
            download.handle.connect_peer(("127.0.0.1", port), 0)

    def registerCallbacks(self):
        super(HiddenServicesClient, self).registerCallbacks()
        self.scenario_runner.register(self.start_seeder, 'start_seeder')
        self.scenario_runner.register(self.start_download, 'start_download')
        self.scenario_runner.register(self.configure_tunnel_community, 'configure_tunnel_community')
        self.scenario_runner.register(self.set_security_limiters, 'set_security_limiters')
        self.scenario_runner.register(self.introduce_candidates, 'introduce_candidates')

if __name__ == '__main__':
    HiddenServicesClient.scenario_file = environ.get('SCENARIO_FILE', 'hiddenservices-1-hop-seeder.scenario')
    main(HiddenServicesClient)
