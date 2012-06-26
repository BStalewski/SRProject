# Client code for reliable broadcast
from ConfigParser import ConfigParser
from random import randint
import os
import socket
import simplejson as json

class Client:
    def __init__( self, addrFile, msgSize=100 ):
        self.addresses = self.readAddrFile( addrFile )
        self.msgSize = msgSize

    def readAddrFile( self, addrFile ):
        parser = ConfigParser()
        parser.read( addrFile )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print 'Wczytano nastepujace adresy z pliku:'
        self.printAddresses( addresses )

        return addresses

    def printAddresses( self, ips ):
        for (i, (ip, port)) in enumerate( ips, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

    def start( self ):
        print '***************************************************************'
        print '****************** WITAJ DROGI UZYTKOWNIKU!! ******************'
        print '******** DZIEKUJEMY ZA SKORZYSTANIE Z NASZEGO PROGRAMU ********'
        print '***************************************************************'
        while True:
            nr = self.chooseServer()
            if nr in ['q', 'Q']:
                print 'Koniec dzialania klienta'
                break
                        
            conn = self.connectToServer( nr - 1 )
            if conn is None:
                print 'Nie mozna polaczyc sie z tym serwerem'
                continue
            
            while True:
                operation = self.menu()
                    
                operationData = self.getOperationData( operation )
                msg = self.prepareMessage( operation, operationData )
                request = json.dumps( msg )

                sentSize = conn.send( request )

                if sentSize == 0:
                    print 'Blad polaczenia z serwerem'
                else:
                    if operation == '6':
                        conn.shutdown( socket.SHUT_RDWR )
                        conn.close()
                        break
                    elif operation in ['4', '5']:
                        continue
                    else:
                        print 'Otrzymano odpowiedz z serwera'
                        response = conn.recv( self.msgSize )
                        decodedResponse = self.decodeResponse( response )
                        self.showResponse( decodedResponse )


    def menu( self ):
        operation = None
        while operation not in ['1', '2', '3', '4', '5', '6']:
            print 'Wybierz operacje'
            print '(1) Pobierz wartosc'
            print '(2) Ustaw wartosc'
            print '(3) Wypisz wszystkie wartosci'
            print '(4) Ustaw opoznienie pakietow'
            print '(5) Ustaw gubienie pakietow'
            print '(6) Zakoncz polaczenie'
            operation = raw_input('$')

        return operation

    def connectToServer( self, nr ):
        ip, str_port = self.addresses[ nr ]
        port = int(str_port)
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print 'Proba polaczenia z %s:%s' % (ip, port)
        try:
            s.connect( (ip, port) )
        except:
            return None
        return s

    def chooseServer( self ):
        ipCount = len( self.addresses )
        print 'Dostepne serwery:'
        self.printAddresses( self.addresses )
        print 'Polacz sie z serwerem lub zakoncz wyjdz z programu.'
        print 'Wpisz liczbe 1 - %d, aby polaczyc sie z wybranym serwerem' % ipCount
        print 'lub %d, aby polaczyc sie z losowym serwerem.' % (ipCount + 1)
        print 'Wpisz Q lub q, aby zakonczyc program.'
        while True:
            userInput = raw_input('$')
            try:
                nr = int( userInput )
                if nr < 1 or nr > ipCount + 1:
                    print 'Bledny numer. Podaj jeszcze raz'
                elif nr == ipCount + 1:
                    nr = randint( 1, ipCount )
                    print 'Wybrano losowy serwer numer:', nr
            except:
                if userInput in ['q', 'Q']:
                    return userInput
            else:
                break
        return nr

    def getOperationData( self, op ):
        if op == '1':
            print 'Podaj nazwe do pobrania'
            name = raw_input('$')
            data = (name,)
        elif op == '2':
            print 'Podaj nazwe'
            name = raw_input('$')
            print 'Podaj wartosc'
            value = int( raw_input('$') )
            data = (name, value)
        elif op == '3':
            data = None
        elif op == '4':
            print 'Czy opoznienie na wejsciu (t/n)?'
            inDelay = raw_input('$').lower() == 't'
            print 'Czy opoznienie na wyjsciu (t/n)?'
            outDelay = raw_input('$').lower() == 't'
            data = (inDelay, outDelay)
        elif op == '5':
            print 'Czy pakiety gubione przez serwer (t/n)?'
            isMiss = raw_input('$').lower() == 't'
            data = (isMiss,)
        elif op == '6':
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
                'type': 'GETALL'
            }
        elif op == '4':
            msg = {
                'type': 'DELAY',
                'in'  : data[0],
                'out' : data[1]
            }
        elif op == '5':
            msg = {
                'type' : 'MISS',
                'value': data[0]
            }
        elif op == '6':
            msg = {
                'type': 'END'
            }
        else:
            raise RuntimeError('Bad operation number %s' % op)

        return msg

    def decodeResponse( self, response ):
        jsonResponse = response.rstrip('#')
        print jsonResponse
        return json.loads( jsonResponse )

    def showResponse( self, response ):
        if response['type'] == 'GET':
            if response['value'] is None:
                print 'Zmienna %s nie istnieje' % response['name']
            else:
                print 'Pobrano: %s = %d' % (response['name'], response['value'])
        elif response['type'] == 'SET':
            print 'Ustawiono: %s = %d' % (response['name'], response['value'])
        elif response['type'] == 'GETALL':
            print 'Zawartosc bazy danych:'
            if len( response['data'] ) == 0:
                print '<PUSTA>'
            else:
                for name, value in response['data'].iteritems():
                    print '%s = %d' % (name, value)
        else:
            raise RuntimeError( 'Unknown response type %s' % response['type'] )


if __name__ == '__main__':
    topDir = os.path.dirname( os.getcwd() )
    addrFile = os.path.join(topDir, 'addr.txt')
    client = Client( addrFile )
    client.start()

