import socket
import SocketServer
import os
import sys
import simplejson as json
from ConfigParser import ConfigParser
from collections import deque

from db import DB

from clock import Clock

import time
import logging


logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )

class SRRequestHandler(SocketServer.BaseRequestHandler):
    def __init__(self, request, client_address, server):
        self.logger = logging.getLogger('[SERVER]')
        self.state = server.getState()
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        data = self.request.recv( self.state.msgSize )
        msg = json.loads( data )
        
        # TODO: to method
        if msg['type'] not in ['DELAY', 'MISS'] and self.state.inDelay > 0:
            self.logger.debug('Delaying message for %d seconds' % self.state.inDelay)
            #print '[SERVER] Delaying message for %d seconds' % self.state.inDelay
            time.sleep( self.state.inDelay )

        #print '[SERVER] Message received =', msg
        self.logger.debug('Message received = %s' % msg)
        if self.isClientMsg( msg['type'] ):
            self.handleClientConnection( msg )
        elif self.isServerMsg( msg['type'] ):
            self.handleServerConnection( msg )
        else:
            raise RuntimeError('Unknown message type: %s' % msg['type'])

        self.request.send(data)

    def isClientMsg( self, msgType ):
        return msgType in ['END', 'GET', 'SET', 'GETALL', 'DELAY', 'MISS']

    def isServerMsg( self, msgType ):
        return msgType in ['SHARE', 'REFUSE', 'HELP', 'FILLUP']

    def handleClientConnection( self, msg ):
        while True:
            if msg['type'] == 'END':
                #self.request.shutdown( socket.SHUT_RDWR )
                #self.request.close()
                strAddr = self.client_address[0] + ':' + str(self.client_address[1])
                self.logger.debug('Connection closed with %s' % strAddr)
                #print '[SERVER] Connection closed with', self.client_address
                return
            elif msg['type'] == 'GET':
                response = {
                    'name' : msg['name'],
                    'value': self.handleGet( msg['name'] )
                }
            elif msg['type'] == 'SET':
                self.handleSet( msg['name'], msg['value'] )
                response = {
                    'name' : msg['name'],
                    'value': msg['value']
                }
                self.replicate( response )
                self.state.clock.send()
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
                jsResponse = json.dumps( response )
                sentSize = self.request.send( jsResponse )
                self.logger.debug('Message sent = %s' % jsResponse)
                #print '[SERVER] Message sent =', jsResponse
                if sentSize == 0:
                    self.logger.error('Unable to connect to client')
                    #print '[SERVER ERROR] Unable to connect to client'
                    return

            try:
                data = self.request.recv( self.state.msgSize )
                msg = json.loads( data )
                if msg['type'] not in ['DELAY', 'MISS'] and self.state.inDelay > 0:
                    self.logger.debug('Delaying message for %d seconds' % self.state.inDelay)
                    #print '[SERVER] Delaying message for %d seconds' % self.state.inDelay
                    time.sleep( self.state.inDelay )
            except:
                self.logger.error('Connection broken')
                #print '[SERVER ERROR] Connection broken'
                return

    def handleServerConnection( self, msg ):
        if msg['type'] == 'SHARE':
            badClockDetected = self.state.clock.isSenderEarlier( msg['sender'], msg['clocks'] )
            if badClockDetected:
                response = {
                    'type'  : 'REFUSE',
                    'sender': self.state.myNr
                }
                self.sendToServer( response, nr=msg['sender'] )
            else:
                self.updateClock( msg )
                self.updateBuffer( msg )
                self.handleSet( msg['name'], msg['value'] )

        elif msg['type'] == 'REFUSE':
            response = {
                'type'  : 'HELP',
                'clocks': self.state.clock.getVector()
            }
            newSock = self.sendToServer( response, nr=msg['sender'] )
            data = newSock.recv( self.state.msgSize )
            time.sleep( self.state.inDelay )
            msg = json.loads( data )
            if msg['type'] != 'FILLUP':
                return
            
            self.update( msg['msgs'] )

        elif msg['type'] == 'HELP':
            msgs = self.getHelpMessages( msg )
            response = {
                'type': 'FILLUP',
                'msgs': json.dumps( msgs )
            }
            self.sendToServer( response, sock=self.request )

    def sendToServer( self, msg, nr=0, sock=None, resp=False ):
        jsMsg = json.dumps( msg )

        if sock is None:
            ip, str_port = self.state.addresses[ nr ]
            port = int(str_port)
            sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
            try:
                sock.connect( (ip, port) )
            except:
                return

        try:
            sentSize = sock.send( jsMsg )
            if not resp:
                sock.shutdown( socket.SHUT_RDWR )
                sock.close()
            else:
                return sock
        except:
            pass

    def replicate( self, msg ):
        myVec = self.state.clock.getVector()
        repMsg = {
            'type'  : 'SHARE',
            'sender': self.state.myNr,
            'clocks': myVec,
            'name'  : msg['name'],
            'value' : msg['value']
        }
        for i in range( len(self.state.addresses) ):
            if i == self.state.myNr:
                continue
            self.sendToServer( repMsg, nr=i )

    def updateClock( self, msg ):
        self.state.clock.recv( msg['sender'], msg['clocks'] )

    def canBeRemoved( self, msg, col ):
        nr = msg['sender']
        return min( col ) >= msg['clocks'][nr] 
        #return min( clk.getColumn(nr) ) >= msg['clocks'][nr] 

    def updateBuffer( self, msg ):
        def isNotNeeded( m ):
            sender  = m['sender']
            return self.canBeRemoved( m, self.state.clock.getColumn( sender ) )

        self.state.msgBuffer.append( msg )
        nr = msg['sender']
        toRemove = [ i for (i, m) in enumerate(self.state.msgBuffer) if isNotNeeded( m ) ]
        #toRemove = [i for (i, m) in enumerate(self.msgBuffer) if self.canBeRemoved( m, self.clock.getColumn( nr ) )]
        toRemove.reverse()

        for i in toRemove:
            self.logger.debug('Message discarded')
            #print '[SERVER] Message discarded'
            del self.state.msgBuffer[ i ]

    def update( self, msgs ):
        for msg in msgs:
            badClockDetected = self.state.clock.isSenderEarlier( msg['sender'], msg['clocks'] )
            if badClockDetected:
                raise RuntimeError('Bad clock detected in update')

            self.updateClock( msg )
            self.updateBuffer( msg )
            self.handleSet( msg['name'], msg['value'] )

    def getHelpMessages( self, msg ):
        def isNeeded( m ):
            sender = m['sender']
            return not self.canBeRemoved( m, [ msg['clocks'][sender] ] )

        return filter( isNeeded, self.state.msgBuffer )

    def handleGet( self, name ):
        self.logger.debug('GET from db %s' % name)
        #print 'GET from db %s' % name
        return self.state.db.getValue( name )

    def handleSet( self, name, value ):
        self.logger.debug('SET in db %s = %d' % (name, value))
        #print 'SET in db %s = %d' % (name, value)
        self.state.db.setValue( name, value )

    def handlePrint( self ):
        self.logger.debug('GET all vars to print')
        #print 'GET all vars to print'
        return self.state.db.getAll()

    def handleDelay( self, inDelay, outDelay ):
        self.state.inDelay = inDelay
        self.state.outDelay = outDelay
        self.logger.debug('In delay = %s, out delay = %s' % (inDelay, outDelay))
        #print '[SERVER] In delay = %s, out delay = %s', (inDelay, outDelay)

    def handleMiss( self, miss ):
        self.state.miss = miss
        self.logger.debug('Miss = %s' % miss)
        #print '[SERVER] Miss = %s', miss

