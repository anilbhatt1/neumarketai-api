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

print(f'reddit_resp_draft.py {current_dir}')

# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_agent_yaml')
agent_yaml_path = os.path.join(current_dir, '..', 'agent_yaml', 'reddit_resp_agent_yaml', 'reddit_resp_draft_ag.yaml')
with open(agent_yaml_path, 'r') as yaml_file:
    agent_cfg_data = yaml.safe_load(yaml_file)
    
# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_task_yaml')
task_yaml_path = os.path.join(current_dir, '..', 'task_yaml', 'reddit_resp_task_yaml',  'reddit_resp_draft_tk.yaml')
with open(task_yaml_path, 'r') as yaml_file:
    task_cfg_data = yaml.safe_load(yaml_file)
    
# Function to get the current timestamp in CCYYMMDD HH:MM:SS format
def get_current_timestamp():
    return datetime.now().strftime('%Y%m%d %H:%M:%S')
    
class ResponseOutput(BaseModel):
    responz: str
    
def reddit_resp_draft(comment_ids_dict_for_response):
    
    logger.info(f'reddit_resp_draft')
    product_long = config.in_data['product_long_description']
    product_short = config.in_data['product_short_description']
    product_name = config.in_data['product_name']
    domain = config.in_data['domain']
    product_url = config.in_data['product_url']
    user_id = config.in_data['user_id']
    
    backstory = agent_cfg_data['response_drafter']['backstory'] 
    goal = agent_cfg_data['response_drafter']['goal']
    role = agent_cfg_data['response_drafter']['role']
    llm_name = agent_cfg_data['response_drafter']['llm_name']
    llm_agent = getattr(config, llm_name)     
    response_drafter = Agent(
                                role=role,
                                goal=goal,
                                backstory=backstory,
                                allow_delegation=False,
                                verbose=False,
                                llm=llm_agent,
                                )
    
    description = task_cfg_data['response_drafting_task']['description']
    expected_out = task_cfg_data['response_drafting_task']['expected_out'] 
            
    response_draft_task = Task(
                                description=description,
                                expected_output=expected_out,
                                output_json=ResponseOutput,
                                agent=response_drafter,
                                )

    draft_crew = Crew(
                        agents=[response_drafter,],
                        tasks=[response_draft_task,],
                        verbose=False,
                    )
    
    tot_cnt = 0
    db_update_list = []
    process_flow_step = 'reddit_resp_draft'
    found_in_db = 0
    tot_cnt = 0
    
    for comm_id, keycombo in comment_ids_dict_for_response.items(): 
        
        tot_cnt += 1
        db_update_dict = {}
        
        db_search_dict = {}
        db_search_dict['comment_userid_keycombo'] = comm_id + '_' + user_id + '_' + keycombo
        db_search_dict['llm_name'] = llm_name
        db_search_dict['process_flow_step'] = process_flow_step        
        
        db_status = fetch_db_record(db_search_dict)
        
        # This comment was already drafted, so fetching it from DB directly
        # If it is above threshold, will be passed to the user interface
        if db_status['status'] == "success":

            print(f'DRAFT FOUND {tot_cnt}th - {comm_id}')                   
            db_rec = db_status['record'] # existing record residing in DB in raw format
            db_meta_rec = db_rec[2] # meta_details is 3rd column in DB
            db_meta_details_dict = json.loads(db_meta_rec) # Loading existing meta_details as json
            db_rec_draft = db_meta_details_dict['draft']
            config.comment_dict_copy[comm_id]['draft'] = db_rec_draft                              
            found_in_db += 1
            
        # Expected DB record not_found
        else:
            
            print(f'DRAFTING {tot_cnt}th {comm_id}')
            input_data = config.comment_dict[comm_id]
            context = reddit_resp_get_context(comm_id)      
            input_dict = {"comment_id": comm_id,
                          "input_data": input_data,
                          "context": context,
                          "product_long": product_long,
                          "product_short": product_short,
                          "domain": domain,
                          "product_name": product_name,
                          "product_url": product_url}
            response_draft = draft_crew.kickoff(inputs=input_dict)  
            draft_text = response_draft.tasks_output[0].json_dict['responz']       
            config.comment_dict_copy[comm_id]['draft'] = draft_text

            if db_status['status'] == "Error":
                print(f"DB Error : {db_status['message']}")
            else:
                db_update_dict['record'] = db_status["record"]  # DB record fetched in raw format                  
            
                current_time = get_current_timestamp()
                db_update_dict['comment_userid_keycombo'] = comm_id + '_' + user_id + '_' + keycombo
                sub_dict = {process_flow_step : llm_name, 'draft_date':current_time, 'draft': draft_text}
                db_meta_details = sub_dict
                db_update_dict['meta_details'] = db_meta_details
                db_update_dict['phase'] = 'draft'
                db_update_dict['process_flow_step'] = process_flow_step                                       
                
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
                
                # DB record for Comment_user_id itself not_found
                else:
                    db_update_dict['action'] = "insert"
                
                db_update_list.append(db_update_dict)

    draft_response = {}
    for comm_id in comment_ids_dict_for_response:
        draft_response[comm_id] = config.comment_dict_copy[comm_id]['draft']
    print(f'Resp drafted {len(draft_response)} = Input comms supplied {len(comment_ids_dict_for_response)}')    
    
    processed_comments_ids = list(comment_ids_dict_for_response.keys()) 
    # output_file_path = os.path.join(current_dir, '..', '..','outputfiles', 'draft_out.txt') 
    # out_lst = reddit_resp_prep_csv_output(processed_comments_ids, 'draft', config.comment_dict_copy, output_file_path)
  
    return draft_response, db_update_list     
              