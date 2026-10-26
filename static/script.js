const fileInput = document.getElementById("audioFile");
const uploadBtn = document.getElementById("uploadBtn");
const statusEl = document.getElementById("status");
const library = document.getElementById("library");
const player = document.getElementById("player");
const nowPlaying = document.getElementById("nowPlaying");
const segLog = document.getElementById("segLog");

let hls = null;

// Upload song to the backend
uploadBtn.addEventListener("click", async () => {
  if (!fileInput.files.length) {
    statusEl.textContent = "Please choose an audio file first.";
    return;
  }
  const formData = new FormData();
  formData.append("audio", fileInput.files[0]);
  formData.append("segment_time", document.getElementById("segTime").value);

  statusEl.textContent = "Uploading and segmenting... please wait";
  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      statusEl.textContent = "Error: " + data.error;
      return;
    }
    statusEl.textContent =
      `Done! "${data.title}" was cut into ${data.segments} segments.`;
    loadLibrary();
  } catch (err) {
    statusEl.textContent = "Server not reachable.";
  }
});

// Show all uploaded tracks
async function loadLibrary() {
  const res = await fetch("/api/tracks");
  const tracks = await res.json();
  library.innerHTML = "";
  if (!tracks.length) {
    library.innerHTML = "<li>No tracks yet</li>";
    return;
  }
  tracks.forEach(t => {
    const li = document.createElement("li");
    li.textContent = `▶ ${t.title}  (${t.segments} segments x ${t.segment_time}s)`;
    li.onclick = () => playTrack(t);
    library.appendChild(li);
  });
}

// Play using HLS
function playTrack(track) {
  nowPlaying.textContent = "Now streaming: " + track.title;
  segLog.innerHTML = "";

  if (hls) hls.destroy();

  if (Hls.isSupported()) {
    hls = new Hls();
    hls.loadSource(track.url);
    hls.attachMedia(player);

    // Log every segment as the browser downloads it
    hls.on(Hls.Events.FRAG_LOADED, (event, data) => {
      const li = document.createElement("li");
      li.textContent = `✔ Loaded segment #${data.frag.sn + 1}`;
      segLog.appendChild(li);
      segLog.scrollTop = segLog.scrollHeight;
    });

    hls.on(Hls.Events.MANIFEST_PARSED, () => player.play());
  } else if (player.canPlayType("application/vnd.apple.mpegurl")) {
    // Safari plays HLS natively
    player.src = track.url;
    player.play();
  } else {
    nowPlaying.textContent = "HLS is not supported in this browser.";
  }
}

loadLibrary();