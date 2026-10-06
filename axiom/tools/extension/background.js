/**
 * AXIOM Browser Bridge — Background Worker / Service Script.
 * Maintains a persistent WebSocket link to the local AXIOM daemon on ws://127.0.0.1:41144.
 * Enables zero-friction, deterministic browser automation for Zen Browser & Chrome.
 */

const WS_URL = "ws://127.0.0.1:41144";
let socket = null;
let reconnectTimer = null;
const INITIAL_RECONNECT_DELAY = 2000;
const MAX_RECONNECT_DELAY = 5000;
const RECONNECT_MULTIPLIER = 1.3;
let reconnectDelay = INITIAL_RECONNECT_DELAY;

function log(msg, ...args) {
  console.log(`[AXIOM Extension] ${msg}`, ...args);
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  log(`Connecting to daemon at ${WS_URL}...`);
  try {
    socket = new WebSocket(WS_URL);
  } catch (err) {
    log(`WebSocket creation failed: ${err.message}`);
    scheduleReconnect();
    return;
  }

  socket.onopen = () => {
    log("Connected to AXIOM daemon.");
    reconnectDelay = INITIAL_RECONNECT_DELAY;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  socket.onmessage = async (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (!msg || !msg.id || !msg.action) {
        log("Invalid command payload:", event.data);
        return;
      }
      await handleCommand(msg);
    } catch (err) {
      log("Error processing message:", err);
    }
  };

  socket.onclose = () => {
    log("Disconnected from daemon.");
    socket = null;
    scheduleReconnect();
  };

  socket.onerror = (err) => {
    log("WebSocket error:", err);
    if (socket) {
      socket.close();
    }
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  log(`Scheduling reconnect in ${reconnectDelay}ms...`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    reconnectDelay = Math.min(Math.round(reconnectDelay * RECONNECT_MULTIPLIER), MAX_RECONNECT_DELAY);
    connect();
  }, reconnectDelay);
}

function sendReply(data) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data));
  } else {
    log("Cannot send reply: socket not open", data);
  }
}

async function getTargetTab(msg) {
  if (msg.tab_id) {
    try {
      const tab = await chrome.tabs.get(Number(msg.tab_id));
      if (tab) return tab;
    } catch (_) {}
  }

  // Fallback to active tab in current or last focused window
  const activeTabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (activeTabs && activeTabs.length > 0) {
    return activeTabs[0];
  }

  const anyActive = await chrome.tabs.query({ active: true });
  if (anyActive && anyActive.length > 0) {
    return anyActive[0];
  }

  const allTabs = await chrome.tabs.query({});
  return allTabs.length > 0 ? allTabs[0] : null;
}

