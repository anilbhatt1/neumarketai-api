import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

import os
import re
import yaml
import json
import ast
import copy
from crewai import Agent, Task, Crew, Process
from textwrap import dedent 
from pydantic import BaseModel
from datetime import datetime
from src_modal.gen_config import config
from src_modal.util.reddit_resp_format import *
from src_modal.util.reddit_resp_db_util import fetch_db_record

current_dir = os.path.dirname(os.path.abspath(__file__))

# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_agent_yaml')
agent_yaml_path = os.path.join(current_dir, '..', 'agent_yaml', 'reddit_resp_agent_yaml', 'reddit_resp_score_ag.yaml')
with open(agent_yaml_path, 'r') as yaml_file:
    agent_cfg_data = yaml.safe_load(yaml_file)
    
# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_task_yaml')
task_yaml_path = os.path.join(current_dir, '..', 'task_yaml', 'reddit_resp_task_yaml',  'reddit_resp_score_tk.yaml')
with open(task_yaml_path, 'r') as yaml_file:
    task_cfg_data = yaml.safe_load(yaml_file)
    
# Function to get the current timestamp in CCYYMMDD HH:MM:SS format
def get_current_timestamp():
    return datetime.now().strftime('%Y%m%d %H:%M:%S')
    
class ScoreOutput(BaseModel):
    score: float
    justification: str
    
