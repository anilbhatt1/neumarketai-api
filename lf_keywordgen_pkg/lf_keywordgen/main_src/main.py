import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import argparse
import yaml
import os
from lf_keywordgen.gen_config import config
from lf_keywordgen.agent_src.keyword_gen import keyword_gen

print(f'main.py')

def handle_main_response(in_data):
    
    logger.info(f'handle_main_response')   
    
    config.in_data = in_data    

    if in_data['request_type'] == "leadfinder_keyword_gen":
        keywords = keyword_gen()
        return {"keywords": keywords}