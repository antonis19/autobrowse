import autogen

# load OPENAI_API_KEY from .env file
from dotenv import load_dotenv

from browser_proxy_agent import BrowserProxyAgent
from retrieve_html_proxy_agent import RetrieveHTMLProxyAgent
load_dotenv()

# print the OPENAI_API_KEY
import os
print(os.environ["OPENAI_API_KEY"])

config_list = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
    file_location=".",
    filter_dict={
        "model": {
            "gpt-3.5-turbo-16k",
        }
    }
)
print(config_list)


html_assistant = autogen.AssistantAgent(
    name="html_assistant",
    llm_config={"config_list": config_list},
    # the default system message of the AssistantAgent is overwritten here
    system_message='''You are a helpful AI Assistant. You help users with their HTML questions. '''
)


# create a UserProxyAgent instance to interact with html_assistant
html_proxy = RetrieveHTMLProxyAgent(
    name="html_user_proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=0,
)


# continuous prompt for the user to ask questions
while True:
    # get the user's question
    user_question = input("What is your question?\n") 
    # initiate the chat with the code_generator
    html_proxy.initiate_chat(html_assistant, message=user_question)



