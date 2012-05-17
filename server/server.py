import socket
import simplejson as json
from ConfigParser import ConfigParser

import common


class Server:
    def __init__( self, ip_file, port, myNr, msgSize=100 ):
        self.ips = self.read_ip_file( ip_file )
        self.port = port
        self.myNr = myNr
        self.msgSize = msgSize

    def read_ip_file( self, ip_file ):
        parser = ConfigParser()
        parser.read( ip_file )
        ips = [t[1] for t in parser.items('IP')]
        print 'Read IPs from file:'
        for (i, ip) in enumerate( ips ):
            print '[%d] %s' % (i+1, ip)
        return ips

    def start( self ):
        print '[SERVER] Starting server'
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print '[SERVER] Socket created'
        s.bind( ('192.168.1.14', self.port) )
        s.listen(5)
        print '[SERVER] Listening'

        while 1:
            (csocket, adr) = s.accept()
            print '[SERVER] Connection from', adr
            try:
                request = csocket.recv(self.msgSize)
            except:
                print 'Connection broken'
            else:
                msg = self.decodeRequest( request )
                print '[SERVER] Message received =', msg
                self.handleConnection( msg['data'] )
                response = self.prepareResponse( msg['data'] )
                filledResponse = common.fillOutMsg( response, self.msgSize )
                
                sentSize = csocket.send( filledResponse )
                print '[SERVER] Message sent =', msg
                if sentSize == 0:
                    print 'Blad polaczenia z klientem'

            csocket.shutdown( socket.SHUT_RDWR )
            csocket.close()
            print '[SERVER] Connection closed with', adr

    def decodeRequest( self, request ):
        json_request = request.rstrip('#')
        return json.loads( json_request )

    def prepareResponse( self, msg ):
        if msg['type'] == 'GET':
            response = {
                'name': msg['name'],
                'value': -1
            }
        elif msg['type'] == 'SET':
            response = {
                'name': msg['name'],
                'value': msg['value'],
            }
        elif msg['type'] == 'DEL':
            response = {
                'name': msg['name']
            }
        else:
            response = [
                { 'name': 'a', 'value': -1 },
                { 'name': 'b', 'value': -2 },
                { 'name': 'c', 'value': -3 }
            ]
        # exit is not handled
        return json.dumps( response )

    def handleConnection( self, msg ):
        oper = msg.get( 'type' )
        if oper == 'GET':
            self.handleGet( msg['name'] )
        elif oper == 'SET':
            self.handleSet( msg['name'], msg['value'] )
        elif oper == 'DEL':
            self.handleDel( msg['name'] )
        elif oper == 'GETALL':
            self.handlePrint()
        else:
            raise RuntimeError('Unknown operation type %s' % oper)

    def handleGet( self, name ):
        print 'GET from db %s' % name

    def handleSet( self, name, value ):
        print 'SET in db %s = %d' % (name, value)

    def handleDel( self, name ):
        print 'DEL in db %s' % name

    def handlePrint( self ):
        print 'GET all vars to print'

    
if __name__ == '__main__':
    server = Server( 'ips.txt', 4321, 1 )
    server.start()

