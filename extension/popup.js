document.addEventListener("DOMContentLoaded", async () => {
    try {
        const url = await getCurrentTabUrl();
        const userId = await getUserId();
        const videoId = getYouTubeVideoId(url);

        if (videoId && userId) {
            await loadHistory(videoId, userId);
        } else {
            document.getElementById("history-container").innerHTML = "<p class='history-status'>Not a YouTube video page.</p>";
        }
    } catch (e) {
        console.error("Error initiating popup:", e);
    }
});

async function loadHistory(videoId, userId) {
    const container = document.getElementById("history-container");
    container.innerHTML = "<p class='history-status'>Loading history...</p>";

    try {
        const res = await fetch(`http://127.0.0.1:8000/history?video_id=${videoId}&user_id=${userId}`);
        const data = await res.json();
        
        renderHistory(data.history);
    } catch (error) {
        console.error("Failed to load history:", error);
        container.innerHTML = "<p class='history-status'>Could not load history.</p>";
    }
}

function renderHistory(history) {
    const container = document.getElementById("history-container");
    container.innerHTML = "";

    if (!history || history.length === 0) {
        container.innerHTML = "<p class='history-status'>No past questions for this video.</p>";
        return;
    }
    history.forEach(item => {
        const itemDiv = document.createElement("div");
        itemDiv.className = "history-item";
        itemDiv.innerHTML = `
            <div class="history-q"><strong>Q:</strong> ${item.question || "Unknown question"}</div>
            <div class="history-a">${parseMarkdown(JSON.stringify(item.answer)) || "Unknow answer"}</div>
        `;
        container.appendChild(itemDiv);
    });
}


async function getUserId() {
  let user_id = await chrome.storage.local.get("user_id");

  if (!user_id.user_id) {
    const newId = crypto.randomUUID();
    await chrome.storage.local.set({ user_id: newId });
    return newId;
  }
  return user_id.user_id;
}

function getYouTubeVideoId(url) {
  const regex = /(?:youtube\.com\/.*v=|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/;
  const match = url.match(regex);
  return match ? match[1] : null;
}

async function getCurrentTabUrl() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab.url;
}

document.getElementById("send").addEventListener("click", async () => {
  const question = document.getElementById("input").value;
  console.log("Sending request...");
  const outputElement = document.getElementById("output");
  
  outputElement.innerHTML = `
    <div class="skeleton-loader">
      <div class="skeleton-line header"></div>
      <div class="skeleton-line body-long"></div>
      <div class="skeleton-line body-medium"></div>
      <div class="skeleton-line body-short"></div>
      <br/>
      <div class="skeleton-line header" style="width: 45%;"></div>
      <div class="skeleton-line body-long"></div>
      <div class="skeleton-line body-medium"></div>
    </div>
  `;

  const url = await getCurrentTabUrl();
  const user_id = await getUserId();
  const videoId = getYouTubeVideoId(url);

  try {
    const res = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        user_id: user_id,
        question: question,
        video_id: videoId   
      })
    });

    const data = await res.json();

    let markdownText = JSON.stringify(data);
    
    outputElement.innerHTML = parseMarkdown(markdownText);

  } catch (error) {
    console.error(error);
    outputElement.innerText = "Error fetching response.";
  }
});

function parseMarkdown(markdownText){
  markdownText = markdownText.replace(/\\n/g, '\n');
    markdownText = markdownText.replace(/^([A-Z][A-Za-z\s\-\:\,\&]+)(?=\n\n\*|\n\*)/gm, '## $1');
    marked.setOptions({
      breaks: true,
      gfm: true
    });
    const rawHtml = marked.parse(markdownText);
    const cleanHtml = DOMPurify.sanitize(rawHtml);
    return cleanHtml;
}