async function handleCommand(msg) {
  const { id, action } = msg;

  try {
    switch (action) {
      case "list_tabs":
      case "tabs": {
        const tabs = await chrome.tabs.query({});
        const tabList = tabs.map((t) => ({
          id: t.id,
          title: t.title || "",
          url: t.url || "",
          active: Boolean(t.active),
          windowId: t.windowId,
        }));
        sendReply({
          id,
          success: true,
          action: "list_tabs",
          tabs: tabList,
          count: tabList.length,
        });
        break;
      }

      case "switch_tab": {
        const query = (msg.query || msg.filter || msg.target || msg.title || msg.url || msg.text || "").toLowerCase().trim();
        const tabId = msg.tab_id ? Number(msg.tab_id) : null;
        const allTabs = await chrome.tabs.query({});

        let matched = null;
        if (tabId) {
          matched = allTabs.find((t) => t.id === tabId);
        } else if (query) {
          matched = allTabs.find(
            (t) =>
              (t.title && t.title.toLowerCase().includes(query)) ||
              (t.url && t.url.toLowerCase().includes(query))
          );
        }

        if (!matched) {
          let openUrl = null;
          if (query.startsWith("http://") || query.startsWith("https://")) {
            openUrl = query;
          } else if (query.includes(".") && !query.includes(" ")) {
            openUrl = `https://${query}`;
          } else if (query === "gemini") {
            openUrl = "https://gemini.google.com";
          } else if (query === "monkeytype") {
            openUrl = "https://monkeytype.com";
          } else if (query === "youtube") {
            openUrl = "https://youtube.com";
          } else if (query === "github") {
            openUrl = "https://github.com";
          }

          if (openUrl) {
            try {
              const newTab = await chrome.tabs.create({ url: openUrl, active: true });
              sendReply({
                id,
                success: true,
                action: "switch_tab",
                tab: {
                  id: newTab.id,
                  title: newTab.title || query,
                  url: newTab.url || openUrl,
                },
              });
              return;
            } catch (_) {}
          }

          sendReply({
            id,
            success: false,
            action: "switch_tab",
            error: `No tab found matching query: '${query || tabId}'`,
          });
          return;
        }

        await chrome.tabs.update(matched.id, { active: true });
        if (matched.windowId && chrome.windows) {
          try {
            await chrome.windows.update(matched.windowId, { focused: true });
          } catch (_) {}
        }

        sendReply({
          id,
          success: true,
          action: "switch_tab",
          tab: {
            id: matched.id,
            title: matched.title || "",
            url: matched.url || "",
          },
        });
        break;
      }

      case "click": {
        const selector = msg.selector;
        if (!selector) {
          sendReply({ id, success: false, action: "click", error: "Missing selector parameter" });
          return;
        }

        const tab = await getTargetTab(msg);
        if (!tab || !tab.id) {
          sendReply({ id, success: false, action: "click", error: "No target tab available" });
          return;
        }

        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (sel) => {
            const el = document.querySelector(sel);
            if (!el) {
              return { success: false, error: `Element not found for selector: '${sel}'` };
            }
            try {
              el.scrollIntoView({ behavior: "instant", block: "center" });
            } catch (_) {}
            el.click();
            return {
              success: true,
              result: `Clicked <${el.tagName.toLowerCase()}> element (${sel})`,
              tagName: el.tagName,
              id: el.id,
            };
          },
          args: [selector],
        });

        const execResult = results && results[0] ? results[0].result : { success: false, error: "Script execution produced no result" };
        sendReply({ id, action: "click", selector, ...execResult });
        break;
      }

      case "type": {
        const selector = msg.selector;
        const text = msg.text || "";
        if (!selector) {
          sendReply({ id, success: false, action: "type", error: "Missing selector parameter" });
          return;
        }

        const tab = await getTargetTab(msg);
        if (!tab || !tab.id) {
          sendReply({ id, success: false, action: "type", error: "No target tab available" });
          return;
        }

        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (sel, val) => {
            const el = document.querySelector(sel);
            if (!el) {
              return { success: false, error: `Element not found for selector: '${sel}'` };
            }
            try {
              el.focus();
            } catch (_) {}
            if ("value" in el) {
              el.value = val;
              el.dispatchEvent(new Event("input", { bubbles: true }));
              el.dispatchEvent(new Event("change", { bubbles: true }));
            } else {
              el.textContent = val;
            }
            return {
              success: true,
              result: `Typed '${val}' into <${el.tagName.toLowerCase()}>`,
              value: val,
            };
          },
          args: [selector, text],
        });

        const execResult = results && results[0] ? results[0].result : { success: false, error: "Script execution produced no result" };
        sendReply({ id, action: "type", selector, ...execResult });
        break;
      }

      case "get_dom":
      case "get_content": {
        const tab = await getTargetTab(msg);
        if (!tab || !tab.id) {
          sendReply({ id, success: false, action: "get_dom", error: "No target tab available" });
          return;
        }

        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            return {
              title: document.title,
              url: window.location.href,
              content: document.body ? document.body.innerText.slice(0, 50000) : "",
            };
          },
        });

        const execResult = results && results[0] ? results[0].result : { success: false, error: "Script execution produced no result" };
        sendReply({ id, success: true, action: "get_dom", ...execResult });
        break;
      }

      default:
        sendReply({
          id,
          success: false,
          error: `Unsupported action: '${action}'`,
          action,
        });
        break;
    }
  } catch (err) {
    sendReply({
      id,
      success: false,
      error: `Internal extension error: ${err.message || String(err)}`,
      action,
    });
  }
}

// Start connection immediately on extension load
connect();

if (typeof chrome !== "undefined" && chrome.runtime) {
  if (chrome.runtime.onStartup) {
    chrome.runtime.onStartup.addListener(() => connect());
  }
  if (chrome.runtime.onInstalled) {
    chrome.runtime.onInstalled.addListener(() => connect());
  }
}
