import sqlite3

class DB:
    def __init__( self, filename, purge=True ):
        self.conn = sqlite3.connect('data.db')
        if purge:
            self.purge()

    def purge( self ):
        self.conn.execute('DROP TABLE values')
        self.conn.execute('CREATE TABLE numbers(name text, value integer)')
        self.conn.commit()
        
    def getValue( self, name ):
        self.conn.execute('SELECT value FROM numbers WHERE name=?', name)
        return self.conn.fetchone()

    def setValue( self, name, value ):
        self.conn.execute('INSERT INTO numbers VALUES (?, ?)', (name, value))
        self.conn.commit()

    def delValue( self, name ):
        self.conn.execute('DELETE FROM numbers WHERE name=?', name)
        self.conn.commit()

    def getAll( self ):
        self.conn.execute('SELECT * FROM VALUES')
        allData = self.conn.fetchall()
        return dict( allData )

