import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Union
import autogen

from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from autogen.agentchat.agent import Agent
from token_count import num_tokens_from_string

import websockets

CHUNK_SIZE = 15_000 # use a chunk size of 15_000 tokens so that it comfortably fits in the OpenAI API limit of 16_000 tokens

def get_html_chunks(html: str):
    text_splitter = CharacterTextSplitter(
        separator=">",
        chunk_size=CHUNK_SIZE,
        chunk_overlap=10,
        length_function=num_tokens_from_string # use OpenAI's tokenizer to count tokens
    )
    chunks = text_splitter.split_text(html)
    return chunks


# TODO : avoid recomputing embeddings for html chunks that have not changes
def build_vectorstore(html_chunks: [str]):
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(texts=html_chunks, embedding=embeddings)
    return vectorstore

load_dotenv()


PROMPT_QA = """You're a retrieve augmented chatbot. You answer user's questions based on the HTML
context provided by the user. You must answer as concisely as possible.

User's question is: {input_question}

Context is: {input_context}
"""

class RetrieveHTMLProxyAgent(autogen.ConversableAgent):
    '''
    An agent that fetches the relevant HTML content from a user query based 
    on the HTML content of the current page on the browser.
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
        self.html = ""
        self.vectorstore = None

    def connect_websocket(self):
        self.websocket = asyncio.get_event_loop().run_until_complete(websockets.connect(self.browser_console_uri))

    async def fetch_html(self, **kwargs) -> str:
        '''
        Fetch the HTML of the current page from the browser console
        '''
        if not self.websocket:
            self.websocket = websockets.connect(self.browser_console_uri)
        print(f"Fetching HTML of current page...")
        message = json.dumps({
            'action': "fetchHTML",
        })
        
        await self.websocket.send(message)
        response_data = json.loads(await self.websocket.recv())
        if not response_data.get('success'):
            raise Exception("Failed to fetch HTML")
        return response_data["result"]
    
    def _retrieve_context(self,  vectorstore,  query: str) -> str:
        '''
        Get the  most relevant chunk using the user's question as a query
        '''
        relevant_chunks = vectorstore.similarity_search(query, k = 1)
        print("Relevant chunks retrieved")
        relevant_chunks = [chunk.page_content for chunk in relevant_chunks]
        return "\n\n".join(relevant_chunks)

    
    def _build_message_with_context(self, question: str) -> str:
        '''
        Build a message with the context retrieved from the HTML using RAG
        '''
        html = ""
        try:
            html =  asyncio.get_event_loop().run_until_complete(self.fetch_html())
        except Exception as e:
           raise e
        if num_tokens_from_string(html) < CHUNK_SIZE :
            context = html
        else :
            if html != self.html: # html has changed
                self.html = html # update html
                html_chunks = get_html_chunks(html)
                print("HTML chunked")
                print("n_chunks = ", len(html_chunks))
                vectorstore = build_vectorstore(html_chunks)
                self.vectorstore = vectorstore
                print("Vectorstore built")
            context = self._retrieve_context(self.vectorstore, question)
        message = PROMPT_QA.format(input_question=question, input_context=context)
        return message

    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ) -> bool:
        """Send a message to another agent.

        Args:
            message (dict or str): message to be sent.
                The message could contain the following fields (either content or function_call must be provided):
                - content (str): the content of the message.
                - function_call (str): the name of the function to be called.
                - name (str): the name of the function to be called.
                - role (str): the role of the message, any role that is not "function"
                    will be modified to "assistant".
                - context (dict): the context of the message, which will be passed to
                    [Completion.create](../oai/Completion#create).
                    For example, one agent can send a message A as:
        ```python
        {
            "content": lambda context: context["use_tool_msg"],
            "context": {
                "use_tool_msg": "Use tool X if they are relevant."
            }
        }
        ```
                    Next time, one agent can send a message B with a different "use_tool_msg".
                    Then the content of message A will be refreshed to the new "use_tool_msg".
                    So effectively, this provides a way for an agent to send a "link" and modify
                    the content of the "link" later.
            recipient (Agent): the recipient of the message.
            request_reply (bool or None): whether to request a reply from the recipient.
            silent (bool or None): (Experimental) whether to print the message sent.

        Raises:
            ValueError: if the message can't be converted into a valid ChatCompletion message.
        """
        #  add relevant HTML context to the message first
        message = self._build_message_with_context(message)
        valid = self._append_oai_message(message, "assistant", recipient)
        if valid:
            recipient.receive(message, self, request_reply, silent)
        else:
            raise ValueError(
                "Message can't be converted into a valid ChatCompletion message. Either content or function_call must be provided."
            )