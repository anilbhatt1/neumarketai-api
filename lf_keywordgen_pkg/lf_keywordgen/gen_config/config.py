import logging
logging.basicConfig(level=logging.WARNING)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

import os
import yaml
import json
from crewai import LLM

print('CONFIG LOADED !!!!')

current_dir = os.path.dirname(os.path.abspath(__file__))

openai_gpt4o_mini = LLM(model="gpt-4o-mini",
                                temperature=0.7,
                                api_key=os.environ["OPENAI_API_KEY"],
                                base_url="https://api.openai.com/v1")

# This in_data will get populated with in_data passed from calling app
in_data = {}


