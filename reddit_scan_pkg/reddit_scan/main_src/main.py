import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import argparse
import yaml
import os
from reddit_scan.main_src.main_resp import main_response_process
from reddit_scan.gen_config import config

print(f'main.py')

def handle_main_response(in_data):
    
    logger.info(f'handle_main_response')   
    
    config.in_data = in_data 

    if in_data['request_type'] == "leadfinder_redditscan":
        out = main_response_process()
        
    return out