def reddit_resp_score(relevant_comment_id_dict):
    
    product_long = config.in_data['product_long_description']
    product_short = config.in_data['product_short_description']
    product_name = config.in_data['product_name']
    domain = config.in_data['domain']
    age_limit = config.in_data['age_limit'] 
    thresh_score_for_response = config.in_data['thresh_score_for_response'] 
    pct_of_comments = config.in_data['pct_of_comments']      
    user_id = config.in_data['user_id']
   
    backstory = agent_cfg_data['content_scoring_analyst']['backstory'] 
    goal = agent_cfg_data['content_scoring_analyst']['goal']
    role = agent_cfg_data['content_scoring_analyst']['role']
    llm_name = agent_cfg_data['content_scoring_analyst']['llm_name']
    llm_agent = getattr(config, llm_name)    
    content_score_analyst = Agent(
                                role=role,
                                goal=goal,
                                backstory=backstory,
                                allow_delegation=False,
                                verbose=False,
                                llm=llm_agent,
                                )
    
    description = task_cfg_data['content_scoring_task']['description']
    expected_out = task_cfg_data['content_scoring_task']['expected_out'] 
            
    content_score_task = Task(
                                description=description,
                                expected_output=expected_out,
                                output_json=ScoreOutput,
                                agent=content_score_analyst,
                                )

    score_crew = Crew(
                        agents=[content_score_analyst,],
                        tasks=[content_score_task,],
                        verbose=False,
                    )

    post_comment_score_dict = {}
    db_update_list = []
    process_flow_step = 'reddit_resp_score'
    found_in_db = 0
    tot_cnt = 0 
    
    for comm_id, keycombo in relevant_comment_id_dict.items():

        tot_cnt += 1
        db_update_dict = {}
        
        db_search_dict = {}
        db_search_dict['comment_userid_keycombo'] = comm_id + '_' + user_id + '_' + keycombo
        db_search_dict['llm_name'] = llm_name
        db_search_dict['process_flow_step'] = process_flow_step
        
        db_status = fetch_db_record(db_search_dict)
        
        # This comment was already scored, so fetching it from DB directly
        # If it is above threshold, will be passed to the next step
        if db_status['status'] == "success":        

            print(f'SCORE FOUND {tot_cnt}th - {comm_id}')                   
            db_rec = db_status['record'] # existing record residing in DB in raw format
            db_meta_rec = db_rec[2] # meta_details is 3rd column in DB
            db_meta_details_dict = json.loads(db_meta_rec) # Loading existing meta_details as json
            score = db_meta_details_dict['score']
            justify = db_meta_details_dict['score_justify']
            config.comment_dict_copy[comm_id]['score'] = score
            config.comment_dict_copy[comm_id]['s_justify'] = justify                               
            found_in_db += 1        
        
        # Expected DB record not_found
        else:
            print(f'SCORING {tot_cnt}th - {comm_id}')
            data_details = reddit_resp_get_data_details(comm_id)
            input_dict = {"comment_id": comm_id,
                          "input_data": data_details,
                          "product_long": product_long,
                          "product_short": product_short,
                          "domain": domain,
                          "age": age_limit,
                          "product_name": product_name}        
            scoring_result = score_crew.kickoff(inputs=input_dict)
            try:
                json_out = ast.literal_eval(scoring_result.json)
                if 'score' in json_out.keys() and 'justification' in json_out.keys():
                    score = json_out['score']
                    justify  = json_out["justification"]
                else:
                    score, justify = reddit_resp_score_string(str(json_out))       
            except:
                score, justify = reddit_resp_score_string(scoring_result.raw)  
            config.comment_dict_copy[comm_id]['score'] = score
            config.comment_dict_copy[comm_id]['s_justify'] = justify 

            if db_status['status'] == "Error":
                print(f"DB Error : {db_status['message']}")
            else:
                db_update_dict['record'] = db_status["record"]  # DB record fetched in raw format                  
            
                current_time = get_current_timestamp()
                db_update_dict['comment_userid_keycombo'] = comm_id + '_' + user_id + '_' + keycombo
                sub_dict = {process_flow_step : llm_name, 'score': score, 'score_date':current_time, 'score_justify':justify}
                db_meta_details = sub_dict
                db_update_dict['meta_details'] = db_meta_details
                db_update_dict['phase'] = 'score'
                db_update_dict['process_flow_step'] = process_flow_step
                db_update_dict['created_at'] = current_time   # Will be used only for Insert        
                                   
                # Comment_user_id record is there, but process_flow_step not there 
                # We need to update the process_flow_step and associated keys
                # Hence passing existing db record db_status["record"]
                if db_status['status'] == "process_flow_step_not_found":                     
                    db_update_dict['action'] = "update_process_flow_step"
                    db_update_dict['record'] = db_status["record"]
                
                # Comment_userid_keycombo record, process_flow_step is there, but llm changed
                # We need to update the llm used
                # Hence passing existing db record db_status["record"]                
                elif db_status['status'] == "llm_not_found":
                    db_update_dict['action'] = "update_llm"
                    db_update_dict['record'] = db_status["record"]
                
                # DB record for Comment_user_id itself not_found
                else:
                    db_update_dict['action'] = "insert"
                
                db_update_list.append(db_update_dict)          
        
        # Only certain comments under certain posts that are above threshold score need to be selected for responding. This logic helps in that 
            
        if float(score) >= thresh_score_for_response:    
            post_id = config.comment_dict[comm_id]['post_id']
            if post_id in post_comment_score_dict.keys():
                post_comment_score_dict[post_id][comm_id] = score
            else:
                post_comment_score_dict[post_id] = {}
                post_comment_score_dict[post_id][comm_id] = score         
    
    print(f'**Score Found in DB : {found_in_db} Scored by AI now : {len(db_update_list)}')
    print(f'**Processed : {len(relevant_comment_id_dict)}**')
    
    thresh_list = [7.0, 7.5, 8.0, 8.5, 9.0, 9.5]
    for thresh in thresh_list:
        thresh_up = 0
        score_cnt = 0
        for comm_id, item in config.comment_dict_copy.items():
            if 'score' in item.keys():
                score_cnt += 1 
                if item['score'] >= thresh:
                    thresh_up += 1
        print(f'GE thresh {thresh} : {thresh_up}/{score_cnt}  & LT thresh : {score_cnt - thresh_up}')

    gt_cnt = 0
    refined_post_comment_score_dict = {}
    for post_id, comm_item in post_comment_score_dict.items():
        for comm_id, score in comm_item.items():        
            if score >= thresh_score_for_response:
                gt_cnt += 1
                if post_id in refined_post_comment_score_dict.keys():
                    refined_post_comment_score_dict[post_id][comm_id] = score
                else:
                    refined_post_comment_score_dict[post_id] = {}
                    refined_post_comment_score_dict[post_id][comm_id] = score
    print(f'Total comments > thresh_score_for_response {thresh_score_for_response} : {gt_cnt}') 
    
    comment_ids_list_for_response = reddit_resp_get_comment_ids_for_response(refined_post_comment_score_dict, thresh_score_for_response, pct_of_comments)
    print(f'Number of comments to respond for {pct_of_comments}% : {len(comment_ids_list_for_response)}') 
    
    comment_ids_dict_for_response = {}
    for comm_id in comment_ids_list_for_response:
        keycombo = relevant_comment_id_dict[comm_id]
        comment_ids_dict_for_response[comm_id] = keycombo
    
    processed_comments_ids = list(relevant_comment_id_dict.keys())    
    # output_file_path = os.path.join(current_dir, '..', '..','outputfiles', 'score_out.txt') 
    # out_lst = reddit_resp_prep_csv_output(processed_comments_ids, 'score', config.comment_dict_copy, output_file_path)
    
    return comment_ids_dict_for_response, db_update_list    