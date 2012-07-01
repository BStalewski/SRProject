import socket
import SocketServer
import os
import sys
import threading
import simplejson as json
from ConfigParser import ConfigParser
from collections import deque

from refactored_db import DB

from clock import Clock

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
        self.logger.debug('Message from %s' % (self.client_address[0] + ':' + self.client_address[1]))
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
        while True:
            if msg['type'] == 'END':
                strAddr = self.client_address[0] + ':' + str(self.client_address[1])
                self.logger.debug('Connection closed with %s' % strAddr)
                return
            elif msg['type'] == 'GET':
                response = {
                    'type' : 'RGET',
                    'name' : msg['name'],
                    'value': self.handle_get( msg['name'] )
                }
            elif msg['type'] == 'SET':
                print '************* BEGIN SET **************'
                self.state.clock.print_state()
                self.handle_set( msg['name'], msg['value'] )
                response = {
                    'type': 'OK'
                }
                my_vec = self.state.clock.get_vector()
                # only here staring a new thread should be made
                # in other connections client won't be blocked unnecessarily
                replicate_thread = threading.Thread( target=thread_replicate, args=(self, msg['name'], msg['value'], my_vec) )
                replicate_thread.start()
                #self.replicate( msg['name'], msg['value'], my_vec )
                self.state.clock.send()
                print '************* END SET ****************'
                self.state.clock.print_state()
            elif msg['type'] == 'GETALL':
                response = {
                    'type': 'RGETALL',
                    'data': self.handle_print()
                }
            elif msg['type'] == 'DELAY':
                self.handle_delay( msg['in'], msg['out'] )
            elif msg['type'] == 'MISS':
                self.handle_miss( msg['in'], msg['out'] )

            if msg['type'] in ['GET', 'SET', 'GETALL']:
                js_response = json.dumps( response )
                sent_size = self.request.send( js_response )
                self.logger.debug('Message sent = %s' % js_response)
                if sent_size == 0:
                    self.logger.error('Unable to connect to client')
                    return

            try:
                data = self.request.recv( self.state.msg_size )
                msg = json.loads( data )
            except:
                self.logger.error('Connection broken')
                return

    def handle_server_connection( self, msg ):
        if msg['type'] == 'SHARE':
            if self.state.in_miss:
                self.logger.debug('In message %s dropped' % msg)
                return
            if self.state.in_delay > 0:
                self.logger.debug('Delaying message %s for %d seconds' % (msg['type'], self.state.in_delay))
                time.sleep( self.state.in_delay )

            if self.find_in_buffer( msg['clocks'], msg['sender'] ):
                self.logger.debug('Share msg from the same sender %d in the buffer, ignoring it' % msg['sender'])
                return

            print '************* BEGIN SHARE **************'
            self.state.clock.print_state()
            if self.is_msg_refusable( msg ):
                self.logger.debug('Sender %d has bad clock' % msg['sender'])
                response = {
                    'type'  : 'REFUSE',
                    'sender': self.state.my_nr,
                    'clocks': msg['clocks']
                }
                self.send_to_server( response, nr=msg['sender'] )
            else:
                need_help = msg['clocks'] > self.state.clock.get_vector()
                if need_help:
                    response = {
                        'type'  : 'HELP',
                        'clocks': self.state.clock.get_vector()
                    }
                    new_sock = self.send_to_server( response, nr=msg['sender'], resp=True )
                    self.logger.debug('Help sent to %d with clocks %s' % (msg['sender'], response['clocks']))
                    data = new_sock.recv( self.state.msg_size )
                    resp_msg = json.loads( data )
                    if resp_msg['type'] != 'FILLUP':
                        return
                    
                    self.logger.debug('Fillup received from %d with msgs = %s' % (msg['sender'], resp_msg['msgs']))
                    time.sleep( self.state.in_delay )
                    self.update( resp_msg['msgs'] )

                else:
                    self.logger.debug('Sender %d has correct clock' % msg['sender'])
                    self.update_clock( msg )
                    self.update_buffer( msg )
                    self.handle_set( msg['name'], msg['value'] )

            print '************* END SHARE ****************'
            self.state.clock.print_state()
        elif msg['type'] == 'REFUSE':
            self.logger.debug('Refuse from %d with clocks %s' % (msg['sender'], msg['clocks']))
            #refuseClocks = msg['clocks']
            if not self.find_in_buffer( msg['clocks'], self.state.my_nr ):
                return
            refused_msg = self.get_from_buffer( msg['clocks'], self.state.my_nr )

            self.state.clock.refuse()

            response = {
                'type'  : 'HELP',
                'clocks': self.state.clock.get_vector()
            }
            new_sock = self.send_to_server( response, nr=msg['sender'], resp=True )
            self.logger.debug('Help sent to %d with clocks %s' % (msg['sender'], response['clocks']))
            data = new_sock.recv( self.state.msg_size )
            resp_msg = json.loads( data )
            if resp_msg['type'] != 'FILLUP':
                return
            
            self.logger.debug('Fillup received from %d with msgs = %s' % (msg['sender'], resp_msg['msgs']))
            time.sleep( self.state.in_delay )
            self.update( resp_msg['msgs'], refuse=True )

            my_vec = self.state.clock.get_vector()
            self.handle_set( refused_msg['name'], refused_msg['value'] )
            self.replicate( refused_msg['name'], refused_msg['value'], my_vec )

        elif msg['type'] == 'HELP':
            self.logger.debug('Help received from %s with clocks = %s' % (self.request, msg['clocks']))
            msgs = self.get_help_messages( msg )
            print 'HELP MESSAGES:', msgs
            response = {
                'type': 'FILLUP',
                'msgs': msgs
            }
            self.send_to_server( response, sock=self.request )
            self.logger.debug('Fillup sent to %s with msgs: %s' % (self.request, response['msgs']))

    def send_to_server( self, msg, nr=None, sock=None, resp=False ):
        js_msg = json.dumps( msg )

        if sock is None:
            ip, str_port = self.state.addresses[ nr ]
            port = int(str_port)
            sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
            try:
                sock.connect( (ip, port) )
            except:
                return

        try:
            sock.send( js_msg )
            if resp:
                return sock
        except Exception as e:
            print 'Error during help messages'
            print e

    def replicate( self, name, value, vec ):
        rep_msg = {
            'type'  : 'SHARE',
            'sender': self.state.my_nr,
            'clocks': vec,
            'name'  : name,
            'value' : value
        }
        self.update_buffer( rep_msg )

        if self.state.out_miss:
            self.logger.debug('Out message replicate %s dropped' % rep_msg)
            return
        if self.state.out_delay > 0:
            self.logger.debug('Delaying out replicate message for %d seconds' % self.state.out_delay)
            time.sleep( self.state.out_delay )

        for i in range( len(self.state.addresses) ):
            if i == self.state.my_nr:
                continue
            self.send_to_server( rep_msg, nr=i )
            self.logger.debug('Replication with clocks = %s sent to %d' % (vec, i))

    def update_clock( self, msg ):
        self.state.clock.recv( msg['sender'], msg['clocks'][:] )

    def can_be_removed( self, msg, col ):
        nr = msg['sender']
        print 'Trying to remove msg from the buffer'
        print 'Sender column in my column:', col, 'Sender nr:', nr, 'Msg clocks:', msg['clocks']
        print 'Checking if min(col) > msg[clocks][nr] :: ', min(col), '>', msg['clocks'][nr]
        return min( col ) > msg['clocks'][nr] 

    def is_msg_refusable( self, msg ):
        my_vec = self.state.clock.get_vector()
        for (i, msg_time) in enumerate(msg['clocks']):
            if msg_time < my_vec[i]:
                return True

        return False

    def update_buffer( self, msg ):
        def is_not_needed( m ):
            sender  = m['sender']
            return self.can_be_removed( m, self.state.clock.getColumn( sender ) )

        self.state.msg_buffer.append( msg )
        to_remove = [ i for (i, m) in enumerate(self.state.msg_buffer) if is_not_needed( m ) ]
        to_remove.reverse()

        for i in to_remove:
            self.logger.debug('Message discarded')
            del self.state.msg_buffer[ i ]

        self.logger.debug( '%d remaining message(s) in the buffer' % len(self.state.msg_buffer) )

    def remove_from_buffer( self, clocks, sender ):
        self.get_from_buffer( clocks, sender )

    def find_in_buffer( self, clocks, sender ):
        for msg in self.state.msg_buffer:
            if msg['clocks'] == clocks and msg['sender'] == sender:
                return True

        return False

    def get_from_buffer( self, clocks, sender ):
        foundMsg = None
        for (i, msg) in enumerate(self.state.msg_buffer):
            if msg['clocks'] == clocks and msg['sender'] == sender:
                foundMsg = msg

        if foundMsg:
            self.state.msg_buffer.remove( foundMsg )
            return foundMsg
        else:
            return None

    def update( self, msgs ):
        for msg in msgs:
            if self.is_msg_refusable( msg ):
                raise RuntimeError('Bad clock detected in update')

            self.update_clock( msg )
            self.update_buffer( msg )
            self.handle_set( msg['name'], msg['value'] )

    def get_help_messages( self, msg ):
        msgs = []
        my_vec = self.state.clock.get_vector()

        for i in range( len( self.state.addresses ) ):
            missing = my_vec[i] - msg['clocks'][i]
            if missing > 0:
                msgs += filter( lambda m: m['sender'] == i, self.state.msg_buffer )[:missing]

        return msgs

    def handle_get( self, name ):
        self.logger.debug('GET from db: %s' % name)
        return self.state.db.get_value( name )

    def handle_set( self, name, value ):
        self.logger.debug('SET in db: %s = %d' % (name, value))
        self.state.db.set_value( name, value )

    def handle_print( self ):
        self.logger.debug('GET all vars')
        return self.state.db.get_all()

    def handle_delay( self, in_delay, out_delay ):
        self.state.in_delay = in_delay
        self.state.out_delay = out_delay
        self.logger.debug('Updated delay: in delay = %s, out delay = %s' % (in_delay, out_delay))

    def handle_miss( self, in_miss, out_miss ):
        self.state.in_miss = in_miss
        self.state.out_miss = out_miss
        self.logger.debug('Updated miss: in miss = %s, out miss = %s' % (in_miss, out_miss))

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
        self._msg_buffer = deque()

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

    # TODO: clean up
    #server = Server( addr_file, ip, port )
    #server.start()

    server_address = (ip, port)
    server = SRServer( addr_file, db_file, server_address, SRRequestHandler )
    #server = SocketServer.TCPServer( server_address, SRRequestHandler )
    server.serve_forever()


