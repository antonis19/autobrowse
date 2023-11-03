
from typing import Any, Dict, List
import autogen

from autogen.agentchat.assistant_agent import AssistantAgent
from autogen.code_utils import extract_code

from browser_proxy_agent import BrowserProxyAgent
from retrieve_html_proxy_agent import RetrieveHTMLProxyAgent
import agent_config



def get_code_blocks(message: str) -> List[str]:
    return [code_block for _, code_block in extract_code(message)]

def is_termination_message_for_code_generator(message):
    """
    function to check if a message is a termination message for the code_generator agent.
    """
    content = message.get("content", "")
    if not content:
        return False
    return content.rstrip().endswith("TERMINATE")


def is_termination_message_for_planner(message):
    """
    function to check if a message is a termination message for the planner agent.
    """
    content = message.get("content", "")
    if not content:
        return False
    return "FINISHED" in content.rstrip()



class AutoBrowse:
    
    def __init__(self, config: Dict[str, Any], browser_console_uri: str = "ws://localhost:3000"):
        # global variable tracking code blocks executed thus far
        self.code_executed_so_far = []
        # browser console uri to send puppeteer.js code to and fetch HTML from
        self.browser_console_uri = browser_console_uri
        # initialize agents
        self.init_html_assistant(config["html_assistant"].get("model"), config["html_assistant"].get("system_message"))
        self.init_code_generator(config["code_generator"].get("model"), config["code_generator"].get("system_message"), config["code_generator_user_proxy"].get("max_consecutive_auto_reply", 0), browser_console_uri= self.browser_console_uri)
        self.init_planner(config["planner"].get("model"), config["planner"].get("system_message"), config["planner_user_proxy"].get("max_consecutive_auto_reply", 0))

    def init_planner(self, model_name = "gpt-4", system_message = "", max_consecutive_auto_reply = 0):
        '''
        Initialize the planner agent, which generates a plan to fulfill a web browsing task.
        '''
        ################## PLANNER ##############
        config_list_planner = autogen.config_list_from_json(
            "OAI_CONFIG_LIST",
            file_location=".",
            filter_dict={
                "model": {
                    model_name,
                }
            },
        )

        llm_config_planner = {
            "config_list": config_list_planner,
            "functions": [
                {
                    "name": "ask_html_assistant",
                    "description": "ask a question to the html_assistant",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "the question to ask the html_assistant about the current page",
                            },
                        },
                        "required": ["message"],
                    },
                },
                {
                    "name": "ask_code_generator",
                    "description": "ask a question to the code_generator",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "the question to ask the code_generator",
                            },
                            "context_html": {
                                "type": "string",
                                "description": "the HTML from the current page",
                            },
                        },
                        "required": ["message"],
                    },
                },
            ],
        }


        # an AssistantAgent named planner that generates a plan to fulfill a web browsing task,
        # the agent can propose the usage of two functions : 1. ask_html_assistant (to ask questions about the current
        # page in the browser - the result will be HTML code) 2. ask_code_generator (to generate and execute puppeteer.js code in the browser)
        self.planner = autogen.AssistantAgent(
            name="planner",
            llm_config=llm_config_planner,
            # the default system message of the AssistantAgent is overwritten here
            system_message=system_message,
        )

        self.planner_user_proxy = autogen.UserProxyAgent(
            name="planner_user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply= max_consecutive_auto_reply,
            is_termination_msg=is_termination_message_for_planner,
            function_map={
                "ask_html_assistant": self.ask_html_assistant,
                "ask_code_generator": self.ask_code_generator,
            },
        )

    def init_html_assistant(self, model_name = "gpt-3.5-turbo-16k", system_message = ""):
        llm_config_list = autogen.config_list_from_json(
            "OAI_CONFIG_LIST",
            file_location=".",
            filter_dict={
                "model": {
                    model_name,
                }
            },
        )
        self.html_assistant = autogen.AssistantAgent(
            name="html_assistant",
            llm_config={"config_list": llm_config_list},
            # the default system message of the AssistantAgent is overwritten here
            system_message=system_message,
        )

        # create a UserProxyAgent instance to interact with html_assistant
        self.html_proxy = RetrieveHTMLProxyAgent(
            name="html_user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
        )

    def init_code_generator(self, model_name = "gpt-4", system_message = "", max_consecutive_auto_reply = 3, browser_console_uri = "ws://localhost:3000"):
        llm_config_list = autogen.config_list_from_json(
            "OAI_CONFIG_LIST",
            file_location=".",
            filter_dict={
                "model": {
                    model_name,
                }
            },
        )

        # create an AssistantAgent named code_generator that generates puppeteer.js code to interact with the browser.
        self.code_generator = autogen.AssistantAgent(
            name="code_generator",
            llm_config={"config_list": llm_config_list},
            # the default system message of the AssistantAgent is overwritten here
            system_message=system_message,
        )

        # create a UserProxyAgent instance to interact with the code_generator
        self.code_generator_user_proxy = BrowserProxyAgent(
            name="code_generator_user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply= max_consecutive_auto_reply,
            is_termination_msg=is_termination_message_for_code_generator,
            code_execution_config={"work_dir": "code_execution"},
            browser_console_uri= browser_console_uri,
        )

    def ask_planner(self, question: str) -> str:
        '''
        Entrypoint function to Autobrowse to fulfill  a web browsing task.
        '''
        self.planner_user_proxy.initiate_chat(
            self.planner,
            message=question
        )
        final_code_executed = "\n".join(self.code_executed_so_far)
        self.code_executed_so_far = []
        return final_code_executed



    def ask_html_assistant(self, message: str) -> str:
        '''
        Function to ask the html assistant a question about the HTML content of the current page
        '''
        self.html_proxy.initiate_chat(self.html_assistant, message=message)
        last_message = self.html_proxy.last_message()["content"]
        return last_message

    def augment_message_to_code_gen(self, message: str, context_html: str):
        '''
        Augment the question to code_generator by appending the relevant HTML for it to complete the task, and the code executed so far.
        '''
        code_executed_so_far_str = "\n".join(self.code_executed_so_far)
        if code_executed_so_far_str:
            if  context_html:
                return f'''{message}\n\nThis is the relevant HTML from the current page:\n\n{context_html}\n\nThis is the code already executed so far:\n{code_executed_so_far_str}'''
            else:
                return f'''{message}\n\nThis is the code already executed so far:\n\n{code_executed_so_far_str}'''
        else :
            return message

    def ask_code_generator(self, message: str, context_html = "") -> str:
        """
        function to ask code_generator a question.

        Args:
            message (str): the question to ask code_generator
            context_html (str): the relevant HTML for code_generator to complete the task
        """
        self.code_generator_user_proxy.initiate_chat(self.code_generator, message=self.augment_message_to_code_gen(message, context_html))
        #  -2 is the execution result,
        #  -3 is the last message with a code block
        last_code_block_message =  self.code_generator_user_proxy.chat_messages[self.code_generator][-3]["content"]
        # get code blocks from last_code_block_message
        code_blocks = get_code_blocks(last_code_block_message)
        code_blocks_str = "\n".join(code_blocks)

        if is_termination_message_for_code_generator(self.code_generator_user_proxy.last_message()):
            # add code blocks to code_executed_so_far
            self.code_executed_so_far.extend(code_blocks)
            return f''' Code execution successful. The following code was executed:\n{code_blocks_str}'''
        else:
            last_error_message = self.code_generator_user_proxy.chat_messages[self.code_generator][-2]["content"]
            return f"Code execution failed. Code execution:\n{code_blocks_str}\nError message:\n{last_error_message}"


if __name__ == "__main__":
    autobrowse = AutoBrowse(config = agent_config.config)
    while True:
        question = input("Enter a question to ask Autobrowse: \n")
        final_code_executed = autobrowse.ask_planner(question)
        print("Final code executed: ")
        print(final_code_executed)
        print("=====================================")
        print("=====================================")
        print("=====================================")
        print("=====================================")
        print("=====================================")
