# -*- coding: utf-8 -*-
# Commands from keyboard

from logger import Logger
from db import FakeDB

def main():
    logger = Logger( 0 )
    fdb = FakeDB( logger )
    op = None
    while op != '5':
        print 'Choose operation'
        print '1. Get value'
        print '2. Set value'
        print '3. Delete value'
        print '4. Print all values'
        print '5. Koniec'
        op = raw_input('Operation number:')

        if op == '1':
            readValue( fdb )
        elif op == '2':
            setValue( fdb ) 
        elif op == '3':
            deleteValue( fdb )
        elif op == '4':
            showValues( fdb )

    print 'Good bye'

def readValue( sdb ):
    name = raw_input('Name:')
    print 'GET %s' % name
    print sdb.getValue( name )

def setValue( sdb ):
    # TODO: CONNECT TO OTHER CLIENTS
    name = raw_input('Name:')
    value = int( raw_input('Value:') )
    print 'SET %s = %s' % (name, value)
    sdb.setValue( name, value )

def deleteValue( sdb ):
    # TODO: CONNECT TO OTHER CLIENTS
    name = raw_input('Name:')
    print 'DELETE %s' % name
    sdb.deleteValue( name )

def showValues( sdb ):
    print 'Base content'
    print sdb.getValues()

if __name__ == '__main__':
    main()

