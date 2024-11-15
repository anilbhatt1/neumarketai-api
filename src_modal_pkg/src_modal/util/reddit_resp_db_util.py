import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

import sqlite3
import os
from src_modal.gen_config import config
from datetime import datetime
import json

print('reddit_resp_db_util.py')

'''
Sample DB record

comment_user_id = 'lrdizde_userid1_human-robot+tesla-optimus'
phase = 'draft&present' # Possible values : 'draft','score','filter'
meta_details = {'reddit_resp_filter':'gemma2_9b','filter':'relevant','filter_justify':'<reason>','filter_date':'ccyymmdd hh:mm:ss',
		        'reddit_resp_score':'gemma2_9b','score':4.5,'score_justify':'<reason>','score_date':'ccyymmdd hh:mm:ss',
		        'reddit_resp_draft':'gemma2_9b','draft': '<draft>', 'draft_date':'ccyymmdd hh:mm:ss'}
created_at = 'ccyymmdd hh:mm:ss'
'''

def init_db_and_table():
    # Loading sqlite3 database from na/reddit_resp_db.db
    out_str = ' '
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    db_name = config.in_data['functionality'] + '_db.db'
    db_path = os.path.join(current_dir, '..', '..', db_name)
    if os.path.exists(db_path):
        print(f"The database '{db_path}' already exists.")
        out_str += f"The database '{db_path}' already exists."
    else:
        print(f"The database '{db_path}' does not exist.")
        out_str += f"The database '{db_path}' does not exist."
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the table exists
    table_name = config.in_data['user_id']
    cursor.execute(f'''SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';''')
    result = cursor.fetchone()

    # If the table doesn't exist, create it
    if result is None:
        cursor.execute(f'''CREATE TABLE {table_name} (
                            comment_userid_keycombo TEXT PRIMARY KEY,
                            phase TEXT,
                            meta_details TEXT,
                            created_at TEXT
                        );''')
        print(f'Table "{table_name}" created.')
        out_str += f'Table "{table_name}" created.'
    else:
        print(f'Table "{table_name}" already exists.')
        out_str += f'Table "{table_name}" already exists.'
        
    config.db_path = db_path
    config.table_name = table_name

    # Commit and close the connection
    conn.commit()
    conn.close() 
    
    return out_str 

def insert_update_db_records(input_list):
    
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()  
    update_cnt = 0  
    insert_cnt = 0
    
    try:
        # Process each dictionary in the input list
        for input_dict in input_list:
            if input_dict['action'] == 'insert':
                insert_status = insert_db_record(input_dict, conn, cursor) 
                insert_cnt += insert_status # status = 1 if success, 0 if failed
            else:
                update_status = update_db_record(input_dict, conn, cursor) 
                update_cnt += update_status['count']
    except Exception as e:
        output_status = f'Error in DB update for {config.db_path} - {config.table_name}: - {e}'
        print(output_status)
        conn.close() 
        return output_status
            
    # Commit the changes to the database and close the connection
    conn.commit()
    conn.close()   
    output_status = f'{config.db_path}-{config.table_name}- Insert: {insert_cnt} Updt: {update_cnt} Tot: {len(input_list)}'
    return output_status 

# Function to insert records
def insert_db_record(input_dict, conn, cursor):
    comment_userid_keycombo = input_dict['comment_userid_keycombo']
    phase = input_dict['phase']  
    meta_details_json = json.dumps(input_dict['meta_details'])
    created_at = input_dict['created_at']
    
    try:
        cursor.execute(f'''
        INSERT INTO {config.table_name} (comment_userid_keycombo, phase, meta_details, created_at)
        VALUES (?, ?, ?, ?)
        ''', (comment_userid_keycombo, phase, meta_details_json, created_at))
        insert_status = 1
        conn.commit()
    except Exception as e:
        insert_status = 0  
        print(f'{comment_userid_keycombo} - Insert Failed - {str(e)}')      
        
    return insert_status
   
