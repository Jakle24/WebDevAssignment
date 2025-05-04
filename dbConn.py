import MySQLdb
# Database configuration
db_config = {
'host': 'localhost',
'user': 'root',
'passwd': 'computing',
'db': 'AdventureWorks2019', # Here you select Sakila database
}
# Create a connection to the database
conn = MySQLdb.connect(**db_config)
# Create a cursor object to interact with the database 