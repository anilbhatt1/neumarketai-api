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
agent_yaml_path = os.path.join(current_dir, '..', 'agent_yaml', 'reddit_resp_agent_yaml', 'reddit_resp_filter_ag.yaml')
with open(agent_yaml_path, 'r') as yaml_file:
    agent_cfg_data = yaml.safe_load(yaml_file)
    
# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_task_yaml')
task_yaml_path = os.path.join(current_dir, '..', 'task_yaml', 'reddit_resp_task_yaml',  'reddit_resp_filter_tk.yaml')
with open(task_yaml_path, 'r') as yaml_file:
    task_cfg_data = yaml.safe_load(yaml_file)
    
# Function to get the current timestamp in CCYYMMDD HH:MM:SS format
def get_current_timestamp():
    return datetime.now().strftime('%Y%m%d %H:%M:%S')

def is_within_time_window(created_dt_str, oldest_time_str, newest_time_str):
    # Convert string dates to datetime objects
    created_dt = datetime.strptime(created_dt_str, '%Y-%m-%d %H:%M:%S')
    oldest_time = datetime.strptime(oldest_time_str, '%Y-%m-%d %H:%M:%S')
    newest_time = datetime.strptime(newest_time_str, '%Y-%m-%d %H:%M:%S')
    
    # Check if created_dt is within the time window
    if oldest_time <= created_dt <= newest_time:
        return True
    else:
        return False
    
class DecisionOutput(BaseModel):
    decision: str
    justification: str 
   
