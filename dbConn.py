import MySQLdb

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'passwd': 'computing',
    'db': 'sakila', # Here you select Sakila database
}

# Create a connection to the database
conn = MySQLdb.connect(**db_config)
