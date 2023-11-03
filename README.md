# AutoBrowse
AutoBrowse is an autonomous AI agent that can browse the web.
You simply give AutoBrowse a task and it will complete it by interacting with the web browser as if it were a human.

Some examples of tasks you can give it:

- Go to booking.com and find a hotel for 2 people in Madrid for 2 nights starting 2 November for under 200 EUR per night.

- Sign up to ryanair.com with email: <example@email.com> and password C0mplexPassword!.

- Go to Craigslist and search for Nintendo DS. Click on the first result.

## How to run

1. Create a Python 3.9 environment

    ```bash
    conda create --name py39 python=3.9
    ```

2. Activate the environment

    ```bash
    conda activate py39
    ```

3. Install dependencies

    ```bash
    pip install -r requirements.txt
    ```

4. Start the browser environment

    Check the README under `browser-console/` for instructions on how to run it.


5. Create a file `OAI_CONFIG_LIST` with the following content and put in your OpenAI API key:

    ```json
    [
        {
            "model": "gpt-4",
            "api_key": "<your-api-key>"
        },
        {
            "model": "gpt-3.5-turbo",
            "api_key": "<your-api-key>"
        },
        {
            "model": "gpt-3.5-turbo-16k",
            "api_key": "<your-api-key>"
        }
    ]
    ```




5. Run AutoBrowse 

    ```bash
    python autobrowse.py
    ```

    You will then be prompted give a task to AutoBrowse.


You can make modifications agent configurations by modifying the `agent_config.py` file. You can edit the system prompts, change the OpenAI models used etc.


## How it works
AutoBrowse uses [autogen](https://github.com/microsoft/autogen) agents and a browser console to plan and execute the task.

The design consists of 3 agents:

1. An HTML assistant that answers questions about the HTML of the current page open in the browser.

2. A code generator agent that generates puppeteer.js code to interact with the browser (i.e. navigate to a new page, click on a button, fill in form elements)

3. A planner agent that coordinates the use of the two agents above to fulfill the high-level task description provided by the user.

The agents interact with the browser through a websocket connection to a sandboxed browser environment that has an endpoint to accept puppeteer.js code to execute, as well as and endpoint to return the rendered HTML of the current open page.

### HTML Assistant
Since HTML documents can be quite long and can exceed the token limit of OpenAI the following approach is taken to answer queries about the HTML:

- The HTML returned from the browser environment is stripped down and simplified to reduce its size. This done by keeping only the most important attributes like id, name, type, and class . Moreover, `script`, `style`, `noscript`, `img`, `svg`, `link`, `meta`  tags are removed altogether.

- The processed HTML is chunked into 15,000 token (as counted by OpenAI) so that they can easily fit in the 16K context window of `gpt-3.5-turbo-16k`. 

- Using RAG with OpenAI embeddings, the most relevant chunk is provided as context to the question, and `gpt-3.5-turbo` can then answer the question about the HTML.

### Code Generator
The code generator uses `gpt-4` to generate puppeteer.js code to interact with the browser. A user proxy agent attached to the code generator sends this code to the browser environment to be executed and reports back the result, so that the code generator can amend the code if there are any errors. Because the code generation needs to be as accurate as possible the more expensive `gpt-4` model is used in favor of the cheaper `gpt-3.5-turbo`.

### Planner

The planner receives the task description from the user and tries to complete it by invoking the HTML Assistant and Code Generator as necessary. The planner, in addition to its own thinking, has the ability to invoke two functions:


1. `ask_html_assistant()` to ask the HTML assistant a question about the current HTML (e.g. extract the HTML for the sign-up form), and 

2. `ask_code_generator()` to ask the code generator to produce puppeteer.js code to send to the browser. The planner may also add HTML retrieved from the HTML assistant to provide more context to the code generator.





