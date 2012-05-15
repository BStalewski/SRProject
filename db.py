# Module simulating database
from ConfigParser import ConfigParser, NoOptionError

class FakeDB:
    def __init__( self, logger, db_file='db.txt' ):
        self.db_file = db_file
        self.db = self.openDB( self.db_file )
        self.logger = logger
        self.logger.log( '[DB] Initiation', 10 )
        self.logger.log( '[DB] Actual values:', 9 )
        for name, value in self.db.items('DB'):
            self.logger.log( '[DB] %s = %s' % (name, value), 9 )
        self.logger.log( '[DB] Initiation done', 9 )

    def openDB( self, db_file ):
        try:
            db = ConfigParser()
            db.read( db_file )
        except:
            self.logger( '[DB] Unable to open file %s' % db_file, 15 )
            exit('FILE ERROR')
        return db

    def saveDB( self ):
        with open( self.db_file, 'wb' ) as f:
            self.db.write( f )
        self.db = self.openDB( self.db_file )

    def setValue( self, name, value ):
        self.logger.log( '[DB] Set value: %s <- %s' % (name, value), 12 )
        self.db.set( 'DB', name, str(value) )
        self.saveDB()

    def deleteValue( self, name ):
        if self.db.has_option( 'DB', name ):
            self.logger.log( '[DB] Delete value: %s' % name, 12 )
            self.db.remove_option( 'DB', name )
            self.saveDB()
        else:
            self.logger.log( '[DB] No name %s to delete' % name, 12 )

    def getValue( self, name ):
        try:
            value = self.db.getint('DB', name)
        except NoOptionError:
            value = None
        self.logger.log( '[DB] Get value: %s = %s' % (name, value), 12 )
        return value

    def getValues( self ):
        result = {}
        for name, value in self.db.items('DB'):
            result[ name ] = self.getValue( name )
        return result
