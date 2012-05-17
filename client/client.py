# Client code for reliable broadcast
from ConfigParser import ConfigParser
from random import randint
import socket
import simplejson as json

class Client:
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
        ip_count = len( self.ips )
        while True:
            nr = self.chooseServer()
            if nr in ['q', 'Q']:
                print 'Koniec dzialania klienta'
                break
                        
            conn = self.connectToServer( nr - 1 )
            if conn is None:
                print 'Nie mozna polaczyc sie z tym serwerem'
                continue
            
            operation = self.menu()
            operation_data = self.getOperationData( operation )
            msg = self.prepareMessage( operation, operation_data )
            '''
            try:
                if operation == '1':
                    name, value = self.getValue()
                    print '%s wynosi %d' % ( name, value )
                elif operation == '2':
                    name, value, result = self.setValue()
                    print 'Ustawienie %s na %d zakonczone %s' % ( name, value, result )
                elif operation == '3':
                    name, result = self.deleteValue()
                    print 'Usuniecie %s zakonczone %s' % ( name, result )
                elif operation == '4':
                    pairs = self.getValues()
                    for name, value in pairs:
                        print '%s wynosi %d' % ( name, value )
            except RuntimeError as e:
                print 'Wystapil blad'
                print e
            '''
            
            fullMsg = {
                'sender': self.myNr,
                'clocks': [0, 0, 0, 0],
                'data': msg
            }
            filledMsg = self.fillOutMsg( json.dumps( fullMsg ) )
            sentSize = conn.send( filledMsg )
            if sentSize == 0:
                print 'Blad polaczenia z serwerem'
            else:
                response = conn.recv( self.msgSize )
                print response

            conn.shutdown( socket.SHUT_RDWR )
            conn.close()

    def menu( self ):
        operation = None
        while operation not in ['1', '2', '3', '4', '5']:
            print 'Wybierz operacje'
            print '(1) Pobierz wartosc'
            print '(2) Ustaw wartosc'
            print '(3) Usun wartosc'
            print '(4) Wypisz wszystkie wartosci'
            print '(5) Zakoncz polaczenie'
            operation = raw_input('$')

        return operation

    def connectToServer( self, nr ):
        ip = self.ips[ nr ]
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print 'TRY connect to %s:%s' % (ip, self.port)
        try:
            s.connect( (ip, self.port) )
        except:
            return None
        return s

    def chooseServer( self ):
        ip_count = len( self.ips )
        print 'Polacz z serwerem. Wybierz liczbe 1 - %d, aby polaczyc sie' % ip_count
        print 'z wybranym serwerem lub %d, aby polaczyc sie z losowym serwerem.' % (ip_count + 1)
        print 'Wpisz Q lub q, aby zakonczyc program.'
        while True:
            user_input = raw_input('$')
            try:
                nr = int( user_input )
                if nr < 1 or nr > ip_count + 1:
                    print 'Bledny numer. Podaj jeszcze raz'
                elif nr == ip_count + 1:
                    nr = randint( 1, ip_count )
                    print 'Wybrano losowy serwer numer:', nr
            except:
                if user_input in ['q', 'Q']:
                    return user_input
            else:
                break
        return nr

    def getOperationData( self, op ):
        if op == '1':
            print 'Podaj nazwe do pobrania'
            name = raw_input('$')
            data = (name,)
        elif op == '2':
            print 'Podaj nazwe i nowa wartosc'
            name = raw_input('$')
            value = raw_input('$')
            data = (name, value)
        elif op == '3':
            print 'Podaj nazwe do usuniecia'
            name = raw_input('$')
            data = (name,)
        elif op == '4':
            data = None
        elif op == '5':
            data = None
        else:
            raise RuntimeError('Bad operation number %s' % op)

        return data

    def prepareMessage( self, op, data ):
        if op == '1':
            msg = {
                'type': 'GET',
                'name': data[0]
            }
        elif op == '2':
            msg = {
                'type': 'SET',
                'name': data[0],
                'value': data[1]
            }
        elif op == '3':
            msg = { 
                'type': 'DEL',
                'name': data[0]
            }
        elif op == '4':
            msg = { 
                'type': 'GETALL'
            }
        elif op == '5':
            msg = {
                'type': 'END'
            }
        else:
            raise RuntimeError('Bad operation number %s' % op)

        return msg

    def fillOutMsg( self, msg ):
        missingSize = self.msgSize - len( msg )
        if missingSize < 0:
            raise RuntimeError('Message too big')
        filling = ''.join( [ '#' for _ in range( missingSize ) ] )
        filledMsg = msg + filling

        return filledMsg

    def getValue( self, name ):
        pass

    def setValue( self, name ):
        pass

    def deleteValue( self, name ):
        pass

    def printValues( self ):
        pass

    def setServerDelay( self, delay ):
        pass

    def setServerDataLose( self ):
        pass

    def unsetServerDataLose( self ):
        pass