class SRServer(SocketServer.TCPServer):
    
    def __init__(self, addrFile, dbFile, server_address, handler_class, msgSize=10000):
        addresses = self.readAddrFile( addrFile )
        self.state = ServerState( addresses, dbFile, server_address, msgSize )
        SocketServer.TCPServer.__init__(self, server_address, handler_class)

    def readAddrFile( self, addrFile ):
        parser = ConfigParser()
        parser.read( addrFile )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print 'Read addresses from the addr file:'
        for (i, (ip, port)) in enumerate( addresses, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

        return addresses

    def getState( self ):
        return self.state

class ServerState(object):
    def __init__( self, addresses, dbFile, server_address, msgSize ):
        self._addresses = addresses
        self._ip, self._port = server_address
        self._myNr = self.findMyIndex( self._addresses, self._ip, self._port )
        self._msgSize = msgSize
        self._db = DB( filename=dbFile )
        self._inDelay = 0
        self._outDelay = 0
        self._miss = False
        self._clock = Clock(self._myNr)
        self._msgBuffer = deque()

    def getAddresses( self ):
        return self._addresses
    addresses = property( getAddresses )

    def getIp( self ):
        return self._ip
    ip = property( getIp )

    def getPort( self ):
        return self._port
    port = property( getPort )

    def getMyNr( self ):
        return self._myNr
    myNr = property( getMyNr )

    def getMsgSize( self ):
        return self._msgSize
    msgSize = property( getMsgSize  )

    def getDb( self ):
        return self._db
    db = property( getDb )

    def getInDelay( self ):
        return self._inDelay
    def setInDelay( self, value ):
        self._inDelay = value
    inDelay = property( getInDelay, setInDelay )

    def getOutDelay( self ):
        return self._outDelay
    def setOutDelay( self, value ):
        self._outDelay = value
    outDelay = property( getOutDelay, setOutDelay )

    def getMiss( self ):
        return self._miss
    def setMiss( self, value ):
        self._miss = value
    miss = property( getMiss, setMiss )

    def getClock( self ):
        return self._clock
    clock = property( getClock  )

    def getMsgBuffer( self ):
        return self._msgBuffer
    msgBuffer = property( getMsgBuffer )

    def findMyIndex( self, addresses, myIp, myPort ):
        addr = [myIp, str(myPort)]
        try:
            index = addresses.index(addr)
        except ValueError:
            raise RuntimeError('Server address %s not in available addresses: %s' \
                                % (addr, addresses))
        else:
            return index


if __name__ == '__main__':
    topDir = os.path.dirname( os.getcwd() )
    addrFile = os.path.join(topDir, 'addr.txt')
    try:
        ip = sys.argv[1]
        port = int( sys.argv[2] )
        dbFile = sys.argv[3]
    except (IndexError, ValueError):
        ip = '127.0.0.1'
        port = 4321
        dbFile = 'data.db'
        print 'No ip/port specified, using default value: %s:%d', (ip, port)

    # TODO: clean up
    #server = Server( addrFile, ip, port )
    #server.start()

    server_address = (ip, port)
    server = SRServer( addrFile, dbFile, server_address, SRRequestHandler )
    #server = SocketServer.TCPServer( server_address, SRRequestHandler )
    server.serve_forever()
