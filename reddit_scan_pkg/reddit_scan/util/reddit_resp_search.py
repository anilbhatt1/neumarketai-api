import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

import yaml
import json
import praw
import copy
from datetime import datetime, timedelta, timezone
from reddit_scan.util.reddit_resp_format import reddit_resp_get_calendar_date
from reddit_scan.gen_config import config

print(f'reddit_resp_search.py')

def calculate_comment_age(unix_timestamp):
    date_obj = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    current_date = datetime.now(timezone.utc)   
    difference_in_days = (current_date - date_obj).days
    age_in_years = round(difference_in_days / 365.25, 5)
    return age_in_years

#Called from reddit_resp_search
def search_for_subreddits(keyword):
    reddit = config.reddit_list[0] # Using first reddit app instance for subreddit search (wont he heavy load)
    subreddits = []
    for subreddit in reddit.subreddits.search_by_name(keyword, exact=False):
        subreddits.append(subreddit.display_name)
    return subreddits

#Called from fetch_posts_from_subreddit
def search_posts(subreddit_name, keyword, reddit_num, reddit_read_count): #, reddit_read_limit, reddit_time_filter):
    posts = []
    post_ids = []

    subreddit = config.reddit_list[reddit_num].subreddit(subreddit_name)
    reddit_read_limit = config.reddit_read_limit[0]
    reddit_time_filter = config.reddit_time_filter
    
    for post in subreddit.search(keyword, sort='new', time_filter=reddit_time_filter, limit=reddit_read_limit):
        age = calculate_comment_age(post.created_utc)
        post_data = {
            'title': post.title,
            "comment_id": post.id,
            'url': post.url,
            'score': post.score,
            'num_comments': post.num_comments,
            'Post_views': post.view_count,
            'upvote_ratio': post.upvote_ratio,
            'author': str(post.author),
            'created_utc': post.created_utc,
            'age': age,
            'image_urls': [],
            'comments': []
        }

        reddit_read_count += 1
        # Check for images in the post
        if hasattr(post, 'url') and \
           ((post.url.endswith('.jpg') or post.url.endswith('.jpeg') or post.url.endswith('.png'))):
            
            post_data['image_urls'].append(post.url)
        
        elif hasattr(post, 'media_metadata'):
            
            for item_id in post.media_metadata:
                media_item = post.media_metadata[item_id]
                if 'm' in media_item and 'image' in media_item['m']:
                    url = media_item.get('s', {}).get('u', None)
                    if url:
                        post_data['image_urls'].append(url)

        # Fetching comments
        post.comments.replace_more(limit=0)
        for comment in post.comments.list():
            age = calculate_comment_age(comment.created_utc)
            comment_data = {
                "comment_id": comment.id,
                "parent_id": comment.parent_id.split('_')[1],
                "text": comment.body,
                "author": str(comment.author),
                "score": comment.score,
                "created_utc": comment.created_utc,
                "age": age,
                "image_url": ""
            }

            reddit_read_count += 1
            # Check for images in comments if applicable
            if hasattr(comment, 'body_html') and 'img src="' in comment.body_html:
                start_index = comment.body_html.find('img src="') + len('img src="')
                end_index = comment.body_html.find('"', start_index)
                comment_data['image_url'] = comment.body_html[start_index:end_index]

            post_data['comments'].append(comment_data)

        posts.append(post_data)
        post_ids.append(post.id)
    
    return posts, post_ids, reddit_read_count

# Called from reddit_resp_search
def fetch_posts_from_subreddit(search_keywords, subreddit_name, reddit_num): #, search_keywords, reddit_read_limit, reddit_time_filter):
    
    subreddit_posts = {}
    subreddit_post_ids = []
    
    subreddit_posts[subreddit_name] = {}
    reddit_read_count = 0
    for keyword in search_keywords:
        posts, post_ids, reddit_read_count = search_posts(subreddit_name, keyword, reddit_num, reddit_read_count) #, reddit_read_limit, reddit_time_filter)    
        subreddit_posts[subreddit_name][keyword] = posts
        subreddit_post_ids.extend(post_ids)
    
    return subreddit_posts, subreddit_post_ids, reddit_read_count

