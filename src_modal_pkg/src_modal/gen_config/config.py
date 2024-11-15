import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

import os
import yaml
import json
import praw
import sqlite3
from crewai import LLM

print('CONFIG LOADED !!!!')

current_dir = os.path.dirname(os.path.abspath(__file__))

# Loading reddit_api_keys.json from ../src_modal/api_keys.json
reddit_api_file_path = os.path.join(current_dir, '..', 'reddit_keys.json')
with open(reddit_api_file_path, 'r') as file:
    reddit_api_keys = json.load(file)   

current_dir = os.path.dirname(os.path.abspath(__file__))     

openai_gpt4o_mini = LLM(model="gpt-4o-mini",
                                temperature=0.7,
                                api_key=os.environ["OPENAI_API_KEY"],
                                base_url="https://api.openai.com/v1")

reddit_list = []
for praw_acct in reddit_api_keys['praw']:    
    reddit_item = praw.Reddit(client_id=praw_acct['client_id'],
                              client_secret=praw_acct['client_secret'],
                              user_agent=praw_acct['user_agent'],
                              username=praw_acct['username'],
                              check_for_async=False)
    reddit_list.append(reddit_item)

# These config variables will be used in post filtering,  scoring & drafting
comment_dict = {}
comment_dict_copy = {}
latest_time_str = ''
oldest_time_str = ''

# This in_data will get populated with in_data passed from calling app
in_data = {}

# db_path and table_name will be set from db init function
db_path = ''
table_name = ''

