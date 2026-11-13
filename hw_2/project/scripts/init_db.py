import os
import duckdb

data_path = "data/raw/archive"
db_file = "olist.db"

con = duckdb.connect(db_file)

csv_files = [f for f in os.listdir(data_path) if f.endswith('.csv')]

for file in csv_files:
    
    table_name = file.replace('_dataset.csv', '').replace('.csv', '')
    file_path = os.path.join(data_path, file)
    
    
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_path}')")
    print(f"Таблица '{table_name}' создана из {file}")

con.close()