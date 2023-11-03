# browser-controller
This package runs a web browser in a sandbox. The console is used to receive `puppeteer.js` code to execute in order to control the browser, and to fetch the rendered HTML of the current page. Communication happens through a websocket connection.

The message format of a request to execute code is:

```json
{
    "action": "executeCode",
    "code" : "<code-to-execute>",
}
```

The message format of a request to fetch the HTML of the current page is:


```json
{
    "action": "fetchHTML",
}
```

## How to run
You need to be using node.js version 18. You can check the version you currently have installed using:

```bash
node -v
```

You can use a node package manager like `nvm` to set the appropriate version:
```bash
nvm install 18 && nvm use
```

Install dependencies with:

```bash
npm install
```

Run the browser controller with:
```bash
node console.js
```