def reddit_resp_filter(condensed_reddit_data):
    
    product_long = config.in_data['product_long_description']
    product_short = config.in_data['product_short_description']
    product_name = config.in_data['product_name']
    oldest_time_str = config.oldest_time_str
    latest_time_str = config.latest_time_str
    domain = config.in_data['domain']
    user_id = config.in_data['user_id'] 
    print(f'user_id : {user_id}')   
    print(f'Time window for filtering : {oldest_time_str} to {latest_time_str}')  
    
    backstory = agent_cfg_data['content_filter_analyst']['backstory'] 
    goal = agent_cfg_data['content_filter_analyst']['goal']
    role = agent_cfg_data['content_filter_analyst']['role'] 
    llm_name = agent_cfg_data['content_filter_analyst']['llm_name']    
    llm_agent = getattr(config, llm_name)
    content_filter_analyst = Agent(
                                role=role,
                                goal=goal,
                                backstory=backstory,
                                allow_delegation=False,
                                verbose=False,
                                llm=llm_agent,
                                )
    
    description = task_cfg_data['content_filter_task']['description']
    expected_out = task_cfg_data['content_filter_task']['expected_out'] 
            
    content_filter_task = Task(
                                description=description,
                                expected_output=expected_out,
                                output_json=DecisionOutput,
                                agent=content_filter_analyst,
                                )

    filter_crew = Crew(
                        agents=[content_filter_analyst,],
                        tasks=[content_filter_task,],
                        verbose=False,
                    )

    tot_cnt = 0
    filter_cnt = 0    
    decision_id_lst = []
    old_comments_id_lst = []
    relevant_comment_id_dict = {}
    db_update_list = []
    found_in_db = 0
    process_flow_step = 'reddit_resp_filter'
    
    for idx, reddit_data_item in enumerate(condensed_reddit_data):
        
        comment_lst = []       
        
        for idx2, comment_data in enumerate(reddit_data_item):            
           
            db_update_dict = {}
            tot_cnt += 1            
            comm_id = comment_data['comment_id']
            keycombo = comment_data['keycombo'] 
            comm_age = comment_data['age']
            comm_create_dt = comment_data['created_date']  
            
            if is_within_time_window(comm_create_dt, oldest_time_str, latest_time_str):           
                      
                filter_cnt += 1        
                db_search_dict = {}
                db_search_dict['comment_userid_keycombo'] = comm_id + '_' + user_id + '_' + keycombo
                db_search_dict['llm_name'] = llm_name
                db_search_dict['process_flow_step'] = process_flow_step
                
                db_status = fetch_db_record(db_search_dict)
                
                # This comment was already filtered, so fetching it from DB directly
                # If it is relevant, will be passed to the next step
                if db_status['status'] == "success":

                    print(f'FILTER FOUND {filter_cnt}/{tot_cnt}th - {comm_id} - {comm_age} - {comm_create_dt}')                   
                    db_rec = db_status['record'] # existing record residing in DB in raw format
                    db_meta_rec = db_rec[2] # meta_details is 3rd column in DB
                    db_meta_details_dict = json.loads(db_meta_rec) # Loading existing meta_details as json
                    db_rec_decision = db_meta_details_dict['filter']
                    db_rec_justify = db_meta_details_dict['filter_justify']
                    if db_rec_decision == 'relevant':
                        relevant_comment_id_dict[comm_id] = keycombo                       
                    decision_id_lst.append(comm_id)
                    config.comment_dict_copy[comm_id]['decision'] = db_rec_decision
                    config.comment_dict_copy[comm_id]['d_justify'] = db_rec_justify                                
                    found_in_db += 1
                    
                # Expected DB record not_found
                else:                    
                        
                    comment_text = comment_data['text']
                    print(f"FILTERING BCOZ {db_status['status']} - {filter_cnt}/{tot_cnt}th - {comm_id} - {comm_age} - {comm_create_dt}")   
                    input_dict = {"comment_id": comm_id,
                                  "input_data": comment_text,
                                  "product_long": product_long,
                                  "product_short": product_short,
                                  "product_name": product_name,
                                  "domain": domain}
                    decision_result = filter_crew.kickoff(inputs=input_dict)
                    
                    try:
                        json_out = ast.literal_eval(decision_result.json)
                        if 'decision' in json_out.keys() and 'justification' in json_out.keys():
                            decision = json_out['decision']
                            justify  = json_out["justification"]
                        else:
                            decision, justify = reddit_resp_decision_string(str(json_out))  
                        json_out['comment_id'] = comm_id
                    except:
                        decision, justify = reddit_resp_decision_string(decision_result.raw)            
                        json_out = {'comment_id': comm_id, 'decision': str(decision), 'justification': str(justify)}
                    
                    decision_id_lst.append(comm_id)
                    config.comment_dict_copy[comm_id]['decision'] = decision
                    config.comment_dict_copy[comm_id]['d_justify'] = justify
                    
                    if decision == 'relevant':
                        relevant_comment_id_dict[comm_id] = keycombo
                        
                    if db_status['status'] == "Error":
                        print(f"DB Error : {db_status['message']}")
                    else:
                        db_update_dict['record'] = db_status["record"]  # DB record fetched in raw format                  
                    
                        current_time = get_current_timestamp()
                        db_update_dict['comment_userid_keycombo'] = comm_id + '_' + user_id + '_' + keycombo                        
                        sub_dict = {process_flow_step : llm_name, 'filter': decision, 'filter_date':current_time, 'filter_justify':justify}
                        db_meta_details = sub_dict
                        db_update_dict['meta_details'] = db_meta_details
                        db_update_dict['phase'] = 'filter'
                        db_update_dict['process_flow_step'] = process_flow_step
                        db_update_dict['created_at'] = current_time   # Will be used only for Insert                                   
                                              
                        # Comment_userid_keycombo record is there, but process_flow_step not there in metadetails
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
                        
                        # DB record for Comment_userid_keycombo itself not_found
                        else:
                            db_update_dict['action'] = "insert"
                        
                        db_update_list.append(db_update_dict)                    
            
            else:
                # print(f" Old comment {comm_id} - {comm_age} - {comm_create_dt}")
                old_comments_id_lst.append(comm_id)
    
    print(f'Time window considered: {config.latest_time_str} till {config.oldest_time_str}')
    print(f'Relevant : {len(relevant_comment_id_dict)} / {tot_cnt}')
    print(f'Found in DB : {found_in_db} / {tot_cnt}')
    print(f'Newly filtered by AI now : {len(db_update_list)} / {tot_cnt}')
    print(f'Processed : {len(decision_id_lst)} == {filter_cnt} Old : {len(old_comments_id_lst)} Tot:{tot_cnt}') 

    #output_file_path = os.path.join(current_dir, '..', '..','outputfiles', 'decision_out.txt')  
   
    #out_lst = reddit_resp_prep_csv_output(decision_id_lst, 'filter', config.comment_dict_copy, output_file_path) 
    
    return relevant_comment_id_dict, db_update_list