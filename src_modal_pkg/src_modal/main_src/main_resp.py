import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import yaml
import os
import json
from src_modal.platform_src.reddit_resp import reddit_resp
from src_modal.platform_src.twitter_resp import twitter_resp
from src_modal.gen_config import config

print('main_resp.py')

def main_response_process():
    
    platform = config.in_data['functionality'].split('_')[-1]
    print(f"Initiating {config.in_data['functionality']} for {platform}")
    logger.info(f"Initiating {config.in_data['functionality']} for {platform}")
    
    if platform == "reddit":
        out = reddit_resp()
    elif platform == "twitter":
        out = twitter_resp()
        
    return out
    
    