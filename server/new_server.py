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
        print self.client_address
        
        self.logger.debug('Message received = %s' % msg)
        if self.isClientMsg( msg['type'] ):
            self.handleClientConnection( msg )
        elif self.isServerMsg( msg['type'] ):
            self.handleServerConnection( msg )
        else:
            raise RuntimeError('Unknown message type: %s' % msg['type'])

    def isClientMsg( self, msgType ):
        return msgType in ['END', 'GET', 'SET', 'GETALL', 'DELAY', 'MISS']

    def isServerMsg( self, msgType ):
        return msgType in ['SHARE', 'REFUSE', 'HELP', 'FILLUP']

    def handleClientConnection( self, msg ):
        while True:
            if msg['type'] == 'END':
                strAddr = self.client_address[0] + ':' + str(self.client_address[1])
                self.logger.debug('Connection closed with %s' % strAddr)
                return
            elif msg['type'] == 'GET':
                response = {
                    'type' : 'RGET',
                    'name' : msg['name'],
                    'value': self.handleGet( msg['name'] )
                }
            elif msg['type'] == 'SET':
                print '************* BEGIN SET **************'
                self.state.clock.printState()
                self.handleSet( msg['name'], msg['value'] )
                response = {
                    'type': 'OK'
                }
                myVec = self.state.clock.getVector()
                self.replicate( msg['name'], msg['value'], myVec )
                self.state.clock.send()
                print '************* END SET ****************'
                self.state.clock.printState()
            elif msg['type'] == 'GETALL':
                response = {
                    'type': 'RGETALL',
                    'data': self.handlePrint()
                }
            elif msg['type'] == 'DELAY':
                self.handleDelay( msg['in'], msg['out'] )
            elif msg['type'] == 'MISS':
                self.handleMiss( msg['in'], msg['out'] )

            if msg['type'] in ['GET', 'SET', 'GETALL']:
                jsResponse = json.dumps( response )
                sentSize = self.request.send( jsResponse )
                self.logger.debug('Message sent = %s' % jsResponse)
                if sentSize == 0:
                    self.logger.error('Unable to connect to client')
                    return

            try:
                data = self.request.recv( self.state.msgSize )
                msg = json.loads( data )
            except:
                self.logger.error('Connection broken')
                return

    def handleServerConnection( self, msg ):
        if msg['type'] == 'SHARE':
            if self.state.inMiss:
                self.logger.debug('In message %s dropped' % msg)
                return
            if self.state.inDelay > 0:
                self.logger.debug('Delaying message %s for %d seconds' % (msg['type'], self.state.inDelay))
                time.sleep( self.state.inDelay )

            if self.findInBuffer( msg['clocks'], msg['sender'] ):
                self.logger.debug('Share msg from the same sender %d in the buffer, ignoring it' % msg['sender'])
                return

            print '************* BEGIN SHARE **************'
            self.state.clock.printState()
            if self.isMsgRefusable( msg ):
                self.logger.debug('Sender %d has bad clock' % msg['sender'])
                response = {
                    'type'  : 'REFUSE',
                    'sender': self.state.myNr,
                    'clocks': msg['clocks']
                }
                self.sendToServer( response, nr=msg['sender'] )
            else:
                needHelp = msg['clocks'] > self.state.clock.getVector()
                if needHelp:
                    response = {
                        'type'  : 'HELP',
                        'clocks': self.state.clock.getVector()
                    }
                    newSock = self.sendToServer( response, nr=msg['sender'], resp=True )
                    self.logger.debug('Help sent to %d with clocks %s' % (msg['sender'], response['clocks']))
                    data = newSock.recv( self.state.msgSize )
                    respMsg = json.loads( data )
                    if respMsg['type'] != 'FILLUP':
                        return
                    
                    self.logger.debug('Fillup received from %d with msgs = %s' % (msg['sender'], respMsg['msgs']))
                    time.sleep( self.state.inDelay )
                    self.update( respMsg['msgs'] )

                else:
                    self.logger.debug('Sender %d has correct clock' % msg['sender'])
                    self.updateClock( msg )
                    self.updateBuffer( msg )
                    self.handleSet( msg['name'], msg['value'] )

            print '************* END SHARE ****************'
            self.state.clock.printState()
        elif msg['type'] == 'REFUSE':
            self.logger.debug('Refuse from %d with clocks %s' % (msg['sender'], msg['clocks']))
            refuseClocks = msg['clocks']
            if not self.findInBuffer( msg['clocks'], self.state.myNr ):
                return
            refusedMsg = self.getFromBuffer( msg['clocks'], self.state.myNr )

            self.state.clock.refuse()

            response = {
                'type'  : 'HELP',
                'clocks': self.state.clock.getVector()
            }
            newSock = self.sendToServer( response, nr=msg['sender'], resp=True )
            self.logger.debug('Help sent to %d with clocks %s' % (msg['sender'], response['clocks']))
            data = newSock.recv( self.state.msgSize )
            respMsg = json.loads( data )
            if respMsg['type'] != 'FILLUP':
                return
            
            self.logger.debug('Fillup received from %d with msgs = %s' % (msg['sender'], respMsg['msgs']))
            time.sleep( self.state.inDelay )
            self.update( respMsg['msgs'], refuse=True )

            myVec = self.state.clock.getVector()
            self.handleSet( refusedMsg['name'], refusedMsg['value'] )
            self.replicate( refusedMsg['name'], refusedMsg['value'], myVec )

        elif msg['type'] == 'HELP':
            self.logger.debug('Help received from %s with clocks = %s' % (self.request, msg['clocks']))
            msgs = self.getHelpMessages( msg )
            print 'HELP MESSAGES:', msgs
            response = {
                'type': 'FILLUP',
                'msgs': msgs
            }
            self.sendToServer( response, sock=self.request )
            self.logger.debug('Fillup sent to %s with msgs: %s' % (self.request, response['msgs']))

    def sendToServer( self, msg, nr=None, sock=None, resp=False ):
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
            if resp:
                return sock
        except Exception as e:
            print 'Error during help messages'
            print e

    def replicate( self, name, value, vec ):
        repMsg = {
            'type'  : 'SHARE',
            'sender': self.state.myNr,
            'clocks': vec,
            'name'  : name,
            'value' : value
        }
        self.updateBuffer( repMsg )

        if self.state.outMiss:
            self.logger.debug('Out message replicate %s dropped' % msg)
            return
        if self.state.outDelay > 0:
            self.logger.debug('Delaying out replicate message for %d seconds' % self.state.outDelay)
            time.sleep( self.state.outDelay )

        for i in range( len(self.state.addresses) ):
            if i == self.state.myNr:
                continue
            self.sendToServer( repMsg, nr=i )
            self.logger.debug('Replication with clocks = %s sent to %d' % (vec, i))

    def updateClock( self, msg ):
        self.state.clock.recv( msg['sender'], msg['clocks'][:] )

    def canBeRemoved( self, msg, col ):
        nr = msg['sender']
        print 'Trying to remove msg from the buffer'
        print 'Sender column in my column:', col, 'Sender nr:', nr, 'Msg clocks:', msg['clocks']
        print 'Checking if min(col) > msg[clocks][nr] :: ', min(col), '>', msg['clocks'][nr]
        return min( col ) > msg['clocks'][nr] 

    def isMsgRefusable( self, msg ):
        myVec = self.state.clock.getVector()
        for (i, msgTime) in enumerate(msg['clocks']):
            if msgTime < myVec[i]:
                return True

        return False

    def updateBuffer( self, msg ):
        def isNotNeeded( m ):
            sender  = m['sender']
            return self.canBeRemoved( m, self.state.clock.getColumn( sender ) )

        self.state.msgBuffer.append( msg )
        nr = msg['sender']
        toRemove = [ i for (i, m) in enumerate(self.state.msgBuffer) if isNotNeeded( m ) ]
        toRemove.reverse()

        for i in toRemove:
            self.logger.debug('Message discarded')
            del self.state.msgBuffer[ i ]

        self.logger.debug( '%d remaining message(s) in the buffer' % len(self.state.msgBuffer) )

    def removeFromBuffer( self, clocks, sender ):
        self.getFromBuffer( clocks, sender )

    def findInBuffer( self, clocks, sender ):
        for msg in self.state.msgBuffer:
            if msg['clocks'] == clocks and msg['sender'] == sender:
                return True

        return False

    def getFromBuffer( self, clocks, sender ):
        foundMsg = None
        for (i, msg) in enumerate(self.state.msgBuffer):
            if msg['clocks'] == clocks and msg['sender'] == sender:
                foundMsg = msg

        if foundMsg:
            self.state.msgBuffer.remove( foundMsg )
            return foundMsg
        else:
            return None

    def update( self, msgs, refuse=False ):
        for msg in msgs:
            badClockDetected = self.isMsgRefusable( msg )
            if not refuse or badClockDetected:
                raise RuntimeError('Bad clock detected in update')

            self.updateClock( msg )
            self.updateBuffer( msg )
            self.handleSet( msg['name'], msg['value'] )

    def getHelpMessages( self, msg ):
        msgs = []
        myVec = self.state.clock.getVector()

        for i in range( len( self.state.addresses ) ):
            missing = myVec[i] - msg['clocks'][i]
            if missing > 0:
                msgs += filter( lambda m: m['sender'] == i, self.state.msgBuffer )[:missing]

        return msgs

    def handleGet( self, name ):
        self.logger.debug('GET from db: %s' % name)
        return self.state.db.getValue( name )

    def handleSet( self, name, value ):
        self.logger.debug('SET in db: %s = %d' % (name, value))
        self.state.db.setValue( name, value )

    def handlePrint( self ):
        self.logger.debug('GET all vars')
        return self.state.db.getAll()

    def handleDelay( self, inDelay, outDelay ):
        self.state.inDelay = inDelay
        self.state.outDelay = outDelay
        self.logger.debug('Updated delay: in delay = %s, out delay = %s' % (inDelay, outDelay))

    def handleMiss( self, inMiss, outMiss ):
        self.state.inMiss = inMiss
        self.state.outMiss = outMiss
        self.logger.debug('Updated miss: in miss = %s, out miss = %s' % (inMiss, outMiss))

class SRServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    
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
    def __init__( self, addresses, dbFile, server_address, msgSize, init_clocks=True ):
        self._addresses = addresses
        self._ip, self._port = server_address
        self._myNr = self.findNr( self._ip, self._port )
        self._msgSize = msgSize
        self._db = DB( filename=dbFile )
        self._inDelay = 0
        self._outDelay = 0
        self._inMiss = False
        self._outMiss = False
        if init_clocks:
            self._clock = Clock( self._myNr, len(addresses) )
        else:
            try:
                self._clock = self._db.getClocks()
            except IOError:
                print 'Error: cannot load clocks from file, initiating'
                self._clock = Clock( self._myNr, len(addresses) )
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

    def getInMiss( self ):
        return self._inMiss
    def setInMiss( self, value ):
        self._inMiss = value
    inMiss = property( getInMiss, setInMiss )

    def getOutMiss( self ):
        return self._outMiss
    def setOutMiss( self, value ):
        self._outmiss = value
    outMiss = property( getOutMiss, setOutMiss )

    def getClock( self ):
        return self._clock
    def setClock( self, clock ):
        self._clock = clock
    clock = property( getClock, setClock )

    def getMsgBuffer( self ):
        return self._msgBuffer
    msgBuffer = property( getMsgBuffer )

    def findNr( self, ip, port ):
        addr = [ip, str(port)]
        try:
            return self._addresses.index(addr)
        except ValueError:
            raise RuntimeError('Server address %s not in available addresses: %s' \
                                % (addr, self._addresses))

    def clockSend( self ):
        self.clock.send()
        self.db.saveClocks( self.clock )

    def clockRecv( self, senderNr, clockVec ):
        self.clock.recv( senderNr, clockVec )
        self.db.saveClocks( self.clock )


if __name__ == '__main__':
    topDir = os.path.dirname( os.getcwd() )
    addrFile = os.path.join(topDir, 'addr.txt')
    try:
        ip = sys.argv[1]
        port = int( sys.argv[2] )
        dbFile = sys.argv[3]
    except (IndexError, ValueError):
        ip = '192.168.1.167'
        port = 4000
        dbFile = 'data.db'
        print 'No ip/port specified, using default value: %s:%d', (ip, port)

    # TODO: clean up
    #server = Server( addrFile, ip, port )
    #server.start()

    server_address = (ip, port)
    server = SRServer( addrFile, dbFile, server_address, SRRequestHandler )
    #server = SocketServer.TCPServer( server_address, SRRequestHandler )
    server.serve_forever()

