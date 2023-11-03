const { Server } = require('ws');
const { VM } = require('vm2');
const { JSDOM } = require('jsdom');
const puppeteer = require('puppeteer');
const beautifyHTML = require('js-beautify').html;

async function initializePuppeteer() {
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();
  return { browser, page };
}

// remove all attributes from the elements apart from 
// name, type, id, class, href, src, title, etc.
const allowedAttributes = ['name', 'type', 'id', 'class', 'href', 'src', 'title' ,'placeholder', 'value', 'checked', 'selected', 'disabled', 'readonly', 'multiple', 'required', 'min', 'max', 'step', 'pattern', 'accept', 'accept-charset', 'autocomplete', 'autofocus', 'form', 'formaction', 'formenctype', 'formmethod', 'formnovalidate', 'formtarget', 'height', 'width', 'alt', 'download', 'media', 'target',  'tabindex', 'accesskey', 'contenteditable', 'draggable', 'dropzone', 'hidden'];

const unwantedTags = 'script, style, noscript, img, svg, link, meta';

// Recursive function to clean attributes of a node and its children
function cleanAttributes(node) {
  // If the node has attributes, inspect them
  if (node.attributes) {
    // Collect attributes in an array to avoid modification issues
    const attributes = Array.from(node.attributes);
    for (const attribute of attributes) {
      // If the attribute is not in the allowed list, remove it
      if (!allowedAttributes.includes(attribute.name)) {
        node.removeAttribute(attribute.name);
      }
    }
  }

  // Recursive case: If the node has child nodes, inspect them
  if (node.childNodes) {
    node.childNodes.forEach(cleanAttributes);
  }
}


initializePuppeteer().then(({ browser, page }) => {
  const vm = new VM({
    sandbox: { browser, page },
    require: { external: true },
  });


  const wss = new Server({ port: 3000 });
  console.log('WebSocket Server is running on port 3000');

  wss.on('connection', (ws) => {
    console.log('A user connected');

    async function executeCode(code) {
      try {
        const result = await vm.run(`(async () => { ${code} })()`);
        ws.send(JSON.stringify({ success: true, result }));
      } catch (err) {
        console.error(`Error executing command: ${err}`);
        ws.send(JSON.stringify({ success: false, error: err.message }));
      }
    }

    async function fetchHTML() {
      if (!page) {
        ws.send(JSON.stringify({ success: false, error: 'Page not initialized' }));
        return;
      }
      try {
        // get the raw HTML content of the page
        const rawHTML = await page.content();        
        // create a new JSDOM object
        const dom = new JSDOM(rawHTML);
        // parse the raw HTML into a new document object
        const doc = dom.window.document;
        // remove unwanted elements from the document
        doc.querySelectorAll(unwantedTags).forEach(element => element.remove());
        // get the clean HTML
        // remove all attributes from the elements apart from 
        // name, type, id, class, href, src, title
        cleanAttributes(doc.documentElement);
        const cleanHTML = doc.documentElement.outerHTML;
        const formattedHTML = beautifyHTML(cleanHTML, { indent_size: 2 });

        console.log("Sending formatted HTML");
        ws.send(JSON.stringify({ success: true, result: formattedHTML }));
      } catch (err) {
        console.error(`Error fetching HTML: ${err}`);
        ws.send(JSON.stringify({ success: false, error: err.message }));
      }
    }

    ws.on('message', async (message) => {
      console.log(`Received: ${message}`);
      message = JSON.parse(message);
      switch (message.action) {
        case 'executeCode':
          await executeCode(message.code);
          break;
        case 'fetchHTML':
          await fetchHTML();
          break;
        default:
          console.error(`Unknown action: ${message.action}`);
      }
    });

    ws.on('close', () => {
      console.log('User disconnected');
    });
  });
});