def reddit_resp_search(search_keywords):   
    
    print(f'***reddit_resp_search started***')
    print(f'search_keywords : {len(search_keywords)} - {search_keywords}')
    print(f'reddit_comment_limit set in config : {config.reddit_comment_limit}')
    print(f'reddit_read_limit set in config : {config.reddit_read_limit[0]}')
    print(f'reddit_time_filter set in config : {config.reddit_time_filter}')
    print(f'reddit_switch_limit set in config : {config.reddit_switch_limit}')    
    found_subreddits = [search_for_subreddits(keyword) for keyword in search_keywords]
    all_subreddits = []
    for each in found_subreddits:
        all_subreddits.extend(each)
    all_subreddits = set(all_subreddits)
    subreddit_count = len(all_subreddits)
    print(f'Number of subreddits found : {subreddit_count}')   
    
    reddit_switch_limit = config.in_data['reddit_switch_limit']
    reddit_posts = {}
    reddit_post_ids = []
    tot_reddit_read_count = 0
    all_subreddits_bkup = all_subreddits.copy()  # This is a backup having all the subreddits found
    reddit_num_dict = {0:1, 1:2, 2:0}
    reddit_num = 0
    i = 0 
    
    while i < subreddit_count:
        print(f'***Reddit switch at {tot_reddit_read_count} to {reddit_num} processed {i} subredddits***')
        
        interim_reddit_read_count = 0 # Resetting the interim count once it hits reddit_switch_limit
        
        # A separate copy made to avoid truncation when all_subreddits gets truncated
        search_subreddits = all_subreddits.copy()
         
        for subreddit_name in search_subreddits:    
            subreddit_posts, subreddit_post_ids, reddit_read_count = fetch_posts_from_subreddit(search_keywords, subreddit_name, reddit_num) #, search_keywords, reddit_read_limit, reddit_time_filter)
            reddit_posts.update(subreddit_posts)
            reddit_post_ids.extend(subreddit_post_ids)
            all_subreddits.remove(subreddit_name) # Subreddits successfully processed are truncated
            i += 1 # Counter to track Subreddits processed
            interim_reddit_read_count += reddit_read_count # Incrementing interim_reddit_read_count
            tot_reddit_read_count += reddit_read_count # Incrementing tot_reddit_read_count
            
            # prnt_stmt = f'{i},{reddit_num},{subreddit_name},{interim_reddit_read_count},{tot_reddit_read_count}'
            # logger.info(prnt_stmt)
            # print(prnt_stmt)
            
            # Switching the reddit account once it hits reddit_switch_limit
            if interim_reddit_read_count > reddit_switch_limit:
                reddit_num = reddit_num_dict[reddit_num]
                break
      
    # Just checking if reddit_posts count is matching with tot_reddit_read_count     
    tot_len = 0
    print('**Checking reddit_posts count is matching with tot_reddit_read_count**')
    logger.info('reddit_resp_search')    
    for sub in all_subreddits_bkup:
        for kw in search_keywords:
            if sub in reddit_posts.keys() and kw in reddit_posts[sub].keys():
                tot_len += len(reddit_posts[sub][kw])
                for reddit_post_dict in reddit_posts[sub][kw]:
                    if 'comments' in reddit_post_dict.keys():
                        tot_len += len(reddit_post_dict['comments'])
    print(f'tot_len {tot_len} == tot_reddit_read_count {tot_reddit_read_count}')     
               
    return reddit_posts, reddit_post_ids

