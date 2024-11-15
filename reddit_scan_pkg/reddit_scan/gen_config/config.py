import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

import os
import yaml
import json
import praw
from crewai import LLM

print('CONFIG LOADED !!!!')

current_dir = os.path.dirname(os.path.abspath(__file__))

# Loading reddit_api_keys.json for PRAW from modal secrets
api_key_str = os.environ["PRAW_TOKEN_1"]
reddit_api_keys = json.loads(api_key_str)

current_dir = os.path.dirname(os.path.abspath(__file__))     

openai_gpt4o_mini = LLM(model="gpt-4o-mini",
                                temperature=0.7,
                                api_key=os.environ["OPENAI_API_KEY"],
                                base_url="https://api.openai.com/v1")

reddit_list = []
for praw_acct in reddit_api_keys:    
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

age_limit = 0.5
thresh_score_for_response = 8.5
pct_of_comments = 0.55
reddit_switch_limit = 2000
reddit_time_filter = "year"
reddit_comment_limit = 1500
reddit_read_limit = [30]

# This in_data will get populated with in_data passed from calling app
in_data = {}