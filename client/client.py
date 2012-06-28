# -*- coding: utf-8 -*-
# Client code for reliable broadcast

from ConfigParser import ConfigParser
from random import randint
import os
import socket
import simplejson as json

#import sys
#reload(sys)
#sys.setdefaultencoding('utf-8')

class Client:
    def __init__( self, addrFile, msgSize=100 ):
        self.addresses = self.readAddrFile( addrFile )
        self.msgSize = msgSize

    def readAddrFile( self, addrFile ):
        parser = ConfigParser()
        parser.read( addrFile )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print u'Wczytano następujące adresy z pliku:'
        self.printAddresses( addresses )

        return addresses

    def printAddresses( self, ips ):
        for (i, (ip, port)) in enumerate( ips, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

    def start( self ):
        print u'***************************************************************'
        print u'****************** WITAJ DROGI UŻYTKOWNIKU!! ******************'
        print u'******** DZIĘKUJEMY ZA SKORZYSTANIE Z NASZEGO PROGRAMU ********'
        print u'***************************************************************'
        while True:
            nr = self.chooseServer()
            if nr in ['q', 'Q']:
                print u'Koniec działania klienta'
                break
                        
            conn = self.connectToServer( nr - 1 )
            if conn is None:
                print u'Nie można połączyć się z tym serwerem'
                continue
            
            while True:
                operation = self.menu( nr )
                    
                operationData = self.getOperationData( operation )
                msg = self.prepareMessage( operation, operationData )
                request = json.dumps( msg )

                sentSize = conn.send( request )

                if sentSize == 0:
                    print u'Błąd połączenia z serwerem'
                else:
                    if operation == '6':
                        conn.shutdown( socket.SHUT_RDWR )
                        conn.close()
                        break
                    elif operation in ['4', '5']:
                        continue
                    else:
                        print 'Przed'
                        response = conn.recv( self.msgSize )
                        print u'Otrzymano odpowiedź z serwera'
                        decodedResponse = self.decodeResponse( response )
                        self.showResponse( decodedResponse )


    def menu( self, nr ):
        operation = None
        while operation not in ['1', '2', '3', '4', '5', '6']:
            print u'*' * 40
            print u'Połączenie z serwerem numer %d' % nr
            print u'Wybierz operację'
            print u'(1) Pobierz wartość'
            print u'(2) Ustaw wartość'
            print u'(3) Wypisz wszystkie wartości'
            print u'(4) Ustaw opóźnienie pakietów'
            print u'(5) Ustaw gubienie pakietów'
            print u'(6) Zakończ połączenie'
            operation = raw_input(u'Operacja: ')
            print '*' * 40

        return operation

    def connectToServer( self, nr ):
        ip, str_port = self.addresses[ nr ]
        port = int(str_port)
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print u'Próba połączenia z %s:%s' % (ip, port)
        try:
            s.connect( (ip, port) )
        except:
            return None
        return s

    def chooseServer( self ):
        ipCount = len( self.addresses )
        print u'Dostępne serwery:'
        self.printAddresses( self.addresses )
        print u'Połącz się z serwerem lub zakończ wyjdź z programu.'
        print u'Wpisz liczbę 1 - %d, aby połączyć się z wybranym serwerem' % ipCount
        print u'lub %d, aby połączyć się z losowym serwerem.' % (ipCount + 1)
        print u'Wpisz Q lub q, aby zakończyć program.'
        while True:
            userInput = raw_input('$')
            try:
                nr = int( userInput )
                if nr < 1 or nr > ipCount + 1:
                    print u'Błędny numer. Podaj jeszcze raz'
                elif nr == ipCount + 1:
                    nr = randint( 1, ipCount )
                    print u'Wybrano losowy serwer numer:', nr
            except:
                if userInput in ['q', 'Q']:
                    return userInput
            else:
                break
        return nr

    def getOperationData( self, op ):
        if op == '1':
            print u'Podaj nazwę do pobrania'
            name = raw_input(u'Nazwa zmiennej: ')
            data = (name,)
        elif op == '2':
            print u'Podaj nazwę'
            name = raw_input(u'Nazwa zmiennej: ')
            print u'Podaj wartość'
            value = int( raw_input(u'Wartosc zmiennej: ') )
            data = (name, value)
        elif op == '3':
            data = None
        elif op == '4':
            print u'Czy opóżnienie na wejściu (t/n)?',
            inDelay = raw_input('').lower() == 't'
            print u'Czy opóźnienie na wyjściu (t/n)?',
            outDelay = raw_input('').lower() == 't'
            data = (inDelay, outDelay)
        elif op == '5':
            print u'Czy pakiety są gubione przez serwer (t/n)?',
            isMiss = raw_input('').lower() == 't'
            data = (isMiss,)
        elif op == '6':
            data = None
        else:
            raise RuntimeError(u'Bad operation number %s' % op)

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
            raise RuntimeError(u'Bad operation number %s' % op)

        return msg

    def decodeResponse( self, response ):
        jsonResponse = response.rstrip('#')
        print jsonResponse
        return json.loads( jsonResponse )

    def showResponse( self, response ):
        if response['type'] == 'RGET':
            value = response.get( 'value' )
            if value is None:
                print u'Zmienna %s nie istnieje' % response['name']
            else:
                print u'Pobrano: %s = %d' % (response['name'], value)
        elif response['type'] == 'OK':
            print u'Ustawiono'
        elif response['type'] == 'RGETALL':
            print u'Zawartość bazy danych:'
            if len( response['data'] ) == 0:
                print u'<PUSTA>'
            else:
                for name, value in response['data'].iteritems():
                    print '%s = %d' % (name, value)
        else:
            raise RuntimeError( u'Unknown response type %s' % response['type'] )


if __name__ == '__main__':
    topDir = os.path.dirname( os.getcwd() )
    addrFile = os.path.join(topDir, 'addr.txt')
    client = Client( addrFile )
    client.start()

