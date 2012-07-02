import socket
import SocketServer
import os
import sys
import threading
import simplejson as json
from ConfigParser import ConfigParser

from refactored_db import DB
from message_buffer import MessageBuffer

from refactored_clock import Clock

import time
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )

def thread_replicate( handler, var_name, var_value, sender_vec ):
    handler.replicate( var_name, var_value, sender_vec )

class SRRequestHandler(SocketServer.BaseRequestHandler):
    def __init__(self, request, client_address, server):
        self.logger = logging.getLogger('[SERVER]')
        self.state = server.getState()
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        data = self.request.recv( self.state.msg_size )
        msg = json.loads( data )
        
        self.logger.debug('Message received = %s' % msg)
        self.logger.debug( 'Message from %s' % (self.client_address[0] + ':' + str(self.client_address[1])) )
        if self.is_client_msg( msg['type'] ):
            self.handle_client_connection( msg )
        elif self.is_server_msg( msg['type'] ):
            self.handle_server_connection( msg )
        else:
            raise RuntimeError('Unknown message type: %s' % msg['type'])

    def is_client_msg( self, msg_type ):
        return msg_type in ['END', 'GET', 'SET', 'GETALL', 'DELAY', 'MISS']

    def is_server_msg( self, msg_type ):
        return msg_type in ['SHARE', 'REFUSE', 'HELP', 'FILLUP']

    def handle_client_connection( self, msg ):
        want_recv = True
        while want_recv:
            if msg['type'] == 'END':
                self.handle_end()
                want_recv = False
            elif msg['type'] == 'GET':
                want_recv = self.handle_get( msg )
            elif msg['type'] == 'SET':
                want_recv = self.handle_set( msg )
            elif msg['type'] == 'GETALL':
                want_recv = self.handle_print()
            elif msg['type'] == 'DELAY':
                want_recv = self.handle_delay( msg )
            else: # msg['type'] == 'MISS'
                want_recv = self.handle_miss( msg )

            if want_recv:
                try:
                    data = self.request.recv( self.state.msg_size )
                    msg = json.loads( data )
                except:
                    self.logger.error('Connection with client %s broken' % self.client_address[0])
                    want_recv = False

    ''' CLIENT MESSAGES
        handle messages return True if they ended with no errors, otherwise False'''

    def handle_end( self ):
        strAddr = self.client_address[0] + ':' + str(self.client_address[1])
        self.logger.debug('Connection closed with %s' % strAddr)
        return True

    def handle_get( self, msg ):
        response_msg = {
            'type' : 'RGET',
            'name' : msg['name'],
            'value': self.state.db.get_value( msg['name'] )
        }
        self.logger.debug('GET from db: %s' % msg['name'])
        return self.send_response( response_msg ) > 0

    def handle_set( self, msg ):
        self.logger.debug('************* BEGIN SET **************')
        self.state.clock.print_state()

        self.state.db.set_value( msg['name'], msg['value'] )
        self.logger.debug('SET in db: %s = %d' % (msg['name'], msg['value']))

        response_msg = {
            'type': 'OK'
        }
        sent_size = self.send_response( response_msg )

        # only here staring a new thread should be made
        # in other connections client won't be blocked unnecessarily
        my_vec = self.state.clock.get_vector()
        replicate_thread = threading.Thread( target=thread_replicate, args=(self, msg['name'], msg['value'], my_vec) )
        replicate_thread.start()
        self.state.clock.send()

        self.logger.debug('************* END SET ****************')
        self.state.clock.print_state()

        return sent_size > 0

    def handle_print( self ):
        response_msg = {
            'type': 'RGETALL',
            'data': self.state.db.get_all()
        }
        self.logger.debug('GET all vars')
        return self.send_response( response_msg ) > 0

    def handle_delay( self, msg ):
        self.state.in_delay = msg['in']
        self.state.out_delay = msg['out']
        self.logger.debug('Updated delay: in delay = %s, out delay = %s' % (msg['in'], msg['out']))
        return True

    def handle_miss( self, msg ):
        self.state.in_miss = msg['in']
        self.state.out_miss = msg['out']
        self.logger.debug('Updated miss: in miss = %s, out miss = %s' % (msg['in'], msg['out']))
        return True

    def send_response( self, response_msg ):
        js_response = json.dumps( response_msg )
        sent_size = self.request.send( js_response )
        if sent_size == 0:
            self.logger.error('Unable to connect to client')
        else:
            self.logger.debug('Message sent = %s' % js_response)
        return sent_size

    ''' SERVER MESSAGES
        handle messages return True if they ended with no errors, otherwise False'''

    def handle_server_connection( self, msg ):
        if msg['type'] == 'SHARE':
            self.handle_share( msg )
        elif msg['type'] == 'REFUSE':
            self.handle_refuse( msg )
        else: # msg['type'] == 'HELP'
            self.handle_help( msg )

    def handle_share( self, msg ):
        if self.simulate_failures( msg, 'in' ):
            return

        if self.state.msg_buffer.is_in_buffer( msg['clocks'], msg['sender'] ):
            self.logger.debug('Share msg from the same sender %d in the buffer, ignoring it' % msg['sender'])
            return

        if self.is_msg_refusable( msg ):
            self.logger.debug('Share sender %d has bad clock' % msg['sender'])
            response = {
                'type'  : 'REFUSE',
                'sender': self.state.my_nr,
                'clocks': msg['clocks']
            }
            self.send_to_server( response, nr=msg['sender'] )
        else:
            need_help = msg['clocks'] > self.state.clock.get_vector()
            if need_help:
                self.request_for_help_messages( msg )
            else:
                # msg['clocks'] == self.state.clock.get_vector()
                self.logger.debug('************* BEGIN SHARE **************')
                self.state.clock.print_state()
                self.logger.debug('Share sender %d has correct clock' % msg['sender'])
                self.update_clock( msg )
                self.state.msg_buffer.update( msg, self.state.clock )

                self.logger.debug('SET in db: %s = %d' % (msg['name'], msg['value']))
                self.state.db.set_value( msg['name'], msg['value'] )
                self.state.clock.print_state()
                self.logger.debug('************* END SHARE ****************')

    def handle_refuse( self, msg ):
        self.logger.debug('Refuse from %d with clocks %s' % (msg['sender'], msg['clocks']))
        if not self.state.msg_buffer.is_in_buffer( msg['clocks'], self.state.my_nr ):
            return

        refused_msg = self.state.msg_buffer.get_message( msg['clocks'], self.state.my_nr )
        self.state.clock.refuse()

        help_correct = self.request_for_help_messages( msg )
        if help_correct:
            my_vec = self.state.clock.get_vector()
            self.logger.debug('SET in db: %s = %d' % (refused_msg['name'], refused_msg['value']))
            self.state.db.set_value( refused_msg['name'], refused_msg['value'] )
            self.replicate( refused_msg['name'], refused_msg['value'], my_vec )

    def handle_help( self, msg ):
        self.logger.debug('Help request received from %s with clocks = %s' % (self.request, msg['clocks']))
        msgs = self.get_help_messages( msg )
        self.logger.debug('Sending help messages %s' % msgs)
        response = {
            'type': 'FILLUP',
            'msgs': msgs
        }
        self.send_to_server( response, sock=self.request )
        self.logger.debug('Fillup sent to %s with msgs: %s' % (self.request, response['msgs']))

    def request_for_help_messages( self, msg ):
        self.logger.debug('I need help from sender %d' % msg['sender'])
        help_msg = {
            'type'  : 'HELP',
            'clocks': self.state.clock.get_vector()
        }
        new_sock = self.send_to_server( help_msg, nr=msg['sender'], resp=True )
        self.logger.debug('Help sent to %d with clocks %s' % (msg['sender'], help_msg['clocks']))

        data = new_sock.recv( self.state.msg_size )
        fillup_msg = json.loads( data )
        if fillup_msg['type'] != 'FILLUP':
            self.logger.debug('Received wrong response for help %s, ignoring it' % fillup_msg)
            return False
        
        self.logger.debug('Fillup received from %d with msgs = %s' % (msg['sender'], fillup_msg['msgs']))
        # TODO: fillup delay&miss
        failure = self.simulate_failures( fillup_msg, 'in' )
        if failure:
            return False
        else:
            self.update( fillup_msg['msgs'] )
            return True

    def simulate_failures( self, msg, direction='in' ):
        is_miss = self.state.in_miss if direction == 'in' else self.state.out_miss
        delay = self.state.in_delay if direction == 'in' else self.state.out_delay
        if is_miss:
            self.logger.debug('DROPPED message %s' % msg)
            return True
        else:
            if delay > 0:
                self.logger.debug('DELAYING message %s for %d seconds' % (msg['type'], self.state.in_delay))
                time.sleep( delay )
            return False

    def send_to_server( self, msg, nr=None, sock=None, resp=False ):
        js_msg = json.dumps( msg )

        if sock is None:
            ip, str_port = self.state.addresses[ nr ]
            port = int(str_port)
            sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
            try:
                sock.connect( (ip, port) )
            except:
                self.logger.error('Unable to connect to server %s:%s' % (ip, str_port))
                return

        try:
            sock.send( js_msg )
            if resp:
                return sock
        except Exception as e:
            self.logger.error('Error during help messages: %s' % e)

    def replicate( self, name, value, vec ):
        rep_msg = {
            'type'  : 'SHARE',
            'sender': self.state.my_nr,
            'clocks': vec,
            'name'  : name,
            'value' : value
        }
        self.state.msg_buffer.update( rep_msg, self.state.clock )

        if self.simulate_failures( rep_msg, 'out' ):
            return

        others_numbers = filter( lambda n: n != self.state.my_nr,
                                 range( len(self.state.addresses) ) )
        for i in others_numbers:
            self.send_to_server( rep_msg, nr=i )
            self.logger.debug('Replication with clocks = %s sent to %d' % (vec, i))

    def update_clock( self, msg ):
        self.state.clock.recv( msg['sender'], msg['clocks'][:] )

    def is_msg_refusable( self, msg ):
        # not normal share and i dont need help
        my_vec = self.state.clock.get_vector()
        return msg['clocks'] != my_vec and not msg['clocks'] > my_vec

    def update( self, msgs ):
        for msg in msgs:
            if self.is_msg_refusable( msg ):
                raise RuntimeError('Bad clock detected in update')

            self.update_clock( msg )
            self.state.msg_buffer.update( msg, self.state.clock )
            self.logger.debug('SET in db: %s = %d' % (msg['name'], msg['value']))
            self.state.db.set_value( msg['name'], msg['value'] )

    def get_help_messages( self, msg ):
        msgs = []
        my_vec = self.state.clock.get_vector()

        for i in range( len( self.state.addresses ) ):
            missing = my_vec[i] - msg['clocks'][i]
            msgs += self.state.msg_buffer.get_last_messages( i, missing )

        return msgs


class SRServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    
    def __init__(self, addr_file, db_file, server_address, handler_class, msg_size=10000):
        addresses = self.read_addr_file( addr_file )
        self.state = ServerState( addresses, db_file, server_address, msg_size )
        SocketServer.TCPServer.__init__(self, server_address, handler_class)

    def read_addr_file( self, addr_file ):
        parser = ConfigParser()
        parser.read( addr_file )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print 'Read addresses from the addr file:'
        for (i, (ip, port)) in enumerate( addresses, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

        return addresses

    def getState( self ):
        return self.state

class ServerState(object):
    def __init__( self, addresses, db_file, server_address, msg_size, init_clocks=True ):
        self._addresses = addresses
        self._ip, self._port = server_address
        self._my_nr = self.find_nr( self._ip, self._port )
        self._msg_size = msg_size
        self._db = DB( filename=db_file )
        self._in_delay = 0
        self._out_delay = 0
        self._in_miss = False
        self._out_miss = False
        if init_clocks:
            self._clock = Clock( self._my_nr, len(addresses) )
        else:
            try:
                self._clock = self._db.getClocks()
            except IOError:
                print 'Error: cannot load clocks from file, initiating'
                self._clock = Clock( self._my_nr, len(addresses) )
        self._msg_buffer = MessageBuffer()

    def get_addresses( self ):
        return self._addresses
    addresses = property( get_addresses )

    def get_ip( self ):
        return self._ip
    ip = property( get_ip )

    def get_port( self ):
        return self._port
    port = property( get_port )

    def get_my_nr( self ):
        return self._my_nr
    my_nr = property( get_my_nr )

    def get_msg_size( self ):
        return self._msg_size
    msg_size = property( get_msg_size  )

    def get_db( self ):
        return self._db
    db = property( get_db )

    def get_in_delay( self ):
        return self._in_delay
    def set_in_delay( self, value ):
        self._in_delay = value
    in_delay = property( get_in_delay, set_in_delay )

    def get_out_delay( self ):
        return self._out_delay
    def set_out_delay( self, value ):
        self._out_delay = value
    out_delay = property( get_out_delay, set_out_delay )

    def get_in_miss( self ):
        return self._in_miss
    def set_in_miss( self, value ):
        self._in_miss = value
    in_miss = property( get_in_miss, set_in_miss )

    def get_out_miss( self ):
        return self._out_miss
    def set_out_miss( self, value ):
        self._outmiss = value
    out_miss = property( get_out_miss, set_out_miss )

    def get_clock( self ):
        return self._clock
    def set_clock( self, clock ):
        self._clock = clock
    clock = property( get_clock, set_clock )

    def get_msg_buffer( self ):
        return self._msg_buffer
    msg_buffer = property( get_msg_buffer )

    def find_nr( self, ip, port ):
        addr = [ip, str(port)]
        try:
            return self._addresses.index(addr)
        except ValueError:
            raise RuntimeError('Server address %s not in available addresses: %s' \
                                % (addr, self._addresses))

    def clock_send( self ):
        self.clock.send()
        self.db.save_clocks( self.clock )

    def clock_recv( self, senderNr, clockVec ):
        self.clock.recv( senderNr, clockVec )
        self.db.save_clocks( self.clock )


if __name__ == '__main__':
    top_dir = os.path.dirname( os.getcwd() )
    addr_file = os.path.join(top_dir, 'addr.txt')
    try:
        ip = sys.argv[1]
        port = int( sys.argv[2] )
        db_file = sys.argv[3]
    except (IndexError, ValueError):
        ip = '192.168.1.167'
        port = 4000
        db_file = 'data.db'
        print 'No ip/port specified, using default value: %s:%d', (ip, port)

    server_address = (ip, port)
    server = SRServer( addr_file, db_file, server_address, SRRequestHandler )
    server.serve_forever()


