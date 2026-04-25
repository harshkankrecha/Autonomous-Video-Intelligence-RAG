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
  const answer = document.getElementById("output");
  const url = await getCurrentTabUrl();
  const user_id = await getUserId();
  const videoId = getYouTubeVideoId(url);

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

  output.innerText =
    JSON.stringify(data);
});