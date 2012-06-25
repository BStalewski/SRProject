import socket
import os
import sys
import simplejson as json
from ConfigParser import ConfigParser
from collections import deque

import common
from db import DB

from clock import Clock

import time

class Server:
    def __init__( self, addrFile, ip, port, msgSize=100, maxConn=5 ):
        self.addresses = self.readAddrFile( addrFile )
        self.ip = ip
        self.port = port
        self.myNr = self.findMyIndex( self.addresses, self.ip, self.port )
        self.msgSize = msgSize
        self.db = DB()
        self.maxConnections = maxConn
        self.inDelay = 0
        self.outDelay = 0
        self.miss = False
        self.clock = Clock(self.myNr)
        self.msgBuffer = deque()

    def readAddrFile( self, addrFile ):
        parser = ConfigParser()
        parser.read( addrFile )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print 'Read addresses from the addr file:'
        for (i, (ip, port)) in enumerate( addresses, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

        return addresses

    def findMyIndex( self, addresses, myIp, myPort ):
        addr = [myIp, str(myPort)]
        try:
            index = addresses.index(addr)
        except ValueError:
            raise RuntimeError('Server address %s not in available addresses: %s' \
                                % (addr, addresses))
        else:
            return index


    def start( self ):
        print '[SERVER] Starting server'
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print '[SERVER] Socket created'
        s.bind( (self.ip, self.port) )
        s.listen( self.maxConnections )
        print '[SERVER] Listening on IP = %s, port = %s' % (self.ip, self.port)

        while True:
            (csocket, addr) = s.accept()
            print '[SERVER] Connection from', addr
            self.handleConnection( csocket, addr )

    def handleConnection( self, csocket, addr )
        try:
            request = csocket.recv( self.msgSize )
            time.sleep( self.inDelay )
        except:
            print '[SERVER ERROR] Connection broken'
            return

        msg = self.decodeRequest( request )
        if msg['type'] not in ['DELAY', 'MISS'] and self.inDelay > 0:
            print '[SERVER] Delaying message for %d seconds' % self.inDelay
            time.sleep(self.inDelay)

        print '[SERVER] Message received =', msg
        if self.isClientMsg(msg['type']):
            self.handleClientConnection(csocket, addr, msg)
        elif self.isServerMsg(msg['type']):
            self.handleServerConnection(csocket, addr, msg)
        else:
            raise RuntimeError('Unknown message type: %s' % msg['type'])

    def isClientMsg( self, msgType ):
        return msgType in ['END', 'GET', 'SET', 'GETALL', 'DELAY', 'MISS']

    def isServerMsg( self, msgType ):
        return msgType in ['SHARE', 'REFUSE', 'HELP', 'FILLUP']

    def handleClientConnection( self, sock, addr, msg ):
        while True:
            if msg['type'] == 'END':
                sock.shutdown( socket.SHUT_RDWR )
                sock.close()
                print '[SERVER] Connection closed with', addr
                return
            elif msg['type'] == 'GET':
                response = {
                    'name' : msg['name'],
                    'value': self.handleGet( msg['name'] )
                }
            elif msg['type'] == 'SET':
                response = {
                    'name' : msg['name'],
                    'value': self.handleSet( msg['name'], msg['value'] )
                }
                self.replicate( response )
            elif msg['type'] == 'GETALL':
                response = {
                    'data': self.handlePrint()
                }
            elif msg['type'] == 'DELAY':
                self.handleDelay( msg['in'], msg['out'] )
            elif msg['type'] == 'MISS':
                self.handleMiss( msg['miss'] )

            if msg['type'] in ['GET', 'SET', 'GETALL']:
                response['type'] = msg['type']
                js_response = json.dumps( response )
                filledResponse = common.fillOutMsg( js_response, self.msgSize )
                sentSize = sock.send( filledResponse )
                print '[SERVER] Message sent =', js_response
                if sentSize == 0:
                    print '[SERVER ERROR] Unable to connect to client'
                    return

            try:
                request = sock.recv( self.msgSize )
            except:
                print '[SERVER ERROR] Connection broken'
                return

    def handleServerConnection( self, sock, addr, msg ):
        if msg['type'] == 'SHARE':
            badClockDetected = self.isMsgClockOk( msg['clocks'] )
            if badClockDetected:
                # send REFUSE
                pass # TODO
            else:
                self.updateClock( msg ) # TODO
                self.updateBuffer( msg ) # TODO
                self.handleSet( msg['name'], msg['value'] )
        elif msg['type'] == 'REFUSE':
            # send HELP
            pass # TODO
        elif msg['type'] == 'HELP':
            # send FILLUP
            pass # TODO
        elif msg['type'] == 'FILLUP':
            # apply FILLUP
            pass # TODO

    def isMsgClockOk( self, clocks ):
        

    def replicate( self, msg ):
        # get clock, send to others
        pass # TODO

    def decodeRequest(self, request):
        jsonRequest = request.rstrip('#')
        return json.loads( jsonRequest )


    def handleGet( self, name ):
        print 'GET from db %s' % name
        return self.db.getValue( name )

    def handleSet( self, name, value ):
        print 'SET in db %s = %d' % (name, value)
        self.db.setValue( name, value )

    def handleDel( self, name ):
        print 'DEL in db %s' % name
        if self.db.getValue( name ) is None:
            return False

        self.db.delValue( name )
        return True

    def handlePrint( self ):
        print 'GET all vars to print'
        return self.db.getAll()

    def handleDelay( self, inDelay, outDelay ):
        self.inDelay = inDelay
        self.outDelay = outDelay
        print '[SERVER] In delay = %s, out delay = %s', (inDelay, outDelay)

    def handleMiss( self, miss ):
        self.miss = miss
        print '[SERVER] Miss = %s', miss


def findLinuxIps():
    # solution to get ip in LAN proposed by smerlin on
    # http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    import fcntl
    import struct
    def get_interface_ip(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl( s.fileno(), 0x8915,  # SIOCGIFADDR
                                             struct.pack('256s', ifname[:15]))[20:24])

    ip = socket.gethostbyname(socket.gethostname())
    if not ip.startswith('127.'):
        return [ ip ]
    else:
        myIps = []
        interfaces = ['eth0','eth1','eth2','wlan0','wlan1','wifi0','ath0','ath1','ppp0']
        for ifname in interfaces:
            try:
                ip = get_interface_ip(ifname)
            except IOError:
                pass
            else:
                myIps.append( ip )
        return myIps

if __name__ == '__main__':
    topDir = os.path.dirname( os.getcwd() )
    addrFile = os.path.join(topDir, 'addr.txt')
    try:
        ip = sys.argv[1]
        port = int( sys.argv[2] )
    except (IndexError, ValueError):
        ip = '127.0.0.1'
        port = 4321
        print 'No ip/port specified, using default value: %s:%d', (ip, port)

    server = Server( addrFile, ip, port )
    server.start()

