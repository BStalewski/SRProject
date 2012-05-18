import socket
import simplejson as json
from ConfigParser import ConfigParser

import common
from db import DB

class Server:
    def __init__( self, ipFile, port, msgSize=100 ):
        self.ips = self.readIpFile( ipFile )
        self.port = port
        self.myNr = self.findMyIndex( self.ips )
        self.msgSize = msgSize
        self.db = DB()

    def readIpFile( self, ipFile ):
        parser = ConfigParser()
        parser.read( ipFile )
        ips = [t[1] for t in parser.items('IP')]
        print 'Read IPs from file:'
        for (i, ip) in enumerate( ips ):
            print '[%d] %s' % (i+1, ip)
        return ips

    def findMyIndex( self, ips ):
        myIps = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in myIps:
            try:
                index = ips.index( ip )
            except:
                pass
            else:
                return index
        raise RuntimeError("None of my ips ( %s ) is in IP list ( %s )" % (myIps, ips))

    def start( self ):
        print '[SERVER] Starting server'
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print '[SERVER] Socket created'
        s.bind( ('192.168.1.14', self.port) )
        s.listen(5)
        print '[SERVER] Listening'

        while True:
            (csocket, adr) = s.accept()
            while True:
                print '[SERVER] Connection from', adr
                try:
                    request = csocket.recv(self.msgSize)
                except:
                    print 'Connection broken'
                else:
                    msg = self.decodeRequest( request )
                    print '[SERVER] Message received =', msg

                    if msg['type'] == 'END':
                        csocket.shutdown( socket.SHUT_RDWR )
                        csocket.close()
                        print '[SERVER] Connection closed with', adr
                        break

                    response = self.prepareResponse( msg )
                    filledResponse = common.fillOutMsg( response, self.msgSize )
                    
                    sentSize = csocket.send( filledResponse )
                    print '[SERVER] Message sent =', response
                    if sentSize == 0:
                        print 'Unable to connect to client'


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
        else:
            response = {
                'data': result
            }
        # exit is not handled
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

    
if __name__ == '__main__':
    ipFile = 'ips.txt'
    port = 4321
    server = Server( ipFile, port )
    server.start()

