import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import os
import time
from src_modal.agent_src.reddit_resp_keyword_gen import reddit_resp_keyword_gen
from src_modal.util.reddit_resp_search import *
from src_modal.agent_src.reddit_resp_filter import reddit_resp_filter
from src_modal.agent_src.reddit_resp_score import reddit_resp_score
from src_modal.agent_src.reddit_resp_draft import reddit_resp_draft
from src_modal.util.reddit_resp_db_util import init_db_and_table, insert_update_db_records
from src_modal.gen_config import config

print('reddit_resp.py')

def reddit_resp():  
    
    out_str = init_db_and_table()
    print(f'init_db_and_table : {out_str}')
    
    search_keywords = reddit_resp_keyword_gen()
    
    start_time = time.time()
    reddit_posts, reddit_post_ids = reddit_resp_search(search_keywords)
    reddit_data, unique_post_ids, unique_comment_ids = condense_data(reddit_posts, reddit_post_ids)
    create_comment_dict(reddit_data)
    trimmed_comments, latest_dt, oldest_dt = process_condensed_data(reddit_data)
    print(f'Reddit Time window to consider : {latest_dt} to {oldest_dt}')    
    end_time = time.time()
    time_taken = (end_time - start_time) / 3600
    logger.info(f"Reddit Search complete Time taken So far : {time_taken:.4f} hours")
    
    relevant_comments, db_update_list = reddit_resp_filter(reddit_data)
    db_update_status = insert_update_db_records(db_update_list)
    logger.info(f' Filter db_update_status : {db_update_status}')
    end_time = time.time()
    time_taken = (end_time - start_time) / 3600    
    logger.info(f"Filter complete Time taken So far : {time_taken:.4f} hours")
    
    comments_for_response, db_update_list = reddit_resp_score(relevant_comments)
    db_update_status = insert_update_db_records(db_update_list)
    logger.info(f' Score db_update_status : {db_update_status}')
    end_time = time.time()
    time_taken = (end_time - start_time) / 3600    
    logger.info(f"Score complete Time taken So far : {time_taken:.4f} hours")    
    
    draft_response, db_update_list = reddit_resp_draft(comments_for_response)
    db_update_status = insert_update_db_records(db_update_list)
    logger.info(f' Draft db_update_status : {db_update_status}')
    end_time = time.time()
    time_taken = (end_time - start_time) / 3600    
    logger.info(f"Draft complete Time taken So far : {time_taken:.4f} hours")
    out = draft_response          
    
    return out