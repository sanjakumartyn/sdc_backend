from django.db import connections

def test_db():
    conn = connections['default']
    print(dir(conn))
    print(conn.connection)
    
if __name__ == '__main__':
    test_db()
