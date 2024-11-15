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
from src_modal.gen_config import config

current_dir = os.path.dirname(os.path.abspath(__file__))

# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_agent_yaml')
agent_yaml_path = os.path.join(current_dir, '..', 'agent_yaml', 'reddit_resp_agent_yaml', 'reddit_resp_keyword_gen_ag.yaml')
with open(agent_yaml_path, 'r') as yaml_file:
    agent_cfg_data = yaml.safe_load(yaml_file)
    
# Path to the YAML file (One directory up to src_runpod, then into 'agent_yaml/reddit_resp_task_yaml')
task_yaml_path = os.path.join(current_dir, '..', 'task_yaml', 'reddit_resp_task_yaml',  'reddit_resp_keyword_gen_tk.yaml')
with open(task_yaml_path, 'r') as yaml_file:
    task_cfg_data = yaml.safe_load(yaml_file)   
  
class KeywordOutput(BaseModel):
    keyword: str

def reddit_resp_keyword_gen():

    backstory = agent_cfg_data['keyword_generator']['backstory'] 
    goal = agent_cfg_data['keyword_generator']['goal']
    role = agent_cfg_data['keyword_generator']['role']
    llm_name = agent_cfg_data['keyword_generator']['llm_name']
    llm_agent = getattr(config, llm_name)    
    keyword_generator = Agent(role=role,
                            goal=goal,
                            backstory=backstory,
                            allow_delegation=False,
                            verbose=False,
                            llm=llm_agent,
                                )    

    description = task_cfg_data['keyword_generation_task']['description']
    expected_out = task_cfg_data['keyword_generation_task']['expected_out'] 
            
    keyword_generation_task = Task(
                                description=description,
                                expected_output=expected_out,
                                # output_json=KeywordOutput,
                                agent=keyword_generator,
                                )
    
    keyword_crew = Crew(
                        agents=[keyword_generator,],
                        tasks=[keyword_generation_task,],
                        verbose=False,
                        )
    
    product_long = config.in_data['product_long_description']
    product_name = config.in_data['product_name']
    domain = config.in_data['domain']
    platforms_to_search = config.in_data['platforms_to_search']
    user_supplied_keywords = config.in_data['user_supplied_keywords']   
    num_keywords_to_generate = config.in_data['num_keywords_for_search'] - len(user_supplied_keywords)
    print(f"config.in_data['subkeywords_to_generate'] : {config.in_data['num_keywords_for_search']}")
    print(f'len(user_supplied_keywords) : {len(user_supplied_keywords)}')
    print(f'num_keywords_to_generate : {num_keywords_to_generate}')

    if num_keywords_to_generate > 0:
        input_dict = {"product_long": product_long,
                    "product_name": product_name,
                    "domain": domain,
                    "platforms_to_search": platforms_to_search,
                    "user_supplied_keywords": user_supplied_keywords, 
                    "num_keywords_to_generate": num_keywords_to_generate,}
        keyword_result = keyword_crew.kickoff(inputs=input_dict)
        # print(f'type(keyword_result) : {type(keyword_result)}')
        print(f'keyword_result.raw : {keyword_result.raw}')
        # try:
        #     keyword_json_out = ast.literal_eval(keyword_result.json)
        #     print(keyword_json_out)
        # except:
        #     print(f'keyword gen EXCEPTION IN PARSING - USING ONLY {domain} as keyword')
        #     keyword_json_out = {"keyword": f"{domain}"}
        
        # generated_keywords = keyword_result.raw['keyword'].split(", ")
        
        keyword_result = ' '.join(keyword_result.raw.replace('\n', '').split())
        generated_keywords = keyword_result.split(", ")
    else:
        generated_keywords = [] 
    print(f'generated_keywords before filtering : {generated_keywords}')   

    user_supplied_keywords_lower = []
    for kw in config.in_data['user_supplied_keywords']:
        user_supplied_keywords_lower.append(kw.lower())
    
    for kw in generated_keywords:
        kw_lower = kw.lower()
        if kw_lower in user_supplied_keywords_lower:           
            generated_keywords.remove(kw)            
            
    if len(generated_keywords) > num_keywords_to_generate:
        generated_keywords = generated_keywords[:num_keywords_to_generate]
    
    keywords_list = generated_keywords + config.in_data['user_supplied_keywords']
    search_keywords = list(set(keywords_list))    # Remove duplicates
    print(f'generated_keywords after filtering : {generated_keywords}')
    print(f'Final keywords for search : {len(search_keywords)} : {search_keywords}')
       
    return search_keywords