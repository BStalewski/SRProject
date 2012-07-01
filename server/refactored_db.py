import pickle

class DB:
    def __init__( self, filename='data.db', purge=True ):
        self.filename = filename
        if purge:
            self.purge()
            self.state = {}
        else:
            self.state = self.get_all()

    def purge( self ):
        self.state = {}
        pickled = pickle.dumps( {} )
        with open( self.filename, 'wb' ) as f:
            f.write( pickled )

    def get_value( self, name ):
        return self.state.get( name )

    def set_value( self, name, value ):
        self.state[ name ] = value
        pickled = pickle.dumps( self.state )
        with open( self.filename, 'wb' ) as f:
            f.write( pickled )

    def get_all( self ):
        return dict( self.state )

    def get_clocks( self ):
        with open( self.clocks_file, 'rb' ) as f:
            content = f.read()

        return pickle.loads( content )

    def save_clocks( self, clocks ):
        pickled = pickle.dumps( clocks )

        with open( self.clocks_file, 'wb' ) as f:
            f.write( pickled )


