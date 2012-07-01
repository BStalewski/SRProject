# -*- coding: utf-8 -*-
# Client code for reliable broadcast

from ConfigParser import ConfigParser
from random import randint
import os
import socket
import simplejson as json

class Client:
    def __init__( self, addr_file, msg_size=100 ):
        self.addresses = self.read_addr_file( addr_file )
        self.msg_size = msg_size

    def read_addr_file( self, addr_file ):
        parser = ConfigParser()
        parser.read( addr_file )
        addresses = [ addr[1].split(':') for addr in parser.items('IP') ]

        print u'Wczytano następujące adresy z pliku:'
        self.print_addresses( addresses )

        return addresses

    def print_addresses( self, ips ):
        for (i, (ip, port)) in enumerate( ips, 1 ):
            print '[%d] %s:%s' % (i, ip, port)

    def start( self ):
        print u'***************************************************************'
        print u'****************** WITAJ DROGI UŻYTKOWNIKU!! ******************'
        print u'******** DZIĘKUJEMY ZA SKORZYSTANIE Z NASZEGO PROGRAMU ********'
        print u'***************************************************************'
        while True:
            nr = self.choose_server()
            if nr in ['q', 'Q']:
                print u'Koniec działania klienta'
                break
                        
            conn = self.connect_to_server( nr - 1 )
            if conn is None:
                print u'Nie można połączyć się z tym serwerem'
                continue
            
            while True:
                operation = self.menu( nr )
                    
                operation_data = self.get_operation_data( operation )
                msg = self.prepare_message( operation, operation_data )
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
                        response = conn.recv( self.msg_size )
                        print u'Otrzymano odpowiedź z serwera'
                        decoded_response = self.decode_response( response )
                        self.show_response( decoded_response )


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

    def connect_to_server( self, nr ):
        ip, str_port = self.addresses[ nr ]
        port = int(str_port)
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        print u'Próba połączenia z %s:%s' % (ip, port)
        try:
            s.connect( (ip, port) )
        except:
            return None
        return s

    def choose_server( self ):
        ip_count = len( self.addresses )
        print u'Dostępne serwery:'
        self.print_addresses( self.addresses )
        print u'Połącz się z serwerem lub zakończ wyjdź z programu.'
        print u'Wpisz liczbę 1 - %d, aby połączyć się z wybranym serwerem' % ip_count
        print u'lub %d, aby połączyć się z losowym serwerem.' % (ip_count + 1)
        print u'Wpisz Q lub q, aby zakończyć program.'
        while True:
            user_input = raw_input('$')
            try:
                nr = int( user_input )
                if nr < 1 or nr > ip_count + 1:
                    print u'Błędny numer. Podaj jeszcze raz'
                elif nr == ip_count + 1:
                    nr = randint( 1, ip_count )
                    print u'Wybrano losowy serwer numer:', nr
            except:
                if user_input in ['q', 'Q']:
                    return user_input
            else:
                break
        return nr

    def get_operation_data( self, op ):
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
            print u'Opóżnienie na wejściu =',
            in_delay = int( raw_input('') )
            print u'Opóźnienie na wyjściu =',
            out_delay = int( raw_input('') )
            data = (in_delay, out_delay)
        elif op == '5':
            print u'Czy pakiety wejściowe są gubione przez serwer (t/n)?',
            in_miss = raw_input('').lower() == 't'
            print u'Czy pakiety wyjściowe są gubione przez serwer (t/n)?',
            out_miss = raw_input('').lower() == 't'
            data = (in_miss, out_miss)
        elif op == '6':
            data = None
        else:
            raise RuntimeError(u'Bad operation number %s' % op)

        return data

    def prepare_message( self, op, data ):
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
                'in'   : data[0],
                'out'  : data[1]
            }
        elif op == '6':
            msg = {
                'type': 'END'
            }
        else:
            raise RuntimeError(u'Bad operation number %s' % op)

        return msg

    def decode_response( self, response ):
        json_response = response.rstrip('#')
        print json_response
        return json.loads( json_response )

    def show_response( self, response ):
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
    top_dir = os.path.dirname( os.getcwd() )
    addr_file = os.path.join(top_dir, 'addr.txt')
    client = Client( addr_file )
    client.start()


