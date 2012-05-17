import sqlite3

class DB:
    def __init__( self, filename='data.db', purge=True ):
        self.conn = sqlite3.connect( filename )
        if purge:
            self.purge()

    def purge( self ):
        cursor = self.conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS numbers')
        cursor.execute('CREATE TABLE numbers(name text, value integer)')
        self.conn.commit()
        
    def getValue( self, name ):
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM numbers WHERE name = ?', (name,))
        result = cursor.fetchone()
        return None if result is None else result[0]

    def setValue( self, name, value ):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO numbers VALUES (?, ?)', (name, value))
        self.conn.commit()

    def delValue( self, name ):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM numbers WHERE name = ?', (name,))
        self.conn.commit()

    def getAll( self ):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM numbers')
        allData = cursor.fetchall()
        return dict( allData )

