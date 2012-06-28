import pickle

class DB:
    def __init__( self, filename='data.db', purge=True ):
        self.filename = filename
        if purge:
            self.purge()
            self.state = {}
        else:
            self.state = self.getAll()

    def purge( self ):
        self.state = {}
        pickled = pickle.dumps( {} )
        with open( self.filename, 'wb' ) as f:
            f.write( pickled )

    def getValue( self, name ):
        return self.state.get( name )

    def setValue( self, name, value ):
        self.state[ name ] = value
        pickled = pickle.dumps( self.state )
        with open( self.filename, 'wb' ) as f:
            f.write( pickled )

    def getAll( self ):
        return dict( self.state )

    def getClocks( self ):
        with open( self.clocks_file, 'rb' ) as f:
            content = f.read()

        return pickle.loads( content )

    def saveClocks( self, clocks ):
        pickled = pickle.dumps( clocks )

        with open( self.clocks_file, 'wb' ) as f:
            f.write( pickled )

