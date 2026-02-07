// Auto-record vertical map video when visiting the page with ?record=0.
(() => {
  const params = new URLSearchParams(window.location.search);
  const shouldAutoRecord = params.get("record") === "0";
  if (!shouldAutoRecord) return;

  const captureWidth = 1080;
  const captureHeight = 1920;

  document.documentElement.classList.add("record-mode");
  document.body.classList.add("record-mode");
  document.documentElement.style.setProperty("--capture-width", `${captureWidth}px`);
  document.documentElement.style.setProperty("--capture-height", `${captureHeight}px`);

  function waitForCanvas(timeoutMs = 12000) {
    const start = performance.now();
    return new Promise((resolve, reject) => {
      const poll = () => {
        const canvas = document.querySelector("#map canvas");
        if (canvas) return resolve(canvas);
        if (performance.now() - start > timeoutMs) return reject(new Error("No map canvas found"));
        requestAnimationFrame(poll);
      };
      poll();
    });
  }

  function makeRecorder(canvas) {
    const stream = canvas.captureStream(30);
    const options = { mimeType: "video/webm;codecs=vp9" };
    let recorder;
    try {
      recorder = new MediaRecorder(stream, options);
    } catch (e) {
      recorder = new MediaRecorder(stream);
    }

    const chunks = [];
    let started = false;
    let stopped = false;

    recorder.ondataavailable = e => e.data && e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: "video/webm" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "map-story-tiktok.webm";
      a.click();
      URL.revokeObjectURL(url);
      window.__recordingActive = false;
    };

    function startRecording() {
      if (started) return;
      started = true;
      window.__recordingActive = true;
      recorder.start();
      console.log("Recording started");
    }

    function stopRecording() {
      if (!started || stopped) return;
      stopped = true;
      setTimeout(() => recorder.stop(), 200);
    }

    const stopAfterStoryboard = () => stopRecording();

    window.addEventListener("storyboard-finished", stopAfterStoryboard);
    window.addEventListener("beforeunload", stopRecording);

    if (window.__storyboardStarted) {
      startRecording();
    } else {
      window.addEventListener("storyboard-started", startRecording, { once: true });
    }

    if (window.__storyboardFinished) stopAfterStoryboard();

    setTimeout(stopRecording, 180000);
  }

  waitForCanvas()
    .then(makeRecorder)
    .catch(err => console.error("Auto-record failed:", err.message));
})();
