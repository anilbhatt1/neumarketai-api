import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import yaml
import os
import json
from reddit_scan.platform_src.reddit_resp import reddit_resp
from reddit_scan.gen_config import config

print('main_resp.py')

def main_response_process():

    logger.info(f"Initiating Lead-Finder Reddit scan")
    
    out = reddit_resp()
       
    return out
    
    