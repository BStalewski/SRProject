import socket
import simplejson as json
from ConfigParser import ConfigParser

from common import fillOutMsg


class Server:
    def __init__( self, ip_file, port, myNr, msgSize=100 ):
        self.ips = self.read_ip_file( ip_file )
        self.port = port
        self.myNr = myNr
        self.msgSize = msgSize

    def read_ip_file( self ):
        parser = ConfigParser()
        parser.read( ip_file )
        ips = [t[1] for t in parser.items('IP')]
        print 'Read IPs from file:'
            print '[%d] %s' % (i+1, ip)
        return ips

    def start( self ):
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )

        s.bind( ('192.168.1.14', port) )
        s.listen(5)

        while 1:
            (csocket, adr) = s.accept()
            try:
                msg = csocket.recv(self.msgSize)
            except:
                print 'Connection broken'
            else:
                self.handleConnection( msg )
                response = self.prepareResponse( msg )
                filledResponse = common.fillOutMsg( response, self.msgSize )
                
                sentSize = csocket.send( filledResponse )
                if sentSize == 0:
                    print 'Blad polaczenia z klientem'

            csocket.shutdown()
            csocket.close()

    def prepareResponse( self, fullMsg ):
        json_msg = fullMsg.rstrip('#')
        msg = json.loads( msg )
        if msg['type'] == 'GET':
            response = {
                'name': name,
                'value': -1
            }
        elif msg['type'] == 'SET':
            response = {
                'name': name,
                'value': value,
            }
        elif msg['type'] == 'DEL':
            response = {
                'name': name
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