def condense_data(reddit_posts, reddit_post_ids):
    condensed_data = []
    unique_post_ids = set()
    unique_comment_ids = set()
    dup_post_cnt = 0
    unq_post_cnt = 0
    dup_comm_cnt = 0
    unq_comm_cnt = 0
    tot_post_cnt = 0
    tot_comm_cnt = 0
    cond_data_cnt = 0
    
    unq_reddit_post_ids = set()
    for p_id in reddit_post_ids:
        unq_reddit_post_ids.add(p_id)
    
    for subreddit_name, keywords_posts in reddit_posts.items():
        for keyword, posts in keywords_posts.items():
            keyword_comb = subreddit_name + '+' + keyword
            keyword_comb = keyword_comb.replace(" ", "-")
            for post in posts:
                tot_post_cnt += 1
                if post['comment_id'] in unique_post_ids:
                    dup_post_cnt += 1
                else:
                    unq_post_cnt += 1
                    post_calendar_date = reddit_resp_get_calendar_date(post['created_utc'])
                    post_comments = [{
                        'comment_id': post['comment_id'],
                        'parent_id': None,  # The main post has no parent
                        'post_id': post['comment_id'],
                        'text': post['title'],
                        'author': post['author'],
                        'score': post['score'],
                        'created_utc': post['created_utc'],
                        'created_date': post_calendar_date,
                        'age': post['age'],
                        'keycombo': keyword_comb,
                    }]                  
                    unique_post_ids.add(post['comment_id'])
                    for comment in post['comments']:
                        tot_comm_cnt += 1
                        if comment['comment_id'] in unique_comment_ids:
                            dup_comm_cnt += 1                        
                        else:
                            unq_comm_cnt += 1
                            comm_calendar_date = reddit_resp_get_calendar_date(comment['created_utc'])
                            comment_data = {
                                'comment_id': comment['comment_id'],
                                'parent_id': comment['parent_id'],
                                'post_id': post['comment_id'], # Comment belongs to this parent post
                                'text': comment['text'],
                                'author': comment['author'],
                                'score': comment['score'],
                                'created_utc': comment['created_utc'],
                                'created_date': comm_calendar_date,
                                'age': comment['age'],
                                'keycombo': keyword_comb,
                            }   
                            post_comments.append(comment_data)
                            unique_comment_ids.add(comment['comment_id'])
                    condensed_data.append(post_comments)

    for lst in condensed_data:
        cond_data_cnt += len(lst)    
    
    print(f'**condense_data stats**')
    print(f'post_cnt: dup_post_cnt {dup_post_cnt} + unq_post_cnt {unq_post_cnt} = tot_post_cnt {tot_post_cnt}')
    print(f'comm_cnt: dup_comm_cnt {dup_comm_cnt} + unq_comm_cnt {unq_comm_cnt} = tot_comm_cnt {tot_comm_cnt}')
    print(f'cond_cnt: cond_data_cnt {cond_data_cnt} = unq_post_cnt {unq_post_cnt} + unq_comm_cnt {unq_comm_cnt}')
    print(f'Cross_ck: len(unq_reddit_post_ids) {len(unq_reddit_post_ids)} = unq_post_cnt {unq_post_cnt}')
    
    return condensed_data, unique_post_ids, unique_comment_ids

def create_comment_dict(condensed_data):
    comment_list = []
    tot_data = 0
    old_comm = 0
    bigger_cnt = 0
    for idx1, item in enumerate(condensed_data):
        for idx2, data in enumerate(item):
            tot_data += 1
            c_id = data['comment_id']
            p_id = data['parent_id']
            post_id = data['post_id']
            text = data['text']
            created_date = data['created_date']
            age = data['age']
            config.comment_dict[c_id] = {'comment_id': c_id, 'parent_id': p_id, 'post_id': post_id, 'text': text, 'age': age, 'created': created_date}
            comment_list.append(c_id)
        if idx2 > 50:
            bigger_cnt +=1             
    print(f'Number of Posts that has more than 50 comments : {bigger_cnt}')
    
    comment_dict_list = list(config.comment_dict.keys())
    config.comment_dict_copy = copy.deepcopy(config.comment_dict)  
    # comment_dict_copy will hold decision, score, response etc. & be used for csv ouput preparation while
    # comment_dict will remain unchanged throughout
    print('len(config.comment_dict) = tot_data, len(comment_dict_list), len(config.comment_dict_copy), len(comment_list)')
    print(len(config.comment_dict), '=', tot_data, len(comment_dict_list), len(config.comment_dict_copy), len(comment_list))
    print(f'Id check # comment_dict_copy: {id(config.comment_dict_copy)} comment_dict: {id(config.comment_dict)}')

