#!/usr/bin/python3
import requests
import json
import re
import csv
import sched
import time
import logging
from datetime import datetime, timedelta


logging.basicConfig(filename='./log.log', format="%(levelname)s:%(asctime)s - %(message)s",
                    level=logging.DEBUG, datefmt="%d-%b-%y %H:%M:%S")


token_info = {"access_token": None, "expires_at": None}

def get_token(NSP_IP, username, password):
    global token_info
    data = {"grant_type": "client_credentials"}
    url = 'https://' + NSP_IP + '/rest-gateway/rest/api/v1/auth/token'
    try:
        if token_info["access_token"] is None or token_info["expires_at"] <= datetime.now():
            response = requests.post(url=url, auth=(username, password), json=data, verify=False)
            response.raise_for_status() 
            res = response.json()
            token_info["access_token"] = res['access_token']
            token_info["expires_at"] = datetime.now() + timedelta(seconds=res['expires_in'])
    except requests.exceptions.RequestException as e:
        logging.error("Error in getting token: %s", e)
    except KeyError as e:
        logging.error("Key error in token response: %s", e)
    except Exception as e:
        logging.error("An error occurred while getting token: %s", e)
    return token_info["access_token"]

def get_inventory_objects_by_offset(NSP_IP, xpath, depth, offset, limit, fields):
    new_dict = {
        "nsp-inventory:input": {
            "xpath-filter": xpath,
            "depth": str(depth),
            "offset": str(offset),
            "limit": str(limit),
            "fields": fields
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token_info["access_token"]
    }
    url = 'https://' + NSP_IP + ':8545/restconf/operations/nsp-inventory:find'
    try:
        payload = json.dumps(new_dict)
        response = requests.request("POST", url, headers=headers, verify=False, data=payload)
        response.raise_for_status() 
        json_data = response.json()
        return json_data
    except requests.exceptions.RequestException as e:
        logging.error("Error in API request: %s", e)
        return None
    except json.JSONDecodeError as e:
        logging.error("Error decoding JSON response: %s", e)
        return None
    except Exception as e:
        logging.error("An error occurred: %s", e)
        return None
        

def get_all_inventory_objects(NSP_IP, xpath, depth, offset, limit, fields):
    all_data = []
    offset = offset
    try:
        while True:
            json_data = get_inventory_objects_by_offset(NSP_IP, xpath, depth, offset, limit, fields)
            if not json_data:
                break
            data = json_data.get("nsp-inventory:output", {}).get("data", [])
            all_data.extend(data)
            end_index = json_data['nsp-inventory:output']['end-index']
            total_count = json_data['nsp-inventory:output']['total-count']
            offset += limit
            if offset >= total_count:
                break
            logging.info(f"entries collected : {end_index}")
            logging.info(f"Total enteries : {total_count}")
    except Exception as e:
        logging.error("An error occurred while getting all data: %s", e)
        return None
    return all_data