def update_db_record(input_dict, conn, cursor):
    
    try:
        
        comment_userid_keycombo = input_dict['comment_userid_keycombo']
        input_phase = input_dict['phase']
    
        db_rec = input_dict['record'] # This is the existing record residing in DB in raw format
        db_phase = db_rec[1] # phase is 2nd column in DB
        meta_details = db_rec[2] # meta_details is 3rd column in DB
        meta_details_current_dict = json.loads(meta_details) # Loading existing meta_details as json   
        
        meta_details_to_update = input_dict['meta_details']  # This is the input that has updates
        process_flow_step = input_dict['process_flow_step']  # eg: reddit_resp_score        
       
        # Process Flow Step is not there. (Eg: Scoring was not done earlier)
        # eg: 'reddit_resp_score' = 'gemma2', 'score' = '9.5'
        if input_dict['action'] == "update_process_flow_step":
            for key, item in meta_details_to_update.items():
                meta_details_current_dict[key] = item
                
        # LLM changed. (Eg: LLM used for scoring changed, so score also will change)
        # eg: 'reddit_resp_score' = 'gemma2-9b', 'score' = '9.0'
        elif input_dict['action'] == "update_llm":         
            for key, item in meta_details_to_update.items():
                meta_details_current_dict[key] = item    
        
        meta_details_json = json.dumps(meta_details_current_dict) # Converting to Json text     
       
        # SQL query to update 'meta_details' column where comment_user_id matches
        if input_phase == db_phase:        
            cursor.execute(f'''
                UPDATE {config.table_name}
                SET meta_details = ?
                WHERE comment_userid_keycombo = ?
            ''', (meta_details_json, comment_userid_keycombo))      
        else:
            cursor.execute(f'''
                UPDATE {config.table_name}
                SET meta_details = ?, phase = ?
                WHERE comment_userid_keycombo = ?
            ''', (meta_details_json, input_phase, comment_userid_keycombo))               
      
        if cursor.rowcount > 0:
            conn.commit()
            return {"status": "success", "message": "Record updated successfully", "count": 1}
        else:
            print(f'{comment_userid_keycombo} - Update Failed')
            return {"status": "update_failed", "message": "Update Failed", "count": 0}
    
    except sqlite3.OperationalError as e:
        print(f'{comment_userid_keycombo} - UpdateOperationalError - {str(e)}')
        return {"status": "UpdateOperationalError", "message": str(e), "count": 0}
    
    except Exception as e:
        print(f'{comment_userid_keycombo} - UpdateOthererror - {str(e)}')
        return {"status": "UpdateOthererror", "message": str(e), "count": 0}

def check_for_correct_record(input_dict, db_rec):
    
    process_flow_step = input_dict['process_flow_step']
    input_llm_name = input_dict['llm_name']
    
    meta_details = db_rec[2] # meta_details is 3rd column in DB
    meta_details_dict = json.loads(meta_details) # Loading it as json    
   
    if process_flow_step in meta_details_dict.keys():
        pass
    else:
        match_status = 'process_flow_step_not_found'
        return match_status
    
    db_llm_name = meta_details_dict[process_flow_step]
    if db_llm_name == input_llm_name:
        match_status = 'success'
    else:
        match_status = 'llm_not_found'
        
    return match_status
   
def fetch_db_record(input_dict):
    
    # Connect to SQLite database
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()  
    update_cnt = 0  
    insert_cnt = 0   
    
    comment_userid_keycombo = input_dict['comment_userid_keycombo']
    
    try:
        # SQL query to fetch a record based on comment_id and keycombo
        cursor.execute(f'''
            SELECT * FROM {config.table_name} 
            WHERE comment_userid_keycombo = ? 
        ''', (comment_userid_keycombo,))
        
        db_rec = cursor.fetchone()  # Fetch the first record that matches
        
        conn.close()
        
        if db_rec:
            match_status = check_for_correct_record(input_dict, db_rec)
            # If matching record exists, match_status = "success"
            # If record exists but not matching, match_status =  'process_flow_step_not_found', "llm_not_found" etc.
            return {"status": match_status, "record": db_rec}
        else:
            return {"status": "not_found", "record": "Record not found"}
    
    except sqlite3.OperationalError as e:
        conn.close()
        return {"status": "Error", "message": str(e)}
    
    except Exception as e:
        # Handle other types of exceptions
        conn.close()
        return {"status": "Error", "message": str(e)}

