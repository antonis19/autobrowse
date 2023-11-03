import asyncio
import json
from typing import Callable, Dict, List, Optional, Tuple, Union
import autogen

# load OPENAI_API_KEY from .env file
from dotenv import load_dotenv
from termcolor import colored
import websockets

from autogen.code_utils import infer_lang

class BrowserProxyAgent(autogen.ConversableAgent):
    '''
    A class that extends ConversableAgent to execute puppeteer.js code in the browser.
    Instead of directly executing Javascript code, it sends the code to the browser console via a websocket.
    '''
    def __init__(
        self,
        name: str,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "ALWAYS",
        function_map: Optional[Dict[str, Callable]] = None,
        code_execution_config: Optional[Union[Dict, bool]] = None,
        default_auto_reply: Optional[Union[str, Dict, None]] = "",
        llm_config: Optional[Union[Dict, bool]] = False,
        system_message: Optional[str] = "",
        browser_console_uri: Optional[str] = "ws://localhost:3000",
    ):
        super().__init__(
            name=name,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            function_map=function_map,
            code_execution_config=code_execution_config,
            default_auto_reply=default_auto_reply,
            llm_config=llm_config,
            system_message=system_message,
        )
        self.browser_console_uri = browser_console_uri
        self.connect_websocket()

    def connect_websocket(self):
        try :
            self.websocket = asyncio.get_event_loop().run_until_complete(websockets.connect(self.browser_console_uri))
        except Exception as e:
            raise Exception("Failed to connect to browser console websocket. Please make sure the browser console is running.")
        
    async def run_puppeteer_code(self, code: str, **kwargs) -> Tuple[int, str, str]:
        if not self.websocket:
            self.connect_websocket()
        message = json.dumps({
            'action': "executeCode",
            'code': code,
        })
        await self.websocket.send(message)
        response_data = json.loads(await self.websocket.recv())

        if response_data.get('success'):
            return 0, str(response_data), None
        else:
            return 1, str(response_data), None


    def execute_code_blocks(self, code_blocks: List[str]) -> Tuple[int, str, str]:
        """Overriden  function Execute the code blocks and return the result.
        IF the language is Javascript, the code will be sent to the browser console to be executed.
        """
        logs_all = ""
        for i, code_block in enumerate(code_blocks):
            lang, code = code_block
            if not lang:
                lang = infer_lang(code)
            print(
                colored(
                    f"\n>>>>>>>> EXECUTING CODE BLOCK {i} (inferred language is {lang})...",
                    "red",
                ),
                flush=True,
            )
            if lang in ["javascript", "Javascript", "node", "Node", "js", "JS"]:
               exitcode, logs, image =  asyncio.get_event_loop().run_until_complete(self.run_puppeteer_code(code, **self._code_execution_config))
            elif lang in ["bash", "shell", "sh"]:
                exitcode, logs, image = self.run_code(code, lang=lang, **self._code_execution_config)
            elif lang in ["python", "Python"]:
                if code.startswith("# filename: "):
                    filename = code[11 : code.find("\n")].strip()
                else:
                    filename = None
                exitcode, logs, image = self.run_code(
                    code,
                    lang="python",
                    filename=filename,
                    **self._code_execution_config,
                )
            else:
                # In case the language is not supported, we return an error message.
                exitcode, logs, image = (
                    1,
                    f"unknown language {lang}",
                    None,
                )
                # raise NotImplementedError
            if image is not None:
                self._code_execution_config["use_docker"] = image
            logs_all += "\n" + logs
            if exitcode != 0:
                return exitcode, logs_all
        return exitcode, logs_all
    
