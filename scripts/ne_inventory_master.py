#!/usr/bin/python3
import os
import csv
import logging
import configparser
from nsp_inventory_restconf import get_inventory_objects_by_offset, get_token, get_all_inventory_objects
from ne_inventory_transformation import main as transformation_main

# ------VARS--------------------
config = configparser.ConfigParser()
config.read('config.ini')
nsp_ip = config['env.var']['nsp_ip']
username = config['env.var']['username']
password = config['env.var']['password']
depth = int(config['env.var']['depth'])
limit = int(config['env.var']['limit'])
offset = int(config['env.var']['offset'])
fields = config['env.var']['fields']
xpath = config['env.var']['xpath']
csv_headers = config['env.var']['csv_headers']


logging.basicConfig(filename='./log.log', format="%(levelname)s:%(asctime)s - %(message)s",
                    level=logging.DEBUG, datefmt="%d-%b-%y %H:%M:%S")

def get_nes():
    try:
        my_token = get_token(nsp_ip, username, password)
        all_data = get_all_inventory_objects(nsp_ip, xpath, depth, offset, limit, fields)
        if all_data:
            process_data(all_data)
    except Exception as e:
        logging.error("An error occurred while fetching or processing data: %s", e)



def recreate_output_file():
    if os.path.exists("output.csv"):
        os.remove("output.csv")
    with open("output.csv", "w", newline="") as csvfile:
        pass


def process_data(all_data):
    try:
        recreate_output_file()
        with open("output.csv", "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(csv_headers)
            for item in all_data:
                row = [item.get(header, "") for header in csv_headers]  
                writer.writerow(row)
        logging.info("Data has been written to the output.csv")
    except Exception as e:
        logging.error(f"An error occurred while processing data: {e}")


if __name__ == '__main__':
    get_nes()
    transformation_main()
