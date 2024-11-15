from src_modal.gen_config import config

print('main_src_util.py')

def main_util_resp_print(out_response):
    
    
    if isinstance(out_response, dict):
        cnt = 0
        for comm_id, response in out_response.items():     
            cnt += 1
            print(f'---{cnt}---')   
            print(comm_id, ':', config.comment_dict_copy[comm_id]['score'])
            print(comm_id, ':', config.comment_dict_copy[comm_id]['post_id'])        
            print('Actual :', config.comment_dict_copy[comm_id]['text'])     
            print(f'----')   
            print('Respon :', response)
            print('***************')
    elif isinstance(out_response, str):
        print(f'Out response : {out_response}')
    elif isinstance(out_response, list):
        for idx, resp in enumerate(out_response):
            print(f'idx : {idx} - {resp}')