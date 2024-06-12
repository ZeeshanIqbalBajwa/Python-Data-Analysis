import logging
import re
import numpy as np
import pandas as pd
import sqlalchemy as db
from sqlalchemy_utils import create_database, database_exists
from functools import wraps
import configparser

logging.basicConfig(filename='./log.log', format="%(levelname)s:%(asctime)s - %(message)s",
                    level=logging.DEBUG, datefmt="%d-%b-%y %H:%M:%S")

def log_function_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"Calling function: {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_function_call
def establish_connection(username, password, database, host='localhost', port=3306):
    try:
        db_conn = db.create_engine(
            f"mariadb+pymysql://{username}:{password}@{host}/{database}")
        if not database_exists(db_conn.url):
            create_database(db_conn.url)
        connection = db_conn.connect()
        logging.info(f"Connected to DB.")
        return db_conn, connection
    except Exception as e:
        logging.error("Failed to connect to DB.")
        raise e

@log_function_call
def create_table(db_conn, table_name, fields):
    metadata = db.MetaData()
    columns = [db.Column(field_name, field_type) for field_name, field_type in fields]
    ne_inventory_table = db.Table(table_name, metadata, *columns)
    metadata.create_all(db_conn, checkfirst=True)
    logging.info(f"Database table '{table_name}' has been created")

@log_function_call
def read_fields_from_ini(filename):
    config = configparser.ConfigParser()
    config.read(filename)

    database_section = config['Database']
    username = database_section['username']
    password = database_section['password']
    database = database_section['database']

    table_section = config['Table']
    table_name = table_section['table_name']

    fields = []
    type_map = {
        'String': db.String,
        'Integer': db.Integer,
        'Float': db.Float,
        'DateTime': db.DateTime
    }
    for field_name, field_type_str in config.items('Fields'):
        field_type_parts = field_type_str.split('(')
        field_type_name = field_type_parts[0]
        field_type_args = ()
        if len(field_type_parts) > 1:
            field_type_args = tuple(map(int, re.findall(r'\d+', field_type_parts[1])))
        field_type = type_map.get(field_type_name)
        if field_type is None:
            logging.error(f"Unknown field type: {field_type_name}")
            continue
        fields.append((field_name, field_type(*field_type_args)))

    return username, password, database, table_name, fields

@log_function_call
def load_ne_coords(db_conn, connection,table_name):
    try:
        # Data Reading and Manipulation
        input_file = pd.read_csv("./data_sheets/output.csv", usecols=[
            'ne-id', 'ne-name', 'product', 'type', 'version', 'communication-state', 'latitude', 'longitude'],
                                 dtype={'siteName': 'string'})
        input_file = input_file.rename(
            columns={"ne-id": "siteId", "ne-name": "siteName", "type": "chassisType","version": "softwareVersion",
             "communication-state": "snmpReachability", "latitude": "lat", "longitude": "lng"})

        input_file['product'] = np.where(input_file['product'].str.contains('Cisco'), 'Cisco', 'Nokia')
        input_file.insert(loc=2, column='areaCode', value=None)
        input_file.insert(loc=2, column='equipmentType', value=None)
        # site_info = input_file['siteName'].str.split("-")
        input_file['areaCode'] = input_file['siteName'].str.extract(
            r"^(\D{3}|\D{2})-")[0]
        input_file = input_file.query(
            "~chassisType.str.contains('^Wavence',case=False) and ~chassisType.str.contains('^NOKIA AIM',case=False) and ~chassisType.str.contains('^VSR',case=False) and ~chassisType.str.contains('SAS') and ~siteName.str.contains('-RR-',case=False) and ~siteName.str.contains('-BNG-')")
        for idx, row in input_file.iterrows():
            site_name_split = row['siteName'].split('-')
            if 'CSG' in site_name_split:
                input_file.at[idx, 'equipmentType'] = 'CSG'
            elif 'PREAGG' in site_name_split or 'SCSG' in site_name_split or 'PRAGG' in site_name_split:
                input_file.at[idx, 'equipmentType'] = 'PREAGG'
            elif 'AGGR' in site_name_split or 'AGG' in site_name_split:
                input_file.at[idx, 'equipmentType'] = 'AGG'

            if re.search(r'^(7705[-| ]SAR)', row['chassisType']):
                input_file.at[idx, 'equipmentType'] = 'CSG'

        area_code_map = pd.read_excel("./data_sheets/Area_Code_Map.xlsx")
        input_file = input_file.merge(area_code_map, how='inner',
                                        right_on='Area Code', left_on='areaCode')
        input_file.drop('Area Code', axis=1, inplace=True)
        input_file = input_file.drop_duplicates(subset='siteId')

        # Update 'date' column based on the merged_df
        input_data = './data_sheets/EOM_Date.csv'
        df = pd.read_csv(input_data,encoding='ISO-8859-1')
        selected_columns1 = df[[
            'IIB Network Elements', ' Current SW Version ', 'SW EoM (C10) Date']]
        merged_df = pd.merge (
            selected_columns1, input_file, left_on=[
                            'IIB Network Elements', ' Current SW Version '], right_on=['chassisType', 'softwareVersion'], how='outer', indicator=True)
        matched_df = merged_df[merged_df['_merge'] == 'both']
        matched_df = matched_df[[
            'chassisType', 'softwareVersion', 'SW EoM (C10) Date']].drop_duplicates()
        matched_df['SW EoM (C10) Date'] = pd.to_datetime(
            matched_df['SW EoM (C10) Date'], format='mixed')
        mapping = matched_df.set_index(
            ['chassisType', 'softwareVersion']).to_dict()['SW EoM (C10) Date']
        input_file['expiredDate'] = input_file.apply(
            lambda row: mapping.get((row['chassisType'], row['softwareVersion']), pd.NaT), axis=1)

        cruncher = './data_sheets/cruncher result.xlsx'
        cr = pd.read_excel(cruncher)
        merged_data = pd.merge(cr, input_file, on='chassisType', how='outer', indicator=True)
        matched_rows = merged_data[merged_data['_merge'] == 'both']
        matched_rows = matched_rows[['chassisType', 'EOL']].drop_duplicates()
        mapping = matched_rows.set_index('chassisType').to_dict()['EOL']
        input_file['EOL'] = input_file['chassisType'].map(mapping)
        logging.info(f"Final Input file: {input_file}")

        input_file.to_sql(table_name, db_conn, if_exists='replace', index=False)
        connection.close()
        db_conn.dispose()
    except Exception as e:
        logging.error(f"An error occurred during data processing: {str(e)}")
        return
    finally:
        if 'connection' in locals():
            connection.close()
        if 'db_conn' in locals():
            db_conn.dispose()


@log_function_call
def main():
    try:
        username, password, database, table_name, fields = read_fields_from_ini('config.ini')
        db_conn, connection = establish_connection(username, password, database)
        create_table(db_conn, table_name, fields)
        load_ne_coords(db_conn, connection,table_name)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    main()