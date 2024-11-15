import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import argparse
import yaml
import os
from src_modal.main_src.main_resp import main_response_process
from src_modal.main_src.main_lead import main_lead_process
from src_modal.util.main_src_util import main_util_resp_print
from src_modal.gen_config import config
from src_modal.agent_src.reddit_resp_keyword_gen import reddit_resp_keyword_gen

print(f'main.py')

def handle_main_response(in_data):
    
    logger.info(f'handle_main_response')   
    
    config.in_data = in_data
    print(f'config.in_data : {config.in_data['functionality']}')      

    if in_data['request_type'] == "leadfinder_keyword_gen":
        keywords = reddit_resp_keyword_gen()
        return {"keywords": keywords}
    
    func_route = in_data['functionality'].split('_')[0]
    
    if func_route == "response":
        out = main_response_process()
        main_util_resp_print(out)
        logger.info('Finished handle_main_response()')
    elif func_route == "lead":
        out = main_lead_process()
        
    return out