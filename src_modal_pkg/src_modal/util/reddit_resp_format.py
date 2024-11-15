import os
import re
import yaml
import json
import ast
import praw
import copy
from datetime import datetime, timedelta
from src_modal.gen_config import config

print(f'reddit_resp_format.py')

def reddit_resp_get_api_keys(api_file_path):
    with open(api_file_path, 'r') as file:
        api_keys = json.load(file)   
    return api_keys

def reddit_resp_load_gen_cfg(cfg_file_path):
    with open(cfg_file_path, 'r') as yaml_file:
        gen_cfg_data = yaml.safe_load(yaml_file)
    return gen_cfg_data

def reddit_resp_define_llms():
    llm_api_keys = reddit_resp_get_api_keys

def reddit_resp_decision_string(input_string):

    # pattern = r"'comment_id':\s*'([^']*)',\s*'decision':\s*(\d+)"
    pattern = r"'decision':\s*'([^']*)'"

    # Use re.search to extract the values
    matches = re.search(pattern, input_string)

    if matches:
        decision = matches.group(1)
    else:
        decision = "discard"

    if "justification" in input_string:
        justification = input_string.split("justification")[-1]
    else:
        justification = "Not available"
    
    return decision, justification

def reddit_resp_score_string(input_string):

    #pattern = r"'comment_id':\s*'([^']*)',\s*'score':\s*(\d+)"
    pattern = r"'score':\s*'([^']*)'"

    # Use re.search to extract the values
    matches = re.search(pattern, input_string)

    if matches:
        score = matches[0]
    else:
        score = 0

    if "justification" in input_string:
        justification = input_string.split("justification")[-1]
    else:
        justification = "Not available"
    
    return score, justification

def reddit_resp_responz_string(input_string):

    if "responz" in input_string:
        response = input_string.split("responz")[-1]
    else:
        response = "Not available"
    
    return response

def reddit_resp_get_calendar_date(unix_timestamp):
    date_obj = datetime.utcfromtimestamp(unix_timestamp)
    readable_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
    return readable_date

def reddit_resp_prep_csv_output(comment_lst, step, comment_dict_copy, filename):
    sep = "^"
    out_lst = []
    for comm_id in comment_lst:
        parent_id = comment_dict_copy[comm_id]["parent_id"]
        if parent_id is None:
            parent_id = 'NA'        
        comment_text = comment_dict_copy[comm_id]["text"]
        created = comment_dict_copy[comm_id]['created']
        age = comment_dict_copy[comm_id]['age']

        if step == "filter":
            decision = comment_dict_copy[comm_id]["decision"]
            d_justify  = comment_dict_copy[comm_id]["d_justify"]
            text_str = sep + comm_id + sep + parent_id + sep + decision + sep + d_justify + sep + comment_text + sep
            out_lst.append(text_str)
        elif step == "filter-old":
            text_str = sep + comm_id + sep + parent_id + sep + str(age) + sep + created + sep + comment_text + sep
            out_lst.append(text_str)
        elif step == "score":
            score = comment_dict_copy[comm_id]["score"]
            s_justify = comment_dict_copy[comm_id]["s_justify"]
            text_str = sep + comm_id + sep + parent_id + sep + str(score) + sep + s_justify + sep 
            out_lst.append(text_str)
        elif step == "draft":
            draft = comment_dict_copy[comm_id]["draft"]
            text_str = sep + comm_id + sep + parent_id + sep + draft + sep 
            out_lst.append(text_str)
        elif step == "comment":
            text_str = sep + comm_id + sep + created + sep + comment_text + sep 
            out_lst.append(text_str)

    with open(filename, "w") as file:
        for item in out_lst:
            file.write(item + "\n")  # Add a newline character after each string   
    print(f"File {filename} has been written for {len(out_lst)} items for **{step}**")

    return out_lst

def reddit_resp_get_data_details(comm_id):
    done = 0
    data_details = []
    while done==0:
        if comm_id in config.comment_dict:
            details = config.comment_dict[comm_id]
            data_details.append(details)
            comm_id = details['parent_id']
        else:
            done = 1
    return data_details

# Getting context by avoiding the comment_id and taking only parent_id details
def reddit_resp_get_context(comm_id):     
    done = 0
    context = []
    orig_comm_id = comm_id
    while done==0:
        if comm_id in config.comment_dict:
            details = config.comment_dict[comm_id]
            if comm_id == orig_comm_id:  # Only take parent comment details for context
                pass
            else:
                context.append(details)
            comm_id = details['parent_id']
        else:
            done = 1
    return context

def reddit_resp_get_comment_ids_for_response(post_dict, score_thresh, pct_limit):
    comment_ids_list_for_response = []
    for post_id, comment_score_dict in post_dict.items():
        comment_score_dict_sorted = dict(sorted(comment_score_dict.items(), key=lambda item: item[1], reverse=True))
        num_items_to_consider = int(len(comment_score_dict_sorted) * pct_limit)
        if num_items_to_consider < 1:
            num_items_to_consider = 1
        selected_items = dict(list(comment_score_dict_sorted.items())[:num_items_to_consider])
        selected_comments = list(selected_items.keys())[:num_items_to_consider]
        for comment_id in selected_comments:
            comment_ids_list_for_response.append(comment_id)
    return comment_ids_list_for_response