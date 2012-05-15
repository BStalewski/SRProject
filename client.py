from logger import Logger
from db import FakeDB
from ConfigParser import ConfigParser, NoOptionError
import simplejson as json
import socket
from threading import Thread

class Client:
    def __init__( self, clock, queue, myid, msgPort=1234, pingPort=1235, ip_file='ip.txt' ):
        self.ips = self.get_ips( ip_file )
        self.clock = clock
        self.queue = queue
        self.myid = myid
        self.msgPort = msgPort
        self.pingPort = pingPort

    def get_ips( self, ip_file ):
        with open( self.ip_file, 'rb' ) as f:
            parser = ConfigParser()
            parser.read( ip_file )
            ip_list = parser.items()
        return [ (int(t[0]), t[1], False) for t in ip_list ]

    def findOthers( self ):
        Thread( target=ping, (self.ips,) ).start()

    def checkConnections( self ):
        for (i, t) in enumerate(ip_list):
            nr, ip, state = t
            newState = state
            s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
            try:
                s.connect(ip, self.pingPort)
                s.close()
            except:
                ip_list[i][2] = False
            else:
                ip_list[i][2] = True

    def sendMsg( self, name, value ):
        self.clock.tick( self.myid )
        myVector = self.clock.getVector( self.myid )
        msg = json.dumps({
            'sender': self.myid,
            'clocks': myVector,
            'name': name,
            'value': value
        })
        
def ping( ips, ping, killSignal ):
    while not killSignal:
    for (i, t) in enumerate(ips):
        nr, ip, state = t
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        socket.setblocking( 0 ) # careful
        try:
            s.connect( ip, port )
            s.close()
            ips[i][2] = True
        except:
            ips[i][2] = False

