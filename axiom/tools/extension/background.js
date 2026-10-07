/**
 * AXIOM Browser Bridge — Background Worker / Service Script.
 * Maintains a persistent WebSocket link to the local AXIOM daemon on ws://127.0.0.1:41144.
 * Enables zero-friction, deterministic browser automation for Zen Browser & Chrome.
 */

const WS_URL = "ws://127.0.0.1:41144";
let socket = null;
let reconnectTimer = null;
let pingTimer = null;
const INITIAL_RECONNECT_DELAY = 2000;
const MAX_RECONNECT_DELAY = 5000;
const RECONNECT_MULTIPLIER = 1.3;
const PING_INTERVAL_MS = 10000; // 10 seconds
let reconnectDelay = INITIAL_RECONNECT_DELAY;

function log(msg, ...args) {
  console.log(`[AXIOM Extension] ${msg}`, ...args);
}

function startKeepAlivePing() {
  stopKeepAlivePing();
  pingTimer = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      log("Sending keep-alive ping to daemon...");
      try {
        socket.send(JSON.stringify({ type: "ping", action: "ping" }));
      } catch (err) {
        log("Failed to send ping:", err);
      }
    }
  }, PING_INTERVAL_MS);
}

function stopKeepAlivePing() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
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
    startKeepAlivePing();
  };

  socket.onmessage = async (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (!msg) return;

      // Handle pong frames from daemon
      if (msg.type === "pong" || msg.action === "pong") {
        log("Received keep-alive pong from daemon.");
        return;
      }

      if (!msg.id || !msg.action) {
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
    stopKeepAlivePing();
    socket = null;
    scheduleReconnect();
  };

  socket.onerror = (err) => {
    log("WebSocket error:", err);
    stopKeepAlivePing();
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
          const openTabs = allTabs.map((t) => ({
            id: t.id,
            title: t.title || "",
            url: t.url || "",
            active: Boolean(t.active),
          }));
          sendReply({
            id,
            success: false,
            action: "switch_tab",
            error: `No open tab matching query: '${query || tabId}'`,
            open_tabs: openTabs,
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

      case "open_tab": {
        let url = (msg.url || msg.query || "about:blank").trim();
        if (url && !url.includes("://") && !url.startsWith("about:") && !url.startsWith("chrome:")) {
          url = `https://${url}`;
        }
        try {
          const tab = await chrome.tabs.create({ url, active: true });
          sendReply({
            id,
            success: true,
            action: "open_tab",
            tab_id: tab.id,
            title: tab.title || "",
            url: tab.url || url,
          });
        } catch (err) {
          sendReply({
            id,
            success: false,
            action: "open_tab",
            error: `Failed to open tab: ${err.message || String(err)}`,
          });
        }
        break;
      }

      case "get_active_tab": {
        try {
          let activeTabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
          if (!activeTabs || activeTabs.length === 0) {
            activeTabs = await chrome.tabs.query({ active: true });
          }
          if (!activeTabs || activeTabs.length === 0) {
            activeTabs = await chrome.tabs.query({});
          }

          if (activeTabs && activeTabs.length > 0) {
            const tab = activeTabs[0];
            sendReply({
              id,
              success: true,
              action: "get_active_tab",
              tab_id: tab.id,
              title: tab.title || "",
              url: tab.url || "",
              active: Boolean(tab.active),
            });
          } else {
            sendReply({
              id,
              success: false,
              action: "get_active_tab",
              error: "No active tab found",
            });
          }
        } catch (err) {
          sendReply({
            id,
            success: false,
            action: "get_active_tab",
            error: `Failed to get active tab: ${err.message || String(err)}`,
          });
        }
        break;
      }

      case "close_tab": {
        const tabId = msg.tab_id ? Number(msg.tab_id) : null;
        const query = (msg.query || msg.filter || msg.target || msg.title || msg.url || "").toLowerCase().trim();
        try {
          const allTabs = await chrome.tabs.query({});
          let target = null;
          if (tabId) {
            target = allTabs.find((t) => t.id === tabId);
          } else if (query) {
            target = allTabs.find(
              (t) =>
                (t.title && t.title.toLowerCase().includes(query)) ||
                (t.url && t.url.toLowerCase().includes(query))
            );
          } else {
            const activeTabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
            if (activeTabs && activeTabs.length > 0) {
              target = activeTabs[0];
            }
          }

          if (!target || !target.id) {
            sendReply({
              id,
              success: false,
              action: "close_tab",
              error: `No tab found to close matching '${query || tabId || "active"}'`,
            });
            return;
          }

          await chrome.tabs.remove(target.id);
          sendReply({
            id,
            success: true,
            action: "close_tab",
            closed_tab_id: target.id,
            title: target.title || "",
            url: target.url || "",
          });
        } catch (err) {
          sendReply({
            id,
            success: false,
            action: "close_tab",
            error: `Failed to close tab: ${err.message || String(err)}`,
          });
        }
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

// Periodic alarm keep-alive to protect against Manifest V3 worker idle termination
if (typeof chrome !== "undefined" && chrome.alarms) {
  try {
    chrome.alarms.create("axiom_keep_alive", { periodInMinutes: 0.4 }); // Every ~24s
    chrome.alarms.onAlarm.addListener((alarm) => {
      if (alarm.name === "axiom_keep_alive") {
        log("Keep-alive alarm triggered: ensuring WebSocket link is active");
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          connect();
        }
      }
    });
  } catch (err) {
    log("Failed to register chrome.alarms keep-alive:", err);
  }
}

