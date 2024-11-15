import modal
from modal import App, Image, web_endpoint, Secret
from pydantic import BaseModel

modal_image = Image.debian_slim().pip_install("crewai==0.70.0", 
                                            "crewai-tools==0.12.0",)

with modal_image.imports(): 
    from lf_keywordgen.main_src.main import handle_main_response

#**********************************#
# Main Modal App that starts everything
#**********************************#
app = App('neumarketai-kwgen', image=modal_image) 
 
@app.function(timeout=20, secrets=[modal.Secret.from_name("my-openai-secret")])
@web_endpoint(method="POST")
def kwgen(item: dict):
    response = handle_main_response(item) 
    return response    