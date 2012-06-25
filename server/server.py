import socket
import os
import sys
import simplejson as json
from ConfigParser import ConfigParser

import common
from db import DB

from clock import Clock

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

    def readAddrFile( self, addrFile ):
        parser = ConfigParser()
        parser.read( addrFile )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print 'Read addresses from the addr file:'
        for (i, (ip, port)) in enumerate( addresses, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

        return addresses

    def findMyIndex( self, addresses, myIp, myPort ):
        '''
        if os.name == 'nt':
            myIps = socket.gethostbyname_ex(socket.gethostname())[2]
        else:
            myIps = findLinuxIps()
        for ip in myIps:
            addr = [ip, str(myPort)]
            try:
                index = addresses.index(addr)
            except ValueError:
                continue
            else:
                return index

        raise RuntimeError("None of server ips ( %s ), port %s, is in addr list ( %s )" % (myIps, myPort, addresses))
        '''
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
        #s.bind( ('127.0.0.1', 4321) )
        s.bind( (self.ip, self.port) )
        s.listen( self.maxConnections )
        print '[SERVER] Listening on IP = %s, port = %s' % (self.ip, self.port)

        while True:
            (csocket, adr) = s.accept()
            while True:
                print '[SERVER] Connection from', adr
                try:
                    request = csocket.recv(self.msgSize)
                except:
                    print '[SERVER ERROR] Connection broken'
                else:
                    msg = self.decodeRequest( request )
                    print '[SERVER] Message received =', msg

                    if msg['type'] == 'END':
                        csocket.shutdown( socket.SHUT_RDWR )
                        csocket.close()
                        print '[SERVER] Connection closed with', adr
                        break
                    elif msg['type'] == 'DELAY':
                        setDelay(msg['in'], msg['out'])
                        break
                    elif msg['type'] == 'MISS':
                        setMiss(msg['miss'])
                        break

                    response = self.prepareResponse( msg )
                    filledResponse = common.fillOutMsg( response, self.msgSize )
                    
                    sentSize = csocket.send( filledResponse )
                    print '[SERVER] Message sent =', response
                    if sentSize == 0:
                        print '[SERVER ERROR] Unable to connect to client'


    def decodeRequest( self, request ):
        jsonRequest = request.rstrip('#')
        return json.loads( jsonRequest )

    def prepareResponse( self, msg ):
        result = self.handleConnection( msg )
        if msg['type'] == 'GET':
            response = {
                'name': msg['name'],
                'value': result
            }
        elif msg['type'] == 'SET':
            response = {
                'name': msg['name'],
                'value': msg['value'],
            }
        elif msg['type'] == 'DEL':
            response = {
                'name': msg['name'],
                'deleted': result
            }
        elif msg['type'] == 'GETALL':
            response = {
                'data': result
            }
        else:
            raise RuntimeError('Unknown message type %s' % msg['type'])

        response['type'] = msg['type']
        return json.dumps( response )

    def handleConnection( self, msg ):
        oper = msg.get( 'type' )
        if oper == 'GET':
            return self.handleGet( msg['name'] )
        elif oper == 'SET':
            self.handleSet( msg['name'], msg['value'] )
        elif oper == 'DEL':
            return self.handleDel( msg['name'] )
        elif oper == 'GETALL':
            return self.handlePrint()
        else:
            raise RuntimeError('Unknown operation type %s' % oper)

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

    def setDelay( self, inDelay, outDelay ):
        self.inDelay = inDelay
        self.outDelay = outDelay
        print '[SERVER] In delay = %s, out delay = %s', (inDelay, outDelay)

    def setMiss( self, miss ):
        self.miss = miss
        print '[SERVER] Miss = %s', miss


class Clock:
    def __init__( self, nr ):


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

