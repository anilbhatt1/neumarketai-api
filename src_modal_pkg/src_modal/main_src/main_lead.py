import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import yaml
import json
from src_modal.gen_config import config

print('main_lead.py')

def main_lead_process():
    logger.info(f"main_lead_process - in_data[functionality] : {config.in_data['functionality']}")