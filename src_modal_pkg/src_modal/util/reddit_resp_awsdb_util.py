import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

import sqlite3
import os
from src_modal.gen_config import config
from datetime import datetime
import json
import psycopg2

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

def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=os.getenv('AWS_DB_HOST'),
            database=os.getenv('AWS_DB_NAME'),
            user=os.getenv('AWS_DB_USER'),
            password=os.getenv('AWS_DB_PASSWORD'),
            port=os.getenv('AWS_DB_PORT')
        )
        print(f"Successfully connected to DB - {os.getenv('DB_HOST')}")
        return connection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None
    
def init_db_and_table():
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the table exists & CREATE if it doesn't
    table_name = config.in_data['user_id']
    create_table_query = f'''
    CREATE TABLE IF NOT EXISTS '{table_name}' (
        comment_userid_keycombo TEXT PRIMARY KEY,
        phase TEXT,
        meta_details TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    '''    

    cursor.execute(create_table_query)
    conn.commit()
    cursor.close()
    conn.close()
    out_str = f'Init DB and Table - {config.db_path}-{config.table_name} - Success'
    
    return out_str 

def insert_update_db_records(input_list):
    
    update_cnt = 0  
    insert_cnt = 0
    
    for input_dict in input_list:
        if input_dict['action'] == 'insert':
            insert_status = insert_db_record(input_dict) 
            insert_cnt += insert_status['count'] # status = 1 if success, 0 if failed
        else:
            update_status = update_db_record(input_dict) 
            update_cnt += update_status['count']
            
    output_status = f'{os.getenv('AWS_DB_NAME')}-{config.table_name}- Insert: {insert_cnt} Updt: {update_cnt} Tot: {len(input_list)}'
    return output_status 

# Function to insert records
def insert_db_record(input_dict):
    comment_userid_keycombo = input_dict['comment_userid_keycombo']
    phase = input_dict['phase']  
    meta_details_json = json.dumps(input_dict['meta_details'])
    created_at = input_dict['created_at']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    insert_query = f'''
    INSERT INTO {config.table_name} (comment_userid_keycombo, phase, meta_details, created_at)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (comment_userid_keycombo) DO NOTHING;
    '''
    values = (comment_userid_keycombo, phase, meta_details_json, created_at)    
    
    try:
        cursor.execute(insert_query, values)
        conn.commit()
        insert_status = {"status": "success", "message": "Record inserted successfully", "count": 1} 
    except Exception as e:
        insert_status = 0  
        print(f'{comment_userid_keycombo} - Insert Failed - {str(e)}')
        insert_status = {"status": "success", "message": "Insert failed", "count": 0} 
    finally:
        cursor.close()
        conn.close()             
        
    return insert_status
   
def update_db_record(input_dict, conn, cursor):   
        
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
    
    conn = get_db_connection()
    cursor = conn.cursor()             
    
    # SQL query to update 'meta_details' column where comment_user_id matches
    try:
        if input_phase == db_phase:
            update_query = f'''
                            UPDATE {config.table_name}
                            SET meta_details = %s
                            WHERE comment_userid_keycombo = %s;
                            '''
            values = (meta_details_json, comment_userid_keycombo)               
            cursor.execute(update_query, values)     
        else:
            update_query = f'''
                            UPDATE {config.table_name}
                            SET meta_details = %s, phase = %s
                            WHERE comment_userid_keycombo = %s;
                            '''
            values = (meta_details_json, input_phase, comment_userid_keycombo)               
            cursor.execute(update_query, values)
            update_status = {"status": "success", "message": "Record updated successfully", "count": 1}            
    except Exception as e:
        print(f'{comment_userid_keycombo} - Update Failed - {str(e)}')
        update_status = {"status": "update_failed", "message": "Update Failed", "count": 0}
    finally:
        cursor.close()
        conn.close()                           
    
    return update_status

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
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor() 
    
    comment_userid_keycombo = input_dict['comment_userid_keycombo']
    
    try:
        
        # SQL query to fetch a record based on comment_userid_keycombo
        select_query = f'''SELECT * FROM {config.table_name} WHERE comment_userid_keycombo = %s;'''
        
        cursor.execute(select_query, (comment_userid_keycombo,))
        
        db_rec = cursor.fetchone()  # Fetch the first record that matches
        
        if db_rec:
            match_status = check_for_correct_record(input_dict, db_rec)
            # If matching record exists, match_status = "success"
            # If record exists but not matching, match_status =  'process_flow_step_not_found', "llm_not_found" etc.
            fetch_status = {"status": match_status, "record": db_rec}
        else:
            fetch_status = {"status": "not_found", "record": "Record not found"}   
    except Exception as e:
        # Handle  exceptions
        fetch_status = {"status": "Error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()
        
    return fetch_status

def delete_db_record(input_dict):
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor() 
    
    comment_userid_keycombo = input_dict['comment_userid_keycombo']

    delete_query = "DELETE FROM {config.table_name} WHERE comment_userid_keycombo = %s;"
    
    try:
        cursor.execute(delete_query, (comment_userid_keycombo,))
        conn.commit()
        delete_status = {"message": "Record deleted successfully"}
    except Exception as e:
        delete_status = {"delete-error": str(e)}
    finally:
        cursor.close()
        conn.close()
        
    return delete_status