# Step 1: Flatten condensed_data and collect all posts/comments with their created_dt
def flatten_condensed_data(condensed_data):
    all_comments = []
    for post_data in condensed_data:
        for item in post_data:
            all_comments.append(item)  # Just the post/comment and created_dt
    return all_comments

# Step 2: Sort all comments by created_dt (descending latest first)
def sort_by_created_dt(all_comments):
    return sorted(all_comments, key=lambda x: datetime.strptime(x['created_date'], '%Y-%m-%d %H:%M:%S'), reverse=True)

def select_within_limit(sorted_comments, limit, window_hours=6):
    """
    Select comments within a given limit by trimming from the oldest time windows (based on `created_date`).
    
    Args:
        sorted_comments (list of dict): List of sorted comments, each comment is a dictionary with metadata.
        limit (int): Maximum number of comments to select.
        window_hours (int): Size of each time window in hours (default is 6).
    
    Returns:
        selected_comments (list of dict): The trimmed list of comments that fit within the limit.
        time_window (tuple): A tuple of (oldest_time, newest_time) for the selected comments.
    """
    
    if len(sorted_comments) <= limit:
        # If the total number of comments is within the limit, return them all
        return sorted_comments, (sorted_comments[-1]['created_date'], sorted_comments[0]['created_date'])
    
    # Group comments into time windows (based on created_date)
    time_windows = {}
    window_duration = timedelta(hours=window_hours)
    
    for comment in sorted_comments:
        created_dt = datetime.strptime(comment['created_date'], '%Y-%m-%d %H:%M:%S')
        
        # Round down the created_dt to the start of the nearest time window
        window_start = created_dt.replace(minute=0, second=0, microsecond=0) - timedelta(hours=created_dt.hour % window_hours)
        window_key = window_start.strftime('%Y-%m-%d %H:%M:%S')
        
        # Group comments by time window
        if window_key not in time_windows:
            time_windows[window_key] = []
        
        time_windows[window_key].append(comment)
    
    # Step 4: Collect comments from the latest windows until the limit is reached
    selected_comments = []
    
    # Traverse time windows in reverse order (latest windows first)
    for window_key in sorted(time_windows.keys(), reverse=True):
        current_window_comments = time_windows[window_key]
        
        if len(selected_comments) + len(current_window_comments) > limit:
            # If adding all the comments from this window exceeds the limit, trim it
            remaining_slots = limit - len(selected_comments)
            selected_comments.extend(current_window_comments[:remaining_slots])
            break
        
        selected_comments.extend(current_window_comments)
    
    # Step 5: Determine the time window of selected comments
    oldest_time = selected_comments[-1]['created_date']
    newest_time = selected_comments[0]['created_date']
    
    return selected_comments, newest_time, oldest_time

# Main function to process the condensed_data
def process_condensed_data(condensed_data):
    all_comments = flatten_condensed_data(condensed_data)  # Step 1
    sorted_comments = sort_by_created_dt(all_comments)     # Step 2
    reddit_comment_limit = config.reddit_comment_limit
    trimmed_comments, latest_dt, oldest_dt = select_within_limit(sorted_comments, reddit_comment_limit)  # Step 3
    config.latest_time_str = latest_dt
    config.oldest_time_str = oldest_dt
    print(f'Reddit Time window to consider: {config.latest_time_str} till {config.oldest_time_str}')
    print(f'reddit_comment_limit set in config : {reddit_comment_limit}')
    print(f'reddit_read_limit set in config : {config.reddit_read_limit[0]}')
    print(f'reddit_time_filter set in config : {config.reddit_time_filter}')
    print(f'reddit_switch_limit set in config : {config.reddit_switch_limit}') 
    print(f'Number of comments within time window: {len(trimmed_comments)}')
    print(f'Number of comments to discard : {len(all_comments) - len(trimmed_comments)}')
    
    return trimmed_comments, latest_dt, oldest